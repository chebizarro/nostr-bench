#!/usr/bin/env python3
"""Aggregate drydock-bench JSONL into a ranked Markdown + JSON report.

Metrics per configuration (reps pooled; min/max across reps for the headline):
  strict      drydock's own grade: category + file + line within tolerance (eval.ScoreCase)
  detected    planted bug found on the right file, by line OR by quoting the planted code
  |line err|  median absolute line offset of detected findings (diff line counting)
  noise       findings per clean control case (originals may hold real bugs, so this
              is a noise rate, not a strict false-positive rate); hi = critical/high only
  ok          share of cases where planner -> reviewer -> walkthrough completed
  repairs     JSON repair calls per case (strict-schema reliability)
  p50 / p95   whole-review wall time; >120s = share of cases with any call over
              drydock's production per-call timeout
  pp / tg     prefill / decode tokens per second (llama.cpp timings)
  $/review    wall time x rig cost_per_hour
Ranking: strict recall, among configurations that are deployable (ok >= 90% and
>120s <= 10%). Gaps <= 5 points with overlapping rep ranges are ties.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def load_runs(runs_dir: Path, phase: str | None):
    """Yield (label, rep_file, header, {case_id: case}) — last record per case wins."""
    for path in sorted(runs_dir.rglob("*.jsonl")):
        if phase and path.parent.name != phase:
            continue
        header, cases = {}, {}
        for line in path.read_text().splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "header":
                header = d
            elif d.get("type") == "case":
                cases[d["case_id"]] = d
        if cases:
            label = path.stem.rsplit("#r", 1)[0]
            gpu = Path(str(path) + ".gpu.json")
            header["_gpu"] = json.loads(gpu.read_text()) if gpu.exists() else {}
            yield path.parent.name, label, path, header, cases


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def metrics(case_list: list[dict], prod_timeout_ms: int) -> dict:
    """Metrics over a flat list of case records (one rep, or several pooled)."""
    planted = [c for c in case_list if (c.get("bench_meta") or {}).get("kind") == "planted"]
    clean = [c for c in case_list if (c.get("bench_meta") or {}).get("kind") == "clean"]
    exp = sum(c["score"]["expected"] for c in planted) or 1
    calls = [k for c in case_list for k in c["calls"]]
    # llama.cpp prompt_n/predicted_n match the timed work (prompt-cache hits excluded).
    pt = sum(k.get("prompt_n", 0) for k in calls if k.get("prompt_ms"))
    pms = sum(k.get("prompt_ms", 0) for k in calls if k.get("prompt_n"))
    ct = sum(k.get("predicted_n", 0) for k in calls if k.get("predicted_ms"))
    dms = sum(k.get("predicted_ms", 0) for k in calls if k.get("predicted_n"))
    by_op = defaultdict(lambda: [0, 0])
    for c in planted:
        op = c["bench_meta"].get("op", "?")
        by_op[op][0] += c.get("detected", 0)
        by_op[op][1] += c["score"]["expected"]
    sec_ops = {"verify_bypass", "hardcoded_secret", "tls_off"}
    fam = defaultdict(lambda: [0, 0])
    for op, (d, n) in by_op.items():
        f = fam["security" if op in sec_ops else "correctness"]
        f[0] += d
        f[1] += n
    line_err = [abs(e) for c in planted for e in (c.get("line_errors") or [])]
    hi = lambda f: (f.get("severity") or "").lower() in ("critical", "high")
    conf = [(f.get("confidence") or 0) for c in planted + clean for f in c["findings"]]
    cases = case_list
    return {
        "cases": len(cases),
        "strict": sum(c["score"]["true_positives"] for c in planted) / exp,
        "detected": sum(c.get("detected", 0) for c in planted) / exp,
        "lenient": sum(c.get("lenient_tp", 0) for c in planted) / exp,
        "line_err_med": st.median(line_err) if line_err else None,
        "noise": st.mean(len(c["findings"]) for c in clean) if clean else None,
        "noise_hi": st.mean(sum(hi(f) for f in c["findings"]) for c in clean) if clean else None,
        "extra_on_planted": st.mean(c["score"]["false_positives"] for c in planted) if planted else None,
        "calib_mae": (sum(c["score"]["calibration_abs_sum"] for c in planted) /
                      max(1, sum(c["score"]["predicted"] for c in planted))),
        "mean_conf": st.mean(conf) if conf else None,
        "ok": sum(c["ok"] for c in cases) / len(cases),
        "repairs": st.mean(c["repair_attempts"] for c in cases),
        "p50_s": pct([c["wall_ms"] / 1000 for c in cases], 0.5),
        "p95_s": pct([c["wall_ms"] / 1000 for c in cases], 0.95),
        "over_prod": sum(any(k["wall_ms"] > prod_timeout_ms for k in c["calls"]) for c in cases) / len(cases),
        "pp_tps": pt / (pms / 1000) if pms else None,
        "tg_tps": ct / (dms / 1000) if dms else None,
        "reason_kchars": st.mean(sum(k.get("reasoning_chars", 0) for k in c["calls"]) for c in cases) / 1000,
        "fail_stages": dict(sorted(_count(c.get("failed_stage") for c in cases if not c["ok"]).items())),
        "by_family": {f: (fam[f][0] / fam[f][1] if fam[f][1] else None) for f in ("correctness", "security")},
        "by_op": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_op.items())},
        "wall_h": sum(c["wall_ms"] for c in cases) / 3.6e6,
        "billed_usd": sum(k.get("cost_usd", 0) for k in calls),
        "retries": sum(k.get("retries", 0) for k in calls),
        "providers": dict(_count(k.get("provider") for k in calls if k.get("provider"))),
        "roles": role_signals(cases),
    }


def role_signals(cases: list[dict]) -> dict:
    """Per-stage reliability and token budget, for splitting roles across cards."""
    n = len(cases) or 1
    out = {}
    for stage in ("planner", "reviewer", "walkthrough"):
        calls = [k for c in cases for k in c["calls"] if k["stage"] == stage]
        repairs = [k for c in cases for k in c["calls"] if k["stage"] == f"repair:{stage}"]
        failed = sum(1 for c in cases if not c["ok"] and c.get("failed_stage") == stage)
        out[stage] = {
            "repairs_per_case": len(repairs) / n,
            "fail_rate": failed / n,
            "out_tokens_per_case": sum(k["completion_tokens"] for k in calls + repairs) / n,
            "in_tokens_per_case": sum(k["prompt_tokens"] for k in calls + repairs) / n,
        }
    return out


def _count(xs):
    d = defaultdict(int)
    for x in xs:
        d[x or "unknown"] += 1
    return d


def pooled(reps: list[list[dict]], cost_per_hour: float, prod_timeout_ms: int) -> dict:
    """Recompute every metric over the pooled case records (percentiles and
    token rates do not average), keeping per-rep strict recall for the range."""
    out = metrics([c for rep in reps for c in rep], prod_timeout_ms)
    per_rep = [metrics(rep, prod_timeout_ms)["strict"] for rep in reps]
    hosted = out["billed_usd"] > 0
    out.update(strict_min=min(per_rep), strict_max=max(per_rep), reps=len(reps), hosted=hosted,
               usd_per_review=(out["billed_usd"] if hosted else cost_per_hour * out["wall_h"]) / max(1, out["cases"]))
    return out


def lemmy_fit(label: str, roster: dict) -> str:
    """How the model behind an OpenRouter label would deploy on 2x P40."""
    if label.startswith("ref:"):
        return "cloud only"
    mid = label.removeprefix("or:").split("@")[0].split("+")[0]
    m = next((m for m in roster.get("models", []) if m["id"] == mid), None)
    if not m:
        return "?"
    q, gb = next(iter(m["quants"].items()))
    gpus = m.get("gpus_by_quant", {}).get(q) or m.get("gpus") or (1 if gb <= 19 else 2)
    return f"{q} {gb:g} GB, {gpus}xP40" + (" +CPU offload" if m.get("offload") else "")


def fmt(v, kind="pct"):
    if v is None or (isinstance(v, float) and v != v):
        return "–"
    if kind == "pct":
        return f"{100 * v:.0f}"
    if kind == "s":
        return f"{v:.0f}"
    if kind == "f1":
        return f"{v:.1f}"
    if kind == "f2":
        return f"{v:.2f}"
    if kind == "usd":
        return f"{v * 100:.2f}¢"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", default=str(ROOT / "runs/drydock"))
    ap.add_argument("--phase", help="screen | efficiency | deploy (default: all)")
    ap.add_argument("--cost-per-hour", type=float, default=0.15)
    ap.add_argument("--prod-timeout-s", type=int, default=120)
    ap.add_argument("--out", default=str(ROOT / "report/drydock-results"))
    ap.add_argument("--roster", default=str(HERE / "roster.yaml"))
    args = ap.parse_args()
    try:
        import yaml
        roster = yaml.safe_load(Path(args.roster).read_text())
    except Exception:
        roster = {}

    groups = defaultdict(list)
    meta, incomplete = {}, []
    for phase, label, path, header, cases in load_runs(Path(args.runs_dir), args.phase):
        want = header.get("dataset_cases")
        if not want or len(cases) < want:
            # A partial rep would rank on whatever cases happened to finish.
            incomplete.append(f"`{path.name}` {len(cases)}/{want or '?'}")
            continue
        groups[(phase, label)].append(list(cases.values()))
        meta[(phase, label)] = header
    if not groups:
        print("no complete runs found" + ("; incomplete: " + ", ".join(incomplete) if incomplete else ""))
        return 1
    rows = []
    for (phase, label), reps in groups.items():
        p = pooled(reps, args.cost_per_hour, args.prod_timeout_s * 1000)
        # Hosted latency says nothing about P40 speed: gate hosted runs on
        # pipeline completion only; Lemmy runs also on the production timeout.
        p["deployable"] = p["ok"] >= 0.9 and (p["hosted"] or p["over_prod"] <= 0.10)
        p["lemmy"] = lemmy_fit(label, roster) if p["hosted"] else "measured"
        p.update(phase=phase, label=label, gpu=meta[(phase, label)].get("_gpu", {}))
        rows.append(p)
    rows.sort(key=lambda r: (not r["deployable"], -r["strict"], -r["detected"], r["p50_s"]))

    best = next((r for r in rows if r["deployable"]), None)
    lines = ["# Drydock local-model benchmark (2x P40)", "",
             "Hidden planted-bug suite built from drydock-test-corpus (see suites/drydock/README.md).",
             "Ranked by strict recall among deployable configs (ok >= 90%, >120s <= 10%).", "",
             "Hosted (OpenRouter) rows: $/review is billed cost and latency columns are not P40-representative.", "",
             "| # | phase | config | reps | strict (min–max) | detected | sec / corr | |line err| | noise / hi | ok | repairs | p50 s | p95 s | >120s | pp t/s | tg t/s | think kch | $/review | Lemmy fit | ok? |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        tie = ""
        if best and r is not best and r["deployable"] and best["strict"] - r["strict"] <= 0.05 \
                and r["strict_max"] >= best["strict_min"]:
            tie = " (tie)"
        lines.append(
            f"| {i} | {r['phase']} | `{r['label']}`{tie} | {r['reps']} | {fmt(r['strict'])} ({fmt(r['strict_min'])}–{fmt(r['strict_max'])}) "
            f"| {fmt(r['detected'])} | {fmt(r['by_family']['security'])} / {fmt(r['by_family']['correctness'])} "
            f"| {fmt(r.get('line_err_med'), 'f1')} | {fmt(r.get('noise'), 'f1')} / {fmt(r.get('noise_hi'), 'f1')} "
            f"| {fmt(r['ok'])} | {fmt(r['repairs'], 'f2')} | {fmt(r['p50_s'], 's')} | {fmt(r['p95_s'], 's')} | {fmt(r['over_prod'])} "
            f"| {fmt(r.get('pp_tps'), 's')} | {fmt(r.get('tg_tps'), 'f1')} | {fmt(r.get('reason_kchars'), 'f1')} "
            f"| {fmt(r['usd_per_review'], 'usd')} | {r['lemmy']} | {'✓' if r['deployable'] else '✗'} |")
    failures = "; ".join(f"`{r['label']}` {r['fail_stages']}" for r in rows if r["fail_stages"])
    lines += ["", "Failures by stage: " + (failures or "none"), ""]
    if incomplete:
        lines += ["Excluded incomplete reps: " + ", ".join(incomplete), ""]
    hosted_rows = [r for r in rows if r["hosted"]]
    if hosted_rows:
        retried = ", ".join(f"`{r['label']}` {r['retries']}" for r in hosted_rows if r["retries"])
        lines += [f"OpenRouter spend: ${sum(r['billed_usd'] for r in hosted_rows):.2f}; provider retries: "
                  + (retried or "none"), ""]
        lines += ["Providers that served each hosted config (quantization varies by provider):", ""]
        lines += [f"- `{r['label']}`: {r['providers']}" for r in hosted_rows]
        lines += [""]
    lines += ["Role signals: planner/walkthrough need strict JSON; output tokens per review drive P40 latency",
              "(decode is bandwidth-bound, so time is roughly out-tokens / tg-rate).", "",
              "| config | planner repairs/case | planner fail | reviewer repairs/case | reviewer fail | walkthrough fail "
              "| out tok/review (P / R / W) | in tok/review |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        g = r["roles"]
        lines.append(
            f"| `{r['label']}` | {g['planner']['repairs_per_case']:.2f} | {fmt(g['planner']['fail_rate'])}% "
            f"| {g['reviewer']['repairs_per_case']:.2f} | {fmt(g['reviewer']['fail_rate'])}% | {fmt(g['walkthrough']['fail_rate'])}% "
            f"| {g['planner']['out_tokens_per_case']:.0f} / {g['reviewer']['out_tokens_per_case']:.0f} / {g['walkthrough']['out_tokens_per_case']:.0f} "
            f"| {sum(s['in_tokens_per_case'] for s in g.values()):.0f} |")
    lines += [""]
    by_label = {(r["phase"], r["label"]): r for r in rows}
    pairs = [(by_label.get((r["phase"], r["label"].replace("+typed-prompt", "").replace("+calibrated-prompt", ""))), r)
             for r in rows if "+typed-prompt" in r["label"] or "+calibrated-prompt" in r["label"]]
    pairs = [(b, t) for b, t in pairs if b]
    if pairs:
        lines += ["Prompt fix A/B (`+typed-prompt` adds field types and allowed values to the planner and",
                  "reviewer system prompts; everything else identical). Δ = typed − production.", "",
                  "| config | strict | Δ strict | ok Δ | planner repairs/case | reviewer repairs/case | calls/review | out tok/review |",
                  "|---|---|---|---|---|---|---|---|"]
        for b, t in pairs:
            def calls(r):
                return sum(1 + s["repairs_per_case"] for s in r["roles"].values())
            def out_tok(r):
                return sum(s["out_tokens_per_case"] for s in r["roles"].values())
            lines.append(
                f"| `{b['label']}` | {fmt(b['strict'])} → {fmt(t['strict'])} | {100 * (t['strict'] - b['strict']):+.0f} "
                f"| {100 * (t['ok'] - b['ok']):+.0f} "
                f"| {b['roles']['planner']['repairs_per_case']:.2f} → {t['roles']['planner']['repairs_per_case']:.2f} "
                f"| {b['roles']['reviewer']['repairs_per_case']:.2f} → {t['roles']['reviewer']['repairs_per_case']:.2f} "
                f"| {calls(b):.2f} → {calls(t):.2f} | {out_tok(b):.0f} → {out_tok(t):.0f} |")
        lines += [""]
    lines += ["Per-operator detection (pooled over reps):", ""]
    lines += [f"- `{r['label']}`: {r['by_op']}" for r in rows]
    lines += ["", "Speculative-decoding guard: speculative variants must match their baseline's",
              "accuracy within the rep range (decoding is lossless); a drop means a serving bug."]
    Path(args.out + ".md").parent.mkdir(parents=True, exist_ok=True)
    Path(args.out + ".md").write_text("\n".join(lines) + "\n")
    Path(args.out + ".json").write_text(json.dumps(rows, indent=1, default=str))
    print("\n".join(lines))
    print(f"\nwrote {args.out}.md and .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
