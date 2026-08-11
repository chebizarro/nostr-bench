"""Mode B — pinned minimal agent. OpenAI tool-calling loop, exactly four tools.

Deliberately ~one screen of logic so results measure the *model*, not someone
else's evolving scaffold. Tools: read_file, write_file, run (sandboxed shell,
can execute the VISIBLE test suite), done. Caps from runmatrix.yaml.

The agent works inside a temp copy of the task's starter/buggy repo. Grading then
overlays the HIDDEN suite on the agent's final tree — same grader as Mode A.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile

from grade import findings as findings_grade
from grade import extract, sandbox, vitest_runner
from providers import get_provider

from .common import Task, RunResult, context_blob

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file in the workspace.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run", "description": "Run a shell command in the workspace (e.g. npx vitest run tests_visible). No network.",
        "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "done", "description": "Signal the task is complete.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}}}},
]

SYSTEM_CODE = (
    "You are an autonomous TypeScript engineer working in a sandboxed repo. Use the "
    "tools to read files, write code, and run the VISIBLE tests (e.g. `npx vitest run "
    "tests_visible`) to check your work. There is a hidden test suite you cannot see — "
    "make the code correct and COMPLETE (implement every required file/function), not "
    "just green on visible tests. Only call done once the visible tests pass and the "
    "implementation is finished. No network access."
)
SYSTEM_AUDIT = (
    "You are an autonomous security auditor in a sandboxed repo. Use read_file/run to "
    "explore the code thoroughly. When finished, write your findings as a JSON array to "
    "the file findings.json (each item: {title, file, severity, description}) using "
    "write_file, then call done. Report only real, exploitable issues — false alarms "
    "are penalized. No network access."
)


def _safe_join(base: str, rel: str) -> str:
    p = os.path.realpath(os.path.join(base, rel.lstrip("/")))
    if not p.startswith(os.path.realpath(base)):
        raise ValueError("path escapes workspace")
    return p


def _dispatch(name: str, args: dict, work: str, caps: dict) -> str:
    try:
        if name == "read_file":
            path = args.get("path")
            if not path:
                return "ERROR: read_file requires a 'path' argument."
            try:
                return open(_safe_join(work, path)).read()[:20000]
            except OSError as e:
                return f"ERROR: {e}"
        if name == "write_file":
            path, content = args.get("path"), args.get("content")
            if not path or content is None:
                return "ERROR: write_file requires 'path' and 'content' arguments."
            dest = _safe_join(work, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "w").write(content)
            return f"wrote {path} ({len(content)} bytes)"
        if name == "run":
            cmd = args.get("cmd")
            if not cmd:
                return "ERROR: run requires a 'cmd' argument."
            if "tests_hidden" in cmd:                      # hidden suite is off-limits
                return "ERROR: tests_hidden is off-limits."
            out = sandbox.run(["sh", "-c", cmd], work, timeout=120)
            return f"[exit {out.returncode}]\n{(out.stdout + out.stderr)[-6000:]}"
        if name == "done":
            return "DONE"
        return f"ERROR: unknown tool {name}"
    except Exception as e:  # noqa: BLE001 — a bad tool call must not kill the run
        return f"ERROR: {type(e).__name__}: {e}"


def run_cell(model: str, task_id: str, tier: str, arm: str, rep: int, *,
             price: dict | None = None, max_turns: int = 25, wall_s: int = 300,
             dry_run: bool = False) -> RunResult:
    task = Task.load(task_id)
    rr = RunResult(task=task_id, mode="microagent", model=model, tier=tier, arm=arm, rep=rep)
    if dry_run:
        rr.detail = {"note": "dry run — no agent loop executed"}
        return rr

    max_turns = int(os.environ.get("NOSTR_BENCH_AGENT_TURNS", str(max_turns)))
    wall_s = int(os.environ.get("NOSTR_BENCH_AGENT_WALL", str(wall_s)))
    max_out = int(os.environ.get("NOSTR_BENCH_AGENT_MAXOUT", "8000"))
    reason_cap = int(os.environ.get("NOSTR_BENCH_AGENT_REASONING_CAP", "4000"))

    work = tempfile.mkdtemp(prefix="nbench_agent_")
    try:
        src = os.path.join(task.dir, task.starter_subdir)
        shutil.copytree(src, work, dirs_exist_ok=True)
        vis = os.path.join(task.dir, "tests_visible")
        if os.path.isdir(vis):
            shutil.copytree(vis, os.path.join(work, "tests_visible"), dirs_exist_ok=True)
        # Seed node_modules from the per-task cache so the agent's `run` tool can
        # execute vitest immediately (Mode B is about using tests as feedback).
        cache = os.path.join(task.dir, ".nmcache")
        if os.path.isdir(cache) and not os.path.isdir(os.path.join(work, "node_modules")):
            sandbox.run(["cp", "-al", cache, os.path.join(work, "node_modules")], work, timeout=60)

        provider = get_provider(arm, price=price)
        system = SYSTEM_AUDIT if task.kind == "audit" else SYSTEM_CODE
        user = task.prompts[tier] + "\n\nThe repository is already in your workspace. Start by exploring it."
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        import time as _time
        t_start = _time.time()
        pt = ct = 0
        cost = 0.0
        turns = 0
        parse_errors = 0
        for turns in range(1, max_turns + 1):
            if _time.time() - t_start > wall_s:
                break
            out = provider.chat(model, messages, tools=TOOLS, temperature=0.2,
                                max_tokens=max_out, reasoning={"max_tokens": reason_cap})
            pt += out.prompt_tokens
            ct += out.completion_tokens
            cost += out.cost_usd or 0.0
            messages.append({"role": "assistant", "content": out.text or None,
                             "tool_calls": out.tool_calls or None})
            if not out.tool_calls:
                break
            stop = False
            for tc in out.tool_calls:
                fn = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args, parse_errors = {}, parse_errors + 1
                result = _dispatch(fn, args, work, {})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                if fn == "done":
                    stop = True
            if stop:
                break

        # grade final tree with hidden suite
        produced = _tree_files(work, task.starter_subdir)
        if task.kind == "audit":
            # prefer findings.json the agent wrote; fall back to its last message
            parsed = None
            fpath = os.path.join(work, "findings.json")
            if os.path.exists(fpath):
                parsed = extract.extract_findings(open(fpath).read())
            if parsed is None:
                last = next((m["content"] for m in reversed(messages)
                             if m["role"] == "assistant" and m.get("content")), "")
                parsed = extract.extract_findings(last or "")
            res = findings_grade.score_findings(parsed, task.answer_key())
            rr.score, rr.detail, rr.format_ok = res["score"], res, parsed is not None
        else:
            res = vitest_runner.build_and_test(task.dir, produced, base_subdir=task.starter_subdir)
            rr.score = round(res["pass_rate"] * 100, 1)
            rr.detail = res
            rr.format_ok = parse_errors == 0
        rr.detail["parse_errors"] = parse_errors
        rr.prompt_tokens, rr.completion_tokens = pt, ct
        rr.cost_usd = cost or None
        rr.turns = turns
        return rr
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _tree_files(work: str, _base: str) -> dict[str, str]:
    out = {}
    for root, _, files in os.walk(work):
        # exclude node_modules, and both test dirs so grading uses ONLY the hidden
        # suite (consistent with one-shot: score is /hidden, not /hidden+visible)
        if "node_modules" in root or "tests_hidden" in root or "tests_visible" in root:
            continue
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, work)
            try:
                out[rel] = open(p).read()
            except (UnicodeDecodeError, OSError):
                pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--tier", default="T1", choices=["T1", "T2"])
    ap.add_argument("--arm", default="cloud", choices=["cloud", "local", "routstr"])
    ap.add_argument("--rep", type=int, default=0)
    a = ap.parse_args()
    rr = run_cell(a.model, a.task, a.tier, a.arm, a.rep)
    name = rr.save()
    print(f"{name}: score={rr.score} turns={rr.turns} tokens={rr.prompt_tokens}+{rr.completion_tokens} cost=${rr.cost_usd}")


if __name__ == "__main__":
    main()
