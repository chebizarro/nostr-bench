"""Mode A — one-shot prompt. Single completion, no tools, no retries.

    python -m drivers.oneshot --model openai/gpt-oss-20b --task n1_implement --tier T1
"""
from __future__ import annotations

import argparse
import os

from grade import findings as findings_grade
from grade import extract, vitest_runner
from providers import get_provider

from .common import Task, RunResult, context_blob

SYSTEM = (
    "You are a precise senior TypeScript engineer. Return complete, runnable code. "
    "For each file you write, use a fenced block labelled with its path, e.g. "
    "```ts title=src/nip01.ts. For audit tasks, return ONLY a JSON array of findings."
)


def build_messages(task: Task, tier: str) -> list[dict]:
    ctx = task.starter_context()
    body = task.prompts[tier]
    user = body
    if ctx:
        user += "\n\n## Provided files\n\n" + context_blob(ctx)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def grade(task: Task, text: str) -> tuple[float, dict, bool]:
    if task.kind == "audit":
        parsed = extract.extract_findings(text)
        res = findings_grade.score_findings(parsed, task.answer_key())
        return res["score"], res, parsed is not None
    produced = extract.extract_files(text, task.target)
    base = task.starter_subdir
    res = vitest_runner.build_and_test(task.dir, produced, base_subdir=base)
    return round(res["pass_rate"] * 100, 1), res, bool(produced)


def run_cell(model: str, task_id: str, tier: str, arm: str, rep: int, *,
             price: dict | None = None, dry_run: bool = False) -> RunResult:
    task = Task.load(task_id)
    rr = RunResult(task=task_id, mode="oneshot", model=model, tier=tier, arm=arm, rep=rep)
    if dry_run:
        msgs = build_messages(task, tier)
        rr.detail = {"prompt_preview": msgs[-1]["content"][:600], "kind": task.kind}
        return rr
    provider = get_provider(arm, price=price)
    msgs = build_messages(task, tier)
    # Generous total budget with a bounded reasoning share, so thinking models
    # still emit a final answer on hard tasks instead of truncating mid-thought.
    max_out = int(os.environ.get("NOSTR_BENCH_MAX_OUTPUT", "30000"))
    reason_cap = int(os.environ.get("NOSTR_BENCH_REASONING_CAP", "15000"))
    out = provider.chat(model, msgs, temperature=0.2, max_tokens=max_out,
                        reasoning={"max_tokens": reason_cap})
    rr.prompt_tokens, rr.completion_tokens = out.prompt_tokens, out.completion_tokens
    rr.cost_usd, rr.wall_clock_s = out.cost_usd, out.wall_clock_s
    # Empty completion (e.g. reasoning ran to the token limit): score 0, don't let
    # stub-throwing code earn spurious partial credit.
    if not (out.text or "").strip():
        rr.score, rr.format_ok = 0.0, False
        rr.error = f"empty_completion (finish={out.finish_reason}, completion_tokens={out.completion_tokens})"
        rr.detail = {"reply_chars": 0, "finish_reason": out.finish_reason}
        return rr
    score, detail, fmt_ok = grade(task, out.text)
    rr.score, rr.detail, rr.format_ok = score, detail, fmt_ok
    rr.detail["reply_chars"] = len(out.text)
    rr.detail["finish_reason"] = out.finish_reason
    return rr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--tier", default="T1", choices=["T1", "T2"])
    ap.add_argument("--arm", default="cloud", choices=["cloud", "local", "routstr"])
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rr = run_cell(a.model, a.task, a.tier, a.arm, a.rep, dry_run=a.dry_run)
    if a.dry_run:
        print("DRY RUN — prompt preview:\n")
        print(rr.detail.get("prompt_preview", ""))
    else:
        name = rr.save()
        print(f"{name}: score={rr.score} tokens={rr.prompt_tokens}+{rr.completion_tokens} "
              f"cost=${rr.cost_usd} {rr.wall_clock_s:.1f}s")


if __name__ == "__main__":
    main()
