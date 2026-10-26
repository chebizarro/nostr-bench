#!/usr/bin/env python3
"""Offline, non-generative finding-filter experiment. No API calls or key access.

Example (raw inputs/output must stay outside git):
  python suites/drydock/finding_filter.py --dataset /path/to/drydock-planted-v1.json \
    --judges '/path/to/runs/*.judge-claude-opus-5.5.jsonl' --out /path/to/runs/filter.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import glob
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEED = 1337
LABELS = {"real_issue", "minor_valid", "false_positive", "hallucinated"}
HEDGES = ("may", "might", "could", "potentially", "ensure")
EXTERNAL = re.compile(
    r"\b(?:library|libraries|protocol|specification|standard|RFC\s*\d+|NIP[- ]?\d+|"
    r"nostr|websocket|TLS|HTTP|SDK|API|npm|react|axios|sqlite|postgres|openssl|"
    r"serde|tokio|reqwest|nostr-tools|go-nostr)\b", re.I,
)
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
QUOTES = re.compile(r"`([^`\n]+)`|\"([^\"\n]+)\"|'([^'\n]+)'")


def normalize(text: str) -> str:
    return " ".join(text.split())


def diff_lines(patch: str) -> dict:
    """New-side hunk ranges and added/replacement lines, keyed by exact path."""
    files: dict = {}
    current = None
    line_number = None
    remaining = 0
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            current, line_number, remaining = None, None, 0
        elif line.startswith("+++ ") and remaining == 0:
            path = line[4:].split("\t", 1)[0]
            current = path[2:] if path.startswith("b/") else path
            files.setdefault(current, {"hunks": [], "added": {}})
        elif match := HUNK.match(line):
            if current is None:
                raise ValueError("hunk without new-side file header")
            line_number = int(match[1])
            remaining = int(match[2]) if match[2] is not None else 1
            files[current]["hunks"].append((line_number, line_number + remaining))
        elif current is not None and line_number is not None:
            if line.startswith("+"):
                files[current]["added"][line_number] = line[1:]
                line_number += 1
                remaining -= 1
            elif line.startswith(" "):
                line_number += 1
                remaining -= 1
            elif not line.startswith(("-", "\\")):
                line_number = None
    return files


def quoted_in_added(text: str, added: list[str]) -> bool:
    spans = [normalize(next(s for s in match.groups() if s is not None))
             for match in QUOTES.finditer(text)]
    return any(len(span) >= 8 and any(span in line for line in added) for span in spans)


def features(finding: dict, patch: str, position: int, count: int) -> dict:
    """Only production-visible fields: no IDs, model identity, labels or planted metadata."""
    evidence = str(finding.get("evidence") or "")
    explanation = str(finding.get("explanation") or "")
    path = str(finding.get("file") or "").removeprefix("./")
    parsed = diff_lines(patch)
    info = parsed.get(path, {"hunks": [], "added": {}})
    added = [normalize(line) for line in info["added"].values() if len(normalize(line)) >= 8]
    normalized_evidence = normalize(evidence)
    line = finding.get("line")
    line = line if isinstance(line, int) and not isinstance(line, bool) else -1
    confidence = finding.get("confidence")
    confidence_missing = confidence is None
    confidence = float(confidence) if confidence is not None else 0.0
    if not np.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError(f"invalid confidence: {confidence}")
    out = {
        "evidence_matches_added": float(len(normalized_evidence) >= 8 and any(
            normalized_evidence in added_line or added_line in normalized_evidence for added_line in added)),
        "evidence_quote_in_added": float(quoted_in_added(evidence, added)),
        "explanation_quote_in_added": float(quoted_in_added(explanation, added)),
        "file_in_diff": float(path in parsed),
        "line_in_hunk": float(any(start <= line < end for start, end in info["hunks"])),
        "line_is_added": float(line in info["added"]),
        "category": str(finding.get("category") or "unknown"),
        "severity": str(finding.get("severity") or "unknown"),
        "confidence": confidence,
        "confidence_missing": float(confidence_missing),
        "explanation_chars": len(explanation),
        "explanation_words": len(explanation.split()),
        "external_claim_terms": len(EXTERNAL.findall(explanation + " " + evidence)),
        "finding_count": count,
        "position": position,
        "relative_position": position / max(count - 1, 1),
    }
    for term in HEDGES:
        out[f"hedge_{term}"] = len(re.findall(rf"\b{term}\b", explanation, re.I))
    out["hedge_total"] = sum(out[f"hedge_{term}"] for term in HEDGES)
    return out


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_data(dataset: Path, judge_paths: list[Path]) -> tuple[list[dict], list[dict], list[dict]]:
    data = json.loads(dataset.read_text())
    cases = {case["case_id"]: case for case in data["cases"]}
    manifest = {str(dataset): sha256(dataset)}
    rows, reviews, seen = [], [], set()
    for judge_path in judge_paths:
        result_path = Path(str(judge_path).split(".judge-", 1)[0])
        result_records = records(result_path)
        headers = [r for r in result_records if r.get("type") == "header"]
        if len(headers) != 1 or headers[0].get("dataset_sha256") != sha256(dataset):
            raise ValueError(f"missing header or dataset hash mismatch: {result_path}")
        config = headers[0]["label"]
        results = {r["case_id"]: r for r in result_records if r.get("type") == "case"}
        manifest.update({str(p): sha256(p) for p in (judge_path, result_path)})
        for judged in records(judge_path):
            if judged.get("type") != "case":
                continue
            cid = judged["case_id"]
            case, result = cases[cid], results[cid]
            identity = (config, result_path.name.split("#", 1)[-1].split(".", 1)[0], cid)
            if identity in seen:
                raise ValueError(f"duplicate labelled review: {identity}")
            seen.add(identity)
            if not result.get("ok"):
                raise ValueError(f"labelled failed review: {identity}")
            findings, verdicts = result.get("findings", []), judged["judge"]["verdicts"]
            indices = [v["index"] for v in verdicts]
            if sorted(indices) != list(range(len(findings))) or judged["n_findings"] != len(findings):
                raise ValueError(f"non-bijective verdict indices: {identity}")
            rid = len(reviews)
            meta = case["bench_meta"]
            review = {"review_id": rid, "case_id": cid, "group": meta["source_event_id"],
                      "config": config, "planted": meta["kind"] == "planted"}
            if judged["kind"] != meta["kind"]:
                raise ValueError(f"kind mismatch: {identity}")
            reviews.append(review)
            for verdict in sorted(verdicts, key=lambda v: v["index"]):
                if verdict["label"] not in LABELS:
                    raise ValueError(f"unknown label: {verdict['label']}")
                i = verdict["index"]
                rows.append({**review, "index": i, "label": verdict["label"],
                             "matches_injected": verdict.get("matches_injected") is True,
                             "correct_injected": review["planted"] and verdict.get("matches_injected") is True
                             and verdict.get("explanation_correct") is True
                             and verdict["label"] in {"real_issue", "minor_valid"},
                             "features": features(findings[i], case["patch_diff"], i, len(findings))})
    return rows, reviews, [{"path": path, "sha256": digest} for path, digest in sorted(manifest.items())]


def pipeline(name: str):
    if name == "logistic":
        model = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)
    elif name == "tree":
        model = GradientBoostingClassifier(n_estimators=60, max_depth=2, min_samples_leaf=10,
                                           learning_rate=0.05, random_state=SEED)
    else:
        raise ValueError(name)
    return make_pipeline(DictVectorizer(sparse=False), StandardScaler(), model)


def predict(name: str, train: np.ndarray, test: np.ndarray, x: list[dict], y: np.ndarray) -> np.ndarray:
    if name == "confidence":
        return np.array([x[i]["confidence"] for i in test])
    model = pipeline(name)
    if len(np.unique(y[train])) < 2:
        model.steps[-1] = ("dummy", DummyClassifier(strategy="constant", constant=int(y[train][0])))
    model.fit([x[i] for i in train], y[train])
    probabilities = model.predict_proba([x[i] for i in test])
    classes = model.classes_.tolist()
    return probabilities[:, classes.index(1)] if 1 in classes else np.zeros(len(test))


def splits(indices: np.ndarray, groups: np.ndarray):
    n = min(5, len(set(groups[indices])))
    if n < 2:
        raise ValueError("need at least two source-patch groups")
    cv = GroupKFold(n_splits=n, shuffle=True, random_state=SEED)
    return [(indices[train], indices[test]) for train, test in cv.split(indices, groups=groups[indices])]


def tune_threshold(scores: np.ndarray, indices: np.ndarray, rows: list[dict], reviews: list[dict],
                   y: np.ndarray, loss: float) -> float:
    train_groups = {rows[i]["group"] for i in indices}
    train_configs = {rows[i]["config"] for i in indices}
    denominator = sum(r["planted"] for r in reviews
                      if r["group"] in train_groups and r["config"] in train_configs)
    # Include zero-finding training reviews in the absolute planted-recall denominator.
    correct = {rows[i]["review_id"] for i in indices if rows[i]["correct_injected"]}
    best = (-1.0, -1, -1.0)
    threshold = 0.0
    train_scores = scores[indices]
    for candidate in np.unique(np.r_[0.0, train_scores]):
        keep = train_scores >= candidate
        retained = {rows[i]["review_id"] for i, accepted in zip(indices, keep)
                    if accepted and rows[i]["correct_injected"]}
        if len(correct - retained) > loss * denominator + 1e-9:
            continue
        precision = float(y[indices][keep].mean()) if keep.any() else 0.0
        # Prefer more true positives, then the lower threshold, on a precision tie.
        rank = (precision, int(y[indices][keep].sum()), -float(candidate))
        if rank > best:
            best, threshold = rank, float(candidate)
    return threshold


def metrics(rows: list[dict], reviews: list[dict], y: np.ndarray, keep: np.ndarray) -> dict:
    total_planted = sum(r["planted"] for r in reviews)
    correct = {r["review_id"] for r in rows if r["correct_injected"]}
    retained = {r["review_id"] for r, accepted in zip(rows, keep) if accepted and r["correct_injected"]}
    matching = {r["review_id"] for r in rows if r["planted"] and r["matches_injected"]}
    matching_kept = {r["review_id"] for r, accepted in zip(rows, keep)
                     if accepted and r["planted"] and r["matches_injected"]}
    tp, kept = int(y[keep].sum()), int(keep.sum())
    return {"kept": kept, "tp": tp, "precision": tp / kept if kept else 0.0,
            "recall": tp / int(y.sum()) if y.sum() else 0.0,
            "planted_total": total_planted, "correct_planted_before": len(correct),
            "correct_planted_kept": len(retained), "correct_planted_dropped": len(correct - retained),
            "planted_recall": len(retained) / total_planted if total_planted else 0.0,
            "planted_loss_pp": 100 * len(correct - retained) / total_planted if total_planted else 0.0,
            "matching_planted_before": len(matching), "matching_planted_kept": len(matching_kept)}


def paired_intervals(rows: list[dict], reviews: list[dict], y: np.ndarray,
                     keep: np.ndarray, baseline: np.ndarray) -> dict:
    """Source-patch cluster bootstrap of paired, already-held-out decisions (not refits)."""
    groups = sorted({r["group"] for r in reviews})
    counts = []
    for group in groups:
        mask = np.array([r["group"] == group for r in rows])
        group_reviews = [r for r in reviews if r["group"] == group]
        planted = sum(r["planted"] for r in group_reviews)
        caught = []
        for selection in (keep, baseline):
            caught.append(len({r["review_id"] for r, accepted in zip(rows, selection)
                               if accepted and r["group"] == group and r["correct_injected"]}))
        counts.append([int(y[mask & keep].sum()), int((mask & keep).sum()),
                       int(y[mask & baseline].sum()), int((mask & baseline).sum()),
                       caught[0], caught[1], planted])
    values = np.array(counts)
    rng = np.random.default_rng(SEED)
    sums = values[rng.integers(0, len(groups), size=(2000, len(groups)))].sum(axis=1)
    gain = sums[:, 0] / np.maximum(sums[:, 1], 1) - sums[:, 2] / np.maximum(sums[:, 3], 1)
    recall_delta = (sums[:, 4] - sums[:, 5]) / np.maximum(sums[:, 6], 1)
    return {"precision_gain_pp_95ci": (100 * np.quantile(gain, [0.025, 0.975])).tolist(),
            "planted_recall_delta_pp_95ci": (100 * np.quantile(recall_delta, [0.025, 0.975])).tolist()}


def evaluate(rows: list[dict], reviews: list[dict], target: str, mode: str) -> dict:
    x = [r["features"] for r in rows]
    positives = {"real_issue"} if target == "real_only" else {"real_issue", "minor_valid"}
    y = np.array([int(r["label"] in positives) for r in rows])
    groups = np.array([r["group"] for r in rows])
    configs = np.array([r["config"] for r in rows])
    indices = np.arange(len(rows))
    outer = splits(indices, groups)
    if mode == "source_and_config":
        outer = [(train[configs[train] != config], test[configs[test] == config])
                 for train, test in outer for config in sorted(set(configs)) if np.any(configs[test] == config)]
    output = {"target": target, "cv": mode, "operating_points": [], "predictions": {}}
    decisions = {}
    for name in ("confidence", "logistic", "tree"):
        scores = np.full(len(rows), np.nan)
        masks = {loss: np.zeros(len(rows), dtype=bool) for loss in (0.0, 0.05, 0.10)}
        thresholds = {loss: [] for loss in masks}
        tested = np.zeros(len(rows), dtype=int)
        for train, test in outer:
            assert not set(groups[train]) & set(groups[test])
            if mode == "source_and_config":
                assert not set(configs[train]) & set(configs[test])
            scores[test] = predict(name, train, test, x, y)
            tested[test] += 1
            inner_scores = np.full(len(rows), np.nan)
            for inner_train, inner_test in splits(train, groups):
                inner_scores[inner_test] = predict(name, inner_train, inner_test, x, y)
            for loss in masks:
                threshold = tune_threshold(inner_scores, train, rows, reviews, y, loss)
                masks[loss][test] = scores[test] >= threshold
                thresholds[loss].append(threshold)
        assert np.all(tested == 1) and np.isfinite(scores).all()
        output["predictions"][name] = scores.tolist()
        # Report the complete confidence curve, not a cherry-picked baseline threshold.
        fixed_thresholds = np.unique(np.r_[0.0, scores]) if name == "confidence" else (0.3, 0.5, 0.7)
        for threshold in fixed_thresholds:
            output["operating_points"].append({"model": name, "policy": f"fixed>={threshold:g}",
                **metrics(rows, reviews, y, scores >= threshold)})
        for loss, keep in masks.items():
            policy = f"inner_loss<={100 * loss:g}pp"
            decisions[(name, policy)] = keep
            output["operating_points"].append({"model": name, "policy": policy,
                "threshold_min": min(thresholds[loss]), "threshold_max": max(thresholds[loss]),
                **metrics(rows, reviews, y, keep)})
    for point in output["operating_points"]:
        policy = point["policy"]
        if point["model"] != "confidence" and policy.startswith("inner_"):
            baseline = decisions[("confidence", policy)]
            point.update(paired_intervals(rows, reviews, y, decisions[(point["model"], policy)], baseline))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--judges", required=True, nargs="+", help="Paths or quoted glob patterns")
    parser.add_argument("--out", required=True, type=Path, help="JSON artifact; keep under gitignored runs/")
    args = parser.parse_args()
    paths = sorted({Path(p) for pattern in args.judges for p in glob.glob(pattern)})
    if not paths:
        parser.error("no judge files matched")
    rows, reviews, manifest = load_data(args.dataset, paths)
    result = {"seed": SEED, "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__},
              "manifest": manifest, "n_findings": len(rows), "n_reviews": len(reviews),
              "n_cases": len({r["case_id"] for r in reviews}),
              "n_source_groups": len({r["group"] for r in reviews}),
              "labels": dict(Counter(r["label"] for r in rows)),
              "configs": dict(Counter(r["config"] for r in reviews)),
              "rows": [{k: v for k, v in r.items() if k != "features"} for r in rows],
              "evaluations": []}
    for mode in ("source", "source_and_config"):
        for target in ("real_only", "real_plus_minor"):
            evaluation = evaluate(rows, reviews, target, mode)
            result["evaluations"].append(evaluation)
            print(f"\n{mode} / {target}")
            print("model       policy                kept precision recall planted dropped loss_pp")
            for point in evaluation["operating_points"]:
                print(f"{point['model']:11} {point['policy']:21} {point['kept']:4d} "
                      f"{point['precision']:9.3f} {point['recall']:6.3f} "
                      f"{point['correct_planted_kept']:3d}/{point['planted_total']:<3d} "
                      f"{point['correct_planted_dropped']:7d} {point['planted_loss_pp']:7.2f}")
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
