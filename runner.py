"""Phase runner: expand runmatrix.yaml into cells and execute a phase.

    python -m runner --phase phase1_oneshot
    python -m runner --phase phase2_agent --arm cloud
    python -m runner --grade-tree <dir> --task n1_implement --mode repoprompt --model glm-oss --tier T1

Cells are skipped if a result JSON already exists (resumable). Failures are
recorded, not fatal — one dead model shouldn't sink a phase.
"""
from __future__ import annotations

import argparse
import os
import statistics
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

from drivers import oneshot, microagent
from drivers.common import RUNS, RunResult

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = yaml.safe_load(open(os.path.join(ROOT, "runmatrix.yaml")))


def _already(task, mode, model, tier, arm, rep) -> bool:
    import re
    safe = re.sub(r"[^\w.-]", "_", f"{task}__{mode}__{model}__{tier}__{arm}__r{rep}")
    return os.path.exists(os.path.join(RUNS, safe + ".json"))


def _phase1_scores(model_id: str) -> float:
    """Mean one-shot score for a model, for phase-2 gating."""
    import glob, json, re
    scores = []
    pat = re.sub(r"[^\w.-]", "_", model_id)
    for p in glob.glob(os.path.join(RUNS, f"*__oneshot__{pat}__*.json")):
        try:
            scores.append(json.load(open(p)).get("score", 0.0))
        except (OSError, ValueError):
            pass
    return statistics.mean(scores) if scores else 0.0


def run_phase(phase: str, only_arm: str | None = None, *, reps: int | None = None,
              only_models: list[str] | None = None, only_tasks: list[str] | None = None,
              only_tiers: list[str] | None = None, workers: int | None = None):
    pcfg = CFG["phases"][phase]
    modes = pcfg["modes"]
    tasks = only_tasks or CFG["tasks"]
    tiers = only_tiers or CFG["tiers"]
    reps = reps if reps is not None else CFG["defaults"]["reps"]
    workers = workers or int(os.environ.get("NOSTR_BENCH_WORKERS", "6"))

    # Build the full cell list up front, then execute with a bounded thread pool.
    cells = []
    for model in CFG["models"]:
        mid = model["id"]
        if only_models and mid not in only_models:
            continue
        arms = [a for a in model["arms"] if (only_arm is None or a == only_arm)]
        if phase == "phase2_agent":
            local_ok = model.get("local_min_vram_gb", 999) <= 24
            if not (local_ok or _phase1_scores(mid) >= 40):
                print(f"skip {mid}: did not advance to phase2", flush=True)
                continue
        for mode in modes:
            if mode not in ("oneshot", "microagent"):
                print("[phase3/repoprompt: use the manual runbook — see drivers/repoprompt.py]", flush=True)
                continue
            for arm in arms:
                for task in tasks:
                    for tier in tiers:
                        for rep in range(reps):
                            if _already(task, mode, mid, tier, arm, rep):
                                continue
                            cells.append((model, mode, arm, task, tier, rep))

    print(f"{len(cells)} cells to run, {workers} workers", flush=True)

    def _do(cell):
        model, mode, arm, task, tier, rep = cell
        mid = model["id"]
        driver = {"oneshot": oneshot, "microagent": microagent}[mode]
        try:
            rr = driver.run_cell(mid, task, tier, arm, rep, price=model.get("price"))
        except Exception as e:  # noqa: BLE001
            rr = RunResult(task=task, mode=mode, model=mid, tier=tier, arm=arm, rep=rep,
                           error=f"{e}\n{traceback.format_exc()[-1200:]}")
        name = rr.save()
        return f"{name}: {rr.score}{' ERR' if rr.error else ''}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_do, c): c for c in cells}
        done = 0
        for fut in as_completed(futs):
            done += 1
            print(f"[{done}/{len(cells)}] {fut.result()}", flush=True)


def grade_tree(tree_dir: str, task: str, mode: str, model: str, tier: str, arm: str):
    """Grade an externally-produced tree (Mode C output) with the shared grader."""
    import json
    from drivers.common import Task
    from grade import vitest_runner, findings as fg, extract
    t = Task.load(task)
    produced = {}
    for root, _, files in os.walk(tree_dir):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), tree_dir)
            produced[rel] = open(os.path.join(root, fn)).read()
    rr = RunResult(task=task, mode=mode, model=model, tier=tier, arm=arm, rep=0)
    if t.kind == "audit":
        findings = extract.extract_findings(produced.get("findings.json", "[]"))
        res = fg.score_findings(findings, t.answer_key())
        rr.score, rr.detail = res["score"], res
    else:
        res = vitest_runner.build_and_test(t.dir, produced, base_subdir=t.starter_subdir)
        rr.score, rr.detail = round(res["pass_rate"] * 100, 1), res
    print(rr.save(), rr.score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase")
    ap.add_argument("--arm", default=None)
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--models", default=None, help="comma-separated model id subset")
    ap.add_argument("--tasks", default=None, help="comma-separated task subset")
    ap.add_argument("--tiers", default=None, help="comma-separated tier subset")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--grade-tree")
    ap.add_argument("--task")
    ap.add_argument("--mode", default="repoprompt")
    ap.add_argument("--model")
    ap.add_argument("--tier", default="T1")
    a = ap.parse_args()
    if a.grade_tree:
        grade_tree(a.grade_tree, a.task, a.mode, a.model, a.tier, a.arm or "cloud")
    elif a.phase:
        run_phase(a.phase, a.arm, reps=a.reps, workers=a.workers,
                  only_models=a.models.split(",") if a.models else None,
                  only_tasks=a.tasks.split(",") if a.tasks else None,
                  only_tiers=a.tiers.split(",") if a.tiers else None)
    else:
        ap.error("need --phase or --grade-tree")


if __name__ == "__main__":
    main()
