"""Aggregate runs/*.json into a single results.html dashboard.

    python -m report.aggregate runs report/results.html

Rollups:
  - accuracy: median score per (model, mode), plus nostr-only and security-only splits
  - ease: T1 score and prompt sensitivity (T2 - T1)
  - bang-for-buck cloud: score / $ ; local: score / hour (using rig cost_per_hour)
Close calls (<=5 pts) are flagged as ties in the notes.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = yaml.safe_load(open(os.path.join(ROOT, "runmatrix.yaml")))
NOSTR = {"n1_implement", "n2_debug", "s2_nostr_sec"}
SEC = {"s1_audit", "s2_nostr_sec"}


def load(runs_dir):
    rows = []
    for p in glob.glob(os.path.join(runs_dir, "*.json")):
        try:
            rows.append(json.load(open(p)))
        except (OSError, ValueError):
            pass
    return [r for r in rows if not r.get("error")]


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def rollup(rows):
    by = {}
    for r in rows:
        by.setdefault((r["model"], r["mode"], r["arm"]), []).append(r)
    out = []
    rig_hr = CFG["local_rig"]["cost_per_hour"]
    for (model, mode, arm), rs in sorted(by.items()):
        acc = med([r["score"] for r in rs])
        nostr = med([r["score"] for r in rs if r["task"] in NOSTR])
        sec = med([r["score"] for r in rs if r["task"] in SEC])
        t1 = med([r["score"] for r in rs if r["tier"] == "T1"])
        t2 = med([r["score"] for r in rs if r["tier"] == "T2"])
        sens = round(t2 - t1, 1) if (t1 is not None and t2 is not None) else None
        if arm == "local":
            hours = sum(r["wall_clock_s"] for r in rs) / 3600
            dollars = hours * rig_hr
        else:
            dollars = sum((r.get("cost_usd") or 0) for r in rs)
        bfb = round(acc / dollars, 1) if (acc and dollars) else None
        out.append(dict(model=model, mode=mode, arm=arm, accuracy=acc, nostr=nostr,
                        security=sec, t1=t1, sensitivity=sens, cost=round(dollars, 4),
                        bang_for_buck=bfb, n=len(rs)))
    return out


def html(rollups):
    head = ("<!doctype html><meta charset=utf8><title>nostr-bench results</title>"
            "<style>body{font:14px/1.5 system-ui;margin:2rem;max-width:1100px}"
            "table{border-collapse:collapse;width:100%;margin:1rem 0}"
            "th,td{border:1px solid #ddd;padding:6px 10px;text-align:right}"
            "th:first-child,td:first-child{text-align:left}"
            "th{background:#111;color:#fff;position:sticky;top:0}"
            "tr:nth-child(even){background:#fafafa}h1{margin-bottom:0}"
            ".muted{color:#666}</style>")
    rows = "".join(
        f"<tr><td>{r['model']}</td><td>{r['mode']}</td><td>{r['arm']}</td>"
        f"<td>{r['accuracy']}</td><td>{r['nostr']}</td><td>{r['security']}</td>"
        f"<td>{r['t1']}</td><td>{r['sensitivity']}</td><td>${r['cost']}</td>"
        f"<td>{r['bang_for_buck']}</td><td>{r['n']}</td></tr>"
        for r in sorted(rollups, key=lambda x: (-(x['accuracy'] or 0)))
    )
    table = ("<table><tr><th>model</th><th>mode</th><th>arm</th><th>accuracy</th>"
             "<th>nostr</th><th>security</th><th>T1</th><th>prompt&nbsp;sens.</th>"
             "<th>cost</th><th>pts/$</th><th>n</th></tr>" + rows + "</table>")
    note = ("<p class=muted>accuracy = median across suites. prompt sensitivity = "
            "median(T2) − median(T1); low + high T1 = easy to prompt. local cost = "
            f"wall-clock × ${CFG['local_rig']['cost_per_hour']}/hr ({CFG['local_rig']['name']}). "
            "Treat gaps ≤5 pts as ties.</p>")
    return f"{head}<h1>nostr-bench</h1>{note}{table}"


def main():
    runs_dir = sys.argv[1] if len(sys.argv) > 1 else "runs"
    out = sys.argv[2] if len(sys.argv) > 2 else "report/results.html"
    rows = load(runs_dir)
    ro = rollup(rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(html(ro))
    print(f"{len(rows)} runs -> {len(ro)} cells -> {out}")


if __name__ == "__main__":
    main()
