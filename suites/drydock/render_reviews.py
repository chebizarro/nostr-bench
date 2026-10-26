#!/usr/bin/env python3
"""Render saved drydock-bench results as readable Markdown reviews.

One file per results JSONL: for every case, the patch it reviewed, the planted
bug (hidden from the model), each finding as the reviewer wrote it, the
frontier judge's verdict on that finding when a judge file exists, and the
diff in a collapsed block so claims can be checked against the code.

Output contains the hidden answers, so write it under runs/ (gitignored) and
never publish it.

  python3 render_reviews.py --results "../../runs/drydock/openrouter/or:qwen3.8-27b+think-off+typed-prompt#r1.jsonl"
  python3 render_reviews.py --results a.jsonl b.jsonl --out-dir ../../runs/drydock/reviews
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATASETS = ["drydock-planted-v1.json", "drydock-planted-v2.json", "drydock-agentic-v2.json"]
LABEL_BADGE = {"real_issue": "✅ real issue", "minor_valid": "➖ minor but valid",
               "false_positive": "❌ false positive", "hallucinated": "👻 hallucinated"}


def load_cases(paths: list[Path]) -> dict[str, dict]:
    """case_id -> dataset case; later datasets fill ids missing from earlier ones."""
    cases: dict[str, dict] = {}
    for p in paths:
        if p.exists():
            for c in json.loads(p.read_text())["cases"]:
                cases.setdefault(c["case_id"], c)
    return cases


def load_jsonl(path: Path) -> tuple[dict, dict[str, dict]]:
    header, records = {}, {}
    for line in path.read_text().splitlines():
        d = json.loads(line)
        if d.get("type") == "header":
            header = d
        elif d.get("type") == "case":
            records[d["case_id"]] = d
    return header, records


def judge_for(results: Path) -> dict[str, dict]:
    files = sorted(glob.glob(glob.escape(str(results)) + ".judge-*.jsonl"))
    return load_jsonl(Path(files[0]))[1] if files else {}


def subject(case: dict) -> str:
    m = re.search(r"## patch description\n(.+)", case.get("context_bundle", ""))
    return m.group(1).strip() if m else "(no description)"


def quote(text: str) -> str:
    return "\n".join("> " + line for line in (text or "").strip().splitlines()) or "> —"


def render_case(case_id: str, rec: dict, case: dict | None, verdicts: dict | None) -> list[str]:
    meta = rec.get("bench_meta") or (case or {}).get("bench_meta") or {}
    out = [f"## `{case_id}`", ""]
    if case:
        out += [f"**Repo:** {meta.get('repo') or '?'}  ·  **Patch:** {subject(case)}  ·  "
                f"**Changed files:** {', '.join(case.get('changed_files', []))}", ""]
    if meta.get("kind") == "planted":
        e = (rec.get("expected") or [{}])[0]
        out += [f"🎯 **Planted bug (hidden from the model):** `{e.get('file')}:{e.get('line')}` "
                f"({e.get('category')}) — {meta.get('note')}",
                f"  - original: `{meta.get('before') or '(line inserted)'}`",
                f"  - planted:  `{meta.get('after')}`", ""]
    else:
        out += ["🧪 **Clean control** — the author's real, unmodified change (no bug planted).", ""]
    score = rec.get("score", {})
    calls = rec.get("calls", [])
    out += [f"**Outcome:** {'completed' if rec.get('ok') else 'FAILED (' + str(rec.get('failed_stage')) + ')'}  ·  "
            f"strict hit {score.get('true_positives', 0)}/{score.get('expected', 0)}  ·  "
            f"detected {rec.get('detected', 0)}  ·  {rec.get('wall_ms', 0) / 1000:.0f}s  ·  "
            f"{len(calls)} model calls  ·  {sum(k.get('completion_tokens', 0) for k in calls):,} output tokens", ""]
    if not rec.get("ok"):
        out += ["```", (rec.get("error") or "")[:800], "```", ""]
    findings = rec.get("findings") or []
    by_index = {v.get("index"): v for v in (verdicts or {}).get("judge", {}).get("verdicts", [])} if verdicts else {}
    if not findings:
        out += ["_No findings._", ""]
    for i, f in enumerate(findings):
        sev = f.get("severity") or f.get("priority") or "?"
        title = f"### Finding {i + 1}: {sev} · {f.get('category')} · `{f.get('file')}:{f.get('line')}`"
        if f.get("confidence") is not None:
            title += f" · confidence {f.get('confidence')}"
        out += [title, ""]
        v = by_index.get(i)
        if v:
            badge = LABEL_BADGE.get(v.get("label"), v.get("label"))
            extra = []
            if v.get("matches_injected"):
                extra.append("hits the planted bug" + (" (explanation correct)" if v.get("explanation_correct") else " (explanation wrong)"))
            if v.get("severity_ok") and v.get("severity_ok") != "ok":
                extra.append(f"severity {v['severity_ok'].replace('_', ' ')}")
            out += [f"**Judge:** {badge}" + (f" — {'; '.join(extra)}" if extra else "") + f". _{v.get('reason', '')}_", ""]
        out += ["**Explanation**", quote(f.get("explanation")), ""]
        if f.get("evidence"):
            out += ["**Evidence**", quote(f.get("evidence")), ""]
        if f.get("suggestion"):
            out += ["**Suggestion**", quote(f.get("suggestion")), ""]
        if f.get("suggested_diff") or f.get("suggested_code"):
            out += ["```", (f.get("suggested_diff") or f.get("suggested_code")).strip(), "```", ""]
    if verdicts:
        j = verdicts.get("judge", {})
        out += [f"**Judge overall:** usefulness {j.get('usefulness')}/5 — {j.get('comment', '')}", ""]
        refs = j.get("reference_issues") or []
        hit = {v.get("matches_reference") for v in j.get("verdicts", [])}
        missed = [r for r in refs if r.get("id") not in hit]
        if missed:
            out += ["**Real issues the judge found that this review missed:**", ""]
            out += [f"- `{r.get('file')}:{r.get('line')}` ({r.get('severity')}) {r.get('description')}" for r in missed]
            out += [""]
    if case:
        out += ["<details><summary>Diff reviewed</summary>", "", "```diff", case["patch_diff"].rstrip(), "```",
                "", "</details>", ""]
    return out + ["---", ""]


def render(results: Path, cases: dict[str, dict], out_dir: Path) -> Path:
    header, records = load_jsonl(results)
    verdicts = judge_for(results)
    planted = [r for r in records.values() if (r.get("bench_meta") or {}).get("kind") == "planted"]
    lines = [f"# Reviews: `{header.get('label') or results.stem}`", "",
             f"Source: `{results}`  ·  dataset `{header.get('dataset_id')}`  ·  {len(records)} cases "
             f"({len(planted)} planted, {len(records) - len(planted)} clean)"
             + ("  ·  agentic path" if header.get("agentic") else "")
             + (f"  ·  judged by frontier model ({len(verdicts)} cases)" if verdicts else ""), "",
             "Each case shows what the reviewer said. Planted-bug details are hidden from the model; "
             "clean controls are the authors' real changes, where findings may be real pre-existing bugs or noise.", ""]
    # Planted first, then clean controls; judged cases first within each group.
    order = sorted(records, key=lambda cid: ((records[cid].get("bench_meta") or {}).get("kind") != "planted",
                                             cid not in verdicts, cid))
    for cid in order:
        lines += render_case(cid, records[cid], cases.get(cid), verdicts.get(cid))
    out_dir.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9._+@-]+", "_", results.name.removesuffix(".jsonl")) + ".md"
    out = out_dir / name
    out.write_text("\n".join(lines))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--data-dir", default=str(HERE / "data"))
    ap.add_argument("--out-dir", default=str(ROOT / "runs/drydock/reviews"))
    args = ap.parse_args()
    cases = load_cases([Path(args.data_dir) / d for d in DATASETS])
    for r in args.results:
        print(render(Path(r), cases, Path(args.out_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
