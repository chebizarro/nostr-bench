"""Assemble a task workspace, drop in the model's files, run hidden vitest suite.

Workflow per graded run:
  1. copy tasks/<task>/starter (or the buggy repo) to a temp .work dir
  2. overlay the model's produced files
  3. overlay tests_hidden/ (the model never saw these)
  4. npm ci / npm install (once, cached) then vitest run --reporter=json
  5. parse pass/fail counts -> score
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from . import sandbox


def _copytree(src: str, dst: str):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)


def build_and_test(task_dir: str, produced: dict[str, str], *, base_subdir: str = "starter",
                   timeout: int = 300) -> dict:
    """Return {passed, failed, total, pass_rate, log, per_test:{name:bool}}."""
    work = tempfile.mkdtemp(prefix="nbench_")
    try:
        _copytree(os.path.join(task_dir, base_subdir), work)
        # overlay model output
        for rel, content in produced.items():
            rel = rel.lstrip("/")
            dest = os.path.join(work, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                f.write(content)
        # overlay hidden tests
        _copytree(os.path.join(task_dir, "tests_hidden"), os.path.join(work, "tests_hidden"))

        # node_modules: reuse a per-task cache via hardlinks (fast); install once if absent.
        nm = os.path.join(work, "node_modules")
        cache = os.path.join(task_dir, ".nmcache")
        if not os.path.isdir(nm):
            if os.path.isdir(cache):
                # cp -al = hardlink tree, near-instant, no re-download
                sandbox.run(["cp", "-al", cache, nm], work, timeout=60)
            else:
                inst = sandbox.run(["npm", "install", "--no-audit", "--no-fund"], work, timeout=timeout)
                if inst.returncode != 0:
                    return {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0,
                            "log": "npm install failed:\n" + inst.stderr[-4000:], "per_test": {}}
                if os.path.isdir(nm):
                    sandbox.run(["cp", "-al", nm, cache], work, timeout=60)

        res = sandbox.run(
            ["npx", "vitest", "run", "--reporter=json", "--outputFile=vitest-out.json"],
            work, timeout=timeout,
        )
        out_path = os.path.join(work, "vitest-out.json")
        if not os.path.exists(out_path):
            return {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0,
                    "log": (res.stdout + res.stderr)[-4000:], "per_test": {}}
        with open(out_path) as f:
            data = json.load(f)
        per_test, passed, failed = {}, 0, 0
        for suite in data.get("testResults", []):
            for t in suite.get("assertionResults", []):
                ok = t.get("status") == "passed"
                per_test[t.get("fullName") or t.get("title", "?")] = ok
                passed += ok
                failed += (not ok)
        total = passed + failed
        return {"passed": passed, "failed": failed, "total": total,
                "pass_rate": (passed / total) if total else 0.0,
                "log": (res.stdout + res.stderr)[-2000:], "per_test": per_test}
    finally:
        shutil.rmtree(work, ignore_errors=True)
