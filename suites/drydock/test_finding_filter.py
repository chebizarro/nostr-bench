"""Deterministic, offline checks; no private benchmark fixtures required."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import finding_filter as ff

PATCH = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -10,2 +10,3 @@
 context_line()
-old_call()
+new_call(value)
+other_call()
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1 @@
-old_second()
+new_second()
"""


class FindingFilterTests(unittest.TestCase):
    def test_new_side_hunks_added_lines_and_file_boundaries(self):
        parsed = ff.diff_lines(PATCH)
        self.assertEqual(parsed["a.py"]["hunks"], [(10, 13)])
        self.assertEqual(parsed["a.py"]["added"], {11: "new_call(value)", 12: "other_call()"})
        self.assertEqual(parsed["b.py"]["added"], {1: "new_second()"})
        deleted = ff.diff_lines("--- a/gone\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n")
        self.assertEqual(deleted["/dev/null"]["hunks"], [(0, 0)])

    def test_features_are_local_to_file_and_changed_lines(self):
        finding = {"file": "a.py", "line": 11, "confidence": 0.95,
                   "evidence": "`new_call(value)`", "explanation": "It might violate RFC 1234; ensure safety."}
        features = ff.features(finding, PATCH, 1, 3)
        for key in ("evidence_matches_added", "evidence_quote_in_added", "line_in_hunk", "line_is_added"):
            self.assertEqual(features[key], 1)
        self.assertEqual(features["hedge_total"], 2)
        self.assertEqual(features["external_claim_terms"], 1)
        self.assertEqual(features["relative_position"], 0.5)
        finding["evidence"] = "`old_call()`"
        self.assertEqual(ff.features(finding, PATCH, 0, 1)["evidence_quote_in_added"], 0)
        finding["evidence"] = "`new_second()`"
        self.assertEqual(ff.features(finding, PATCH, 0, 1)["evidence_quote_in_added"], 0)
        finding["line"] = 13
        self.assertEqual(ff.features(finding, PATCH, 0, 1)["line_in_hunk"], 0)
        finding["line"] = 10
        values = ff.features(finding, PATCH, 0, 1)
        self.assertEqual((values["line_in_hunk"], values["line_is_added"]), (1, 0))
        finding.update(bench_meta={"kind": "planted"}, label="real_issue", case_id="secret", config="secret")
        self.assertEqual(values, ff.features(finding, PATCH, 0, 1))

    def test_invalid_confidence_rejected_and_missing_explicit(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.assertRaises(ValueError):
                ff.features({"confidence": value}, PATCH, 0, 1)
        self.assertEqual(ff.features({}, PATCH, 0, 1)["confidence_missing"], 1)

    def test_planted_metric_dedupes_findings_and_counts_empty_reviews(self):
        reviews = [{"review_id": i, "planted": True} for i in range(3)]
        rows = [{**reviews[i], "correct_injected": True, "matches_injected": True} for i in (0, 0, 1)]
        values = ff.metrics(rows, reviews, np.array([1, 1, 1]), np.array([False, True, False]))
        self.assertEqual(values["correct_planted_dropped"], 1)
        self.assertEqual(values["correct_planted_kept"], 1)
        self.assertAlmostEqual(values["planted_loss_pp"], 100 / 3)
        self.assertEqual(values["matching_planted_kept"], 1)

    def test_threshold_uses_only_training_reviews_including_empty_ones(self):
        reviews = [{"review_id": i, "group": "train", "config": "a", "planted": True}
                   for i in range(20)]
        reviews.append({"review_id": 20, "group": "test", "config": "b", "planted": True})
        rows = [{**reviews[i], "correct_injected": i == 0} for i in range(3)]
        indices = np.arange(3)
        scores, y = np.array([0.1, 0.5, 0.9]), np.array([1, 0, 1])
        self.assertEqual(ff.tune_threshold(scores, indices, rows, reviews, y, 0.05), 0.9)
        self.assertEqual(ff.tune_threshold(scores, indices, rows, reviews, y, 0), 0.0)
        # A high-scoring held-out finding must not affect threshold selection.
        rows.append({**reviews[20], "correct_injected": True})
        self.assertEqual(ff.tune_threshold(np.r_[scores, 1.0], indices, rows, reviews,
                                           np.r_[y, 1], 0.05), 0.9)

    def test_nested_cv_never_shares_source_or_config(self):
        rows, reviews = [], []
        for group in range(10):
            for config in ("a", "b", "c"):
                review = {"review_id": len(reviews), "case_id": str(group), "group": str(group),
                          "config": config, "planted": group % 2 == 0}
                reviews.append(review)
                rows.append({**review, "label": "real_issue" if group % 2 == 0 else "false_positive",
                             "correct_injected": group % 2 == 0, "matches_injected": group % 2 == 0,
                             "features": {"confidence": 0.9 if group % 2 == 0 else 0.5}})
        original = ff.predict
        calls = []

        def checked_predict(name, train, test, x, y):
            self.assertFalse({rows[i]["group"] for i in train} & {rows[i]["group"] for i in test})
            calls.append((train, test))
            return original("confidence", train, test, x, y)

        with patch.object(ff, "predict", side_effect=checked_predict):
            first = ff.evaluate(rows, reviews, "real_only", "source_and_config")
            second = ff.evaluate(rows, reviews, "real_only", "source_and_config")
        self.assertEqual(first, second)
        # Each outer fit is followed by five inner fits. Only outer fits must also exclude config.
        for train, test in calls[::6]:
            self.assertFalse({rows[i]["config"] for i in train} & {rows[i]["config"] for i in test})

    def test_loader_rejects_wrong_dataset_and_verdict_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset.json"
            dataset.write_text(json.dumps({"cases": [{"case_id": "case", "patch_diff": PATCH,
                "bench_meta": {"kind": "planted", "source_event_id": "source"}}]}))
            result = root / "model#r1.jsonl"
            header = {"type": "header", "label": "model", "dataset_sha256": ff.sha256(dataset)}
            record = {"type": "case", "case_id": "case", "ok": True, "findings": [{}]}
            result.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n")
            judge = Path(str(result) + ".judge-model.jsonl")
            verdict = {"index": 0, "label": "real_issue", "matches_injected": True, "explanation_correct": True}
            judged = {"type": "case", "case_id": "case", "kind": "planted", "n_findings": 1,
                      "judge": {"verdicts": [verdict]}}
            judge.write_text(json.dumps(judged) + "\n")
            rows, reviews, _ = ff.load_data(dataset, [judge])
            self.assertTrue(rows[0]["correct_injected"])
            self.assertEqual(len(reviews), 1)
            invalid = copy.deepcopy(judged)
            invalid["judge"]["verdicts"][0]["index"] = 1
            judge.write_text(json.dumps(invalid) + "\n")
            with self.assertRaisesRegex(ValueError, "verdict indices"):
                ff.load_data(dataset, [judge])
            header["dataset_sha256"] = "wrong"
            result.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                ff.load_data(dataset, [judge])


if __name__ == "__main__":
    unittest.main()
