#!/usr/bin/env python3
"""Frontier-model quality check of saved drydock-bench results.

The mechanical grader only says whether a planted bug was located. This asks a
frontier judge, per case, to (a) review the diff itself, as a reference for which
real issues exist, and (b) label every finding the candidate model produced:
real_issue | minor_valid | false_positive | hallucinated, plus whether the
planted bug was correctly understood and whether severity is reasonable.
Nothing is re-run; it reads an existing results JSONL plus the dataset.

  python3 judge.py --results "../../runs/drydock/openrouter/or:qwen3.8-27b+think-off+typed-prompt#r1.jsonl"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
URL = "https://openrouter.ai/api/v1/chat/completions"
LABELS = ("real_issue", "minor_valid", "false_positive", "hallucinated")

SYSTEM = """You are a principal engineer auditing an automated code reviewer.
You get a patch (unified diff plus context) and the findings an AI reviewer produced for it.
Judge strictly from the code in the diff and context; do not reward plausible-sounding prose.

Return JSON ONLY with keys:
- "reference_issues": real defects YOU find in the changed code (bugs, security problems, broken
  behaviour; not style nits). Each: {"id": "R1", "file", "line", "severity": "critical|high|medium|low",
  "description"}. Exclude the injected defect if one is disclosed below. Use [] if there are none.
- "verdicts": one entry per reviewer finding, in order. Each:
  {"index": n,
   "label": "real_issue" (a genuine defect worth raising) | "minor_valid" (true but low value: nit,
            speculative hardening, style) | "false_positive" (the claim is wrong about this code)
            | "hallucinated" (refers to code, behaviour or files not present in the patch),
   "matches_injected": true|false,
   "explanation_correct": true|false|null (only for matches_injected: does it correctly explain WHY
            the injected change is wrong?),
   "severity_ok": "ok"|"too_high"|"too_low",
   "matches_reference": "R1".. or null,
   "reason": one short sentence}
- "usefulness": 1-5, how useful this review would be to the patch author (5 = catches what matters,
  little noise)
- "comment": one sentence on the review's biggest strength or weakness."""


def load_jsonl(path: Path) -> dict[str, dict]:
    cases = {}
    for line in path.read_text().splitlines():
        d = json.loads(line)
        if d.get("type") == "case":
            cases[d["case_id"]] = d
    return cases


def user_prompt(case: dict, result: dict) -> str:
    meta = case.get("bench_meta") or {}
    injected = "No defect was injected into this patch (it is the original, unmodified change)."
    if meta.get("kind") == "planted":
        e = case["expected_findings"][0]
        injected = (f"One defect WAS deliberately injected for this benchmark at {e['file']}:{e['line']} "
                    f"({e['category']}): {meta.get('note')}. Original line: {meta.get('before') or '(none: line inserted)'!r}; "
                    f"injected line: {meta.get('after')!r}. The rest of the patch is the author's real change.")
    findings = [{k: f.get(k) for k in ("file", "line", "category", "severity", "confidence", "evidence",
                                         "explanation", "suggestion")} for f in result.get("findings", [])]
    return (f"{injected}\n\n## Context\n{case['context_bundle']}\n\n## Diff\n{case['patch_diff']}\n\n"
            f"## Reviewer findings ({len(findings)})\n"
            + "\n".join(f"[{i}] {json.dumps(f, ensure_ascii=False)}" for i, f in enumerate(findings))
            + ("\n(none)" if not findings else ""))


