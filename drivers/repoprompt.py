"""Mode C — multi-model orchestration via Repo Prompt CE (macOS, over MCP).

This is the least automatable arm: Repo Prompt CE is a native macOS app driven
through its bundled MCP server. This module is a SCRIPTED SKELETON of the flow —
it documents the exact MCP call sequence and provides a pluggable `MCPClient`
port so it can be driven either from this Python harness (if you bridge to the
MCP server) or transcribed into the Cowork/Claude MCP session that already has
the RepoPromptCE tools loaded.

Two sub-configs (see runmatrix.yaml -> repoprompt_pairings):
  C1  oracle/editor pairing: strong model plans (oracle_send), cheap model edits (apply_edits)
  C2  context-engineered single model: same model as Mode B, but context_builder curates first

Call sequence per run (tool names are the RepoPromptCE MCP tools):
  1. manage_workspaces(open, path=<temp copy of task repo>)
  2. manage_worktree(create)                         # isolate this run
  3. context_builder(goal=<task prompt>, token_budget=...)   # curate context
  4a C1: oracle_send(model=<oracle>, prompt=<plan request + context>)  -> plan/spec
      -> apply_edits(model=<editor>, spec=<plan>)               # cheap editor writes code
  4b C2: agent_run(model=<model>, goal=<task prompt>)          # single model, curated ctx
  5. git(diff) / read_file to capture the produced tree
  6. copy tree out, grade with the SAME hidden-suite grader as Modes A/B
  7. manage_worktree(remove)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .common import Task, RunResult


class MCPClient(Protocol):
    """Port over the RepoPromptCE MCP tools. Implement against whichever transport
    you have (direct MCP bridge, or hand-run inside the Claude MCP session)."""
    def manage_workspaces(self, action: str, **kw) -> dict: ...
    def manage_worktree(self, action: str, **kw) -> dict: ...
    def context_builder(self, goal: str, token_budget: int) -> dict: ...
    def oracle_send(self, model: str, prompt: str) -> dict: ...
    def apply_edits(self, model: str, spec: str) -> dict: ...
    def agent_run(self, model: str, goal: str) -> dict: ...
    def git(self, action: str, **kw) -> dict: ...
    def read_tree(self) -> dict[str, str]: ...


@dataclass
class Pairing:
    name: str
    oracle: str
    editor: str


def run_pairing_c1(mcp: MCPClient, task: Task, tier: str, pairing: Pairing, *,
                   token_budget: int = 48000) -> dict[str, str]:
    """Execute the C1 oracle/editor flow and return the produced file tree."""
    mcp.manage_worktree("create")
    ctx = mcp.context_builder(goal=task.prompts[tier], token_budget=token_budget)
    plan = mcp.oracle_send(
        model=pairing.oracle,
        prompt=(f"{task.prompts[tier]}\n\nUsing the curated context, produce a precise "
                f"edit plan: which files to change and exactly what each change is. "
                f"Do not write final code, write an unambiguous spec."),
    )
    mcp.apply_edits(model=pairing.editor, spec=plan.get("text", ""))
    tree = mcp.read_tree()
    mcp.manage_worktree("remove")
    return tree


def run_pairing_c2(mcp: MCPClient, task: Task, tier: str, model: str, *,
                   token_budget: int = 48000) -> dict[str, str]:
    """C2 control: one model, but with Repo Prompt's curated context."""
    mcp.manage_worktree("create")
    mcp.context_builder(goal=task.prompts[tier], token_budget=token_budget)
    mcp.agent_run(model=model, goal=task.prompts[tier])
    tree = mcp.read_tree()
    mcp.manage_worktree("remove")
    return tree


# Grading reuses grade.vitest_runner / grade.findings on the returned tree exactly
# as Modes A and B do; see runner.py for how a produced tree becomes a RunResult.

RUNBOOK = """\
MANUAL RUNBOOK (first runs, until the MCP bridge is scripted)
------------------------------------------------------------
For each (task, pairing, tier):
  1. Copy tasks/<task>/<starter|src> to a scratch git repo; git init && commit.
  2. In Repo Prompt CE: open it as a workspace, create a worktree.
  3. Run Context Builder with the task's T1/T2 prompt as the goal.
  4. C1:  oracle_send with the ORACLE model -> save the returned plan.
          apply_edits with the EDITOR model against that plan.
     C2:  agent_run with the single model.
  5. Copy the resulting src/ back into tasks/<task>/ layout and run:
        python -m runner --grade-tree <dir> --task <task> --mode repoprompt \\
               --model <pairing-or-model> --tier <tier>
  6. Record oracle+editor token usage from Repo Prompt's session view into the
     run JSON's cost field (Phase 3 cost is oracle-dominated).
"""

if __name__ == "__main__":
    print(RUNBOOK)
