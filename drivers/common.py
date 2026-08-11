"""Shared task loading, prompt assembly, and result recording for all drivers."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "tasks")
RUNS = os.path.join(ROOT, "runs")

# task.md carries both prompt tiers, delimited by HTML-comment markers:
#   <!-- T1 --> terse ... <!-- /T1 -->   <!-- T2 --> engineered ... <!-- /T2 -->
#   <!-- TARGET: src/nip01.ts -->        (primary file for unlabeled code blocks)
#   <!-- KIND: implement|debug|audit -->
_TIER_RE = {t: re.compile(rf"<!--\s*{t}\s*-->(.*?)<!--\s*/{t}\s*-->", re.DOTALL) for t in ("T1", "T2")}
_META_RE = re.compile(r"<!--\s*(TARGET|KIND):\s*([^\n>]+?)\s*-->")


@dataclass
class Task:
    id: str
    dir: str
    kind: str                     # implement | debug | audit
    target: str                   # primary output file for code tasks
    prompts: dict = field(default_factory=dict)   # {"T1":..., "T2":...}
    starter_subdir: str = "starter"

    @classmethod
    def load(cls, task_id: str) -> "Task":
        d = os.path.join(TASKS, task_id)
        md = open(os.path.join(d, "task.md")).read()
        meta = {k: v for k, v in _META_RE.findall(md)}
        prompts = {}
        for tier, rx in _TIER_RE.items():
            m = rx.search(md)
            if m:
                prompts[tier] = m.group(1).strip()
        kind = meta.get("KIND", "implement")
        starter = "starter" if os.path.isdir(os.path.join(d, "starter")) else "src"
        return cls(id=task_id, dir=d, kind=kind, target=meta.get("TARGET", "src/main.ts"),
                   prompts=prompts, starter_subdir=starter)

    def starter_context(self) -> dict[str, str]:
        """Files the model is allowed to see (starter or buggy repo, minus hidden tests)."""
        base = os.path.join(self.dir, self.starter_subdir)
        ctx = {}
        for root, _, files in os.walk(base):
            for fn in files:
                if "node_modules" in root:
                    continue
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, base)
                try:
                    ctx[rel] = open(p).read()
                except (UnicodeDecodeError, OSError):
                    pass
        # visible tests are fair game
        vis = os.path.join(self.dir, "tests_visible")
        if os.path.isdir(vis):
            for fn in os.listdir(vis):
                ctx[f"tests_visible/{fn}"] = open(os.path.join(vis, fn)).read()
        return ctx

    def answer_key(self) -> dict:
        p = os.path.join(self.dir, "answer_key.json")
        return json.load(open(p)) if os.path.exists(p) else {}


def context_blob(ctx: dict[str, str]) -> str:
    parts = []
    for rel, content in sorted(ctx.items()):
        lang = "ts" if rel.endswith((".ts", ".tsx")) else "json" if rel.endswith(".json") else ""
        parts.append(f"### `{rel}`\n```{lang}\n{content}\n```")
    return "\n\n".join(parts)


@dataclass
class RunResult:
    task: str
    mode: str
    model: str
    tier: str
    arm: str
    rep: int
    score: float = 0.0
    detail: dict = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Optional[float] = None
    wall_clock_s: float = 0.0
    turns: int = 1
    format_ok: bool = True
    error: Optional[str] = None
    ts: float = field(default_factory=time.time)

    def save(self):
        os.makedirs(RUNS, exist_ok=True)
        safe = re.sub(r"[^\w.-]", "_", f"{self.task}__{self.mode}__{self.model}__{self.tier}__{self.arm}__r{self.rep}")
        with open(os.path.join(RUNS, safe + ".json"), "w") as f:
            json.dump(asdict(self), f, indent=2)
        return safe