def call(model: str, key: str, system: str, user: str, retries: int = 3) -> tuple[dict, float]:
    body = json.dumps({"model": model, "temperature": 0, "response_format": {"type": "json_object"},
                       "usage": {"include": True},
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(URL, data=body, headers={"Authorization": f"Bearer {key}",
                                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                d = json.load(r)
            text = d["choices"][0]["message"]["content"]
            text = text[text.find("{"): text.rfind("}") + 1]
            return json.loads(text), (d.get("usage") or {}).get("cost", 0.0)
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            if attempt == retries:
                raise RuntimeError(f"judge call failed: {e}") from e
            time.sleep(2 ** (attempt + 1))
    raise AssertionError


def summarize(judged: list[dict]) -> list[str]:
    labels, sev = Counter(), Counter()
    injected_hits = injected_correct = ref_total = ref_found = 0
    useful = []
    per_kind = {"planted": Counter(), "clean": Counter()}
    for j in judged:
        v = j["judge"]
        kind = j["kind"]
        useful.append(v.get("usefulness", 0))
        refs = {r["id"] for r in v.get("reference_issues", [])}
        ref_total += len(refs)
        ref_found += len(refs & {x.get("matches_reference") for x in v.get("verdicts", [])})
        hits = [x for x in v.get("verdicts", []) if x.get("matches_injected")]
        if kind == "planted" and hits:  # count cases, not findings: several may cite the same bug
            injected_hits += 1
            injected_correct += any(x.get("explanation_correct") for x in hits)
        for x in v.get("verdicts", []):
            labels[x.get("label")] += 1
            per_kind[kind][x.get("label")] += 1
            sev[x.get("severity_ok")] += 1
    n = sum(labels.values()) or 1
    planted = sum(1 for j in judged if j["kind"] == "planted")
    out = [f"cases judged: {len(judged)} ({planted} planted, {len(judged) - planted} clean); findings: {n}",
           "finding labels: " + ", ".join(f"{k} {labels[k]} ({100 * labels[k] / n:.0f}%)" for k in LABELS),
           f"precision (real + minor valid): {100 * (labels['real_issue'] + labels['minor_valid']) / n:.0f}%  "
           f"| high-value precision (real only): {100 * labels['real_issue'] / n:.0f}%  "
           f"| hallucinated: {100 * labels['hallucinated'] / n:.0f}%",
           f"injected bug found (judge's view): {injected_hits}/{planted}; explanation correct: {injected_correct}/{injected_hits or 1}",
           f"reference issues (real pre-existing defects the judge found): {ref_total}; caught by the model: {ref_found}",
           "severity: " + ", ".join(f"{k} {v}" for k, v in sev.most_common()),
           f"usefulness (1-5): mean {sum(useful) / len(useful):.2f}; distribution {dict(sorted(Counter(useful).items()))}",
           "by case kind: " + "; ".join(f"{k}: {dict(c)}" for k, c in per_kind.items())]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True)
    ap.add_argument("--dataset", default=str(HERE / "data/drydock-planted-v2.json"))
    ap.add_argument("--judge", default="anthropic/claude-opus-5.5")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", help="default: <results>.judge-<model>.jsonl")
    ap.add_argument("--summary-only", action="store_true", help="re-summarize existing verdicts without new calls")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY") or (ROOT / ".orkey").read_text().strip()
    cases = {c["case_id"]: c for c in json.loads(Path(args.dataset).read_text())["cases"]}
    results = load_jsonl(Path(args.results))
    out = Path(args.out or f"{args.results}.judge-{args.judge.split('/')[-1]}.jsonl")
    done = load_jsonl(out) if out.exists() else {}
    todo = [cid for cid, r in results.items() if r.get("ok") and cid in cases and cid not in done]
    print(f"{len(results)} results, {len(done)} already judged, {len(todo)} to judge with {args.judge}", file=sys.stderr)
    if args.summary_only:
        todo = []

    spend = 0.0

    def work(cid: str) -> dict:
        verdict, cost = call(args.judge, key, SYSTEM, user_prompt(cases[cid], results[cid]))
        return {"type": "case", "case_id": cid, "kind": cases[cid]["bench_meta"]["kind"],
                "n_findings": len(results[cid].get("findings", [])), "judge": verdict, "cost_usd": cost}

    with out.open("a") as fh, ThreadPoolExecutor(args.workers) as pool:
        for rec in pool.map(work, todo):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            spend += rec["cost_usd"]
            v = rec["judge"]
            print(f"{rec['case_id'][:34]:34} findings={rec['n_findings']} "
                  f"labels={dict(Counter(x.get('label') for x in v.get('verdicts', [])))} "
                  f"refs={len(v.get('reference_issues', []))} useful={v.get('usefulness')}", file=sys.stderr)

    judged = list(load_jsonl(out).values())
    lines = summarize(judged)
    total_cost = sum(j.get("cost_usd", 0) for j in judged)
    print("\n".join(lines + [f"judge spend: ${total_cost:.2f} (this run ${spend:.2f})", f"wrote {out}"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
