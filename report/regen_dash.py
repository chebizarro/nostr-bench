"""Recompute report/dash.json from all one-shot runs (n reps aware).

Emits per-model: mean accuracy, per-task means, nostr/security splits, T1/T2,
prompt sensitivity, summed cost, rep count, and min/max range for the accuracy
spread so the dashboard can show error bars.
"""
import json, glob, os, statistics as st
import yaml

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
cfg = yaml.safe_load(open(os.path.join(ROOT, "runmatrix.yaml")))
meta = {m["id"]: m for m in cfg["models"]}
NOSTR = {"n1_implement", "n2_debug", "s2_nostr_sec"}; SEC = {"s1_audit", "s2_nostr_sec"}
TASKS = ["n1_implement", "n2_debug", "s1_audit", "s2_nostr_sec"]

rows = [json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "runs", "*oneshot*.json"))]
by = {}
for r in rows:
    by.setdefault(r["model"], []).append(r)

def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 1) if xs else None

out = []
for m, rs in by.items():
    ok = [r for r in rs if not r.get("error")]
    if m not in meta:
        continue
    accs = [r["score"] for r in ok]
    cell = {
        "model": m,
        "tier_local": meta[m].get("local_min_vram_gb", 999) <= 24,
        "local_any": "local" in meta[m]["arms"],
        "vram": meta[m].get("local_min_vram_gb"),
        "acc": mean(accs),
        "acc_min": round(min(accs), 1) if accs else None,
        "acc_max": round(max(accs), 1) if accs else None,
        "nostr": mean([r["score"] for r in ok if r["task"] in NOSTR]),
        "sec": mean([r["score"] for r in ok if r["task"] in SEC]),
        "t1": mean([r["score"] for r in ok if r["tier"] == "T1"]),
        "t2": mean([r["score"] for r in ok if r["tier"] == "T2"]),
        "cost": round(sum((r.get("cost_usd") or 0) for r in rs), 4),
        "n": len(ok),
        "reps": len({r.get("rep") for r in ok}),
        "missing": len(rs) - len(ok),
    }
    for t in TASKS:
        cell[t] = mean([r["score"] for r in ok if r["task"] == t])
    cell["sens"] = round(cell["t2"] - cell["t1"], 1) if (cell["t1"] is not None and cell["t2"] is not None) else None
    per_run = cell["cost"] / cell["n"] if cell["n"] else None
    cell["pts_per_dollar"] = round(cell["acc"] / per_run, 0) if (per_run and per_run > 0 and cell["acc"]) else None
    out.append(cell)

out.sort(key=lambda c: -(c["acc"] or 0))
total_reps = max((c["reps"] for c in out), default=1)
json.dump({"cells": out, "meta": {"total_cost": round(sum(c["cost"] for c in out), 3),
                                  "n_runs": len(rows), "reps": total_reps, "date": "2026-08-11"}},
          open(os.path.join(HERE, "dash.json"), "w"), indent=1)
print(f"dash.json: {len(out)} models, up to n={total_reps} reps, {len(rows)} one-shot runs")
for c in out:
    print(f"  {c['model'].split('/')[-1]:32} acc={c['acc']} [{c['acc_min']}-{c['acc_max']}] "
          f"nostr={c['nostr']} sec={c['sec']} n={c['n']} reps={c['reps']}")
