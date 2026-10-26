# Finding filter: DRYDOCK-ud08 phase 1

## Recommendation: NO-GO for phase 2

Do not replace or supplement drydock's production confidence gate with these
models yet. Neither learned filter clearly improves **high-value precision**
within the five-point planted-recall allowance on unseen source patches and
configs. The broader real+minor target has a nominal positive result against a
fold-tuned confidence baseline, but not a clear precision gain over the ordinary
confidence-threshold curve. No drydock Go code or production gates were changed.

## Data and spend

All results below use **v1**, verified against each result header's dataset SHA256:
`5980246f0ac76ceada79250d61ceea30a22982f18e2f6d166e100be1d730d4ed`.
V2 was inspected but not mixed into the experiment.

| Rep-1 config | Labelled reviews | Findings |
|---|---:|---:|
| qwen3.8-27b + think-off + typed-prompt (existing) | 45 | 81 |
| qwen3.8-27b + think-off + calibrated-prompt (existing) | 45 | 76 |
| qwen3.8-27b, thinking on | 14 | 73 |
| qwen3.6-35b-a3b + think-off + typed-prompt | 13 | 41 |
| gemma-4-26b-a4b + think-off | 15 | 36 |
| ref:deepseek-v4.1-flash | 14 | 65 |
| **Total** | **146** | **372** |

There are 45 distinct case IDs, 32 source-patch groups, and 97 planted review
instances. Labels: 87 real_issue, 199 minor_valid, 84 false_positive, 2 hallucinated.
The expansion added 215 findings from 56 successful reviews. Sampling was
label-blind: `random.Random(1337)`, sample five clean cases followed by ten planted
cases from v1 dataset order, using the same sample for each new config. Three
failed reviewer results were excluded; one judge response was truncated and was
not retried. This missingness can bias the sample.

**New judge spend:** $2.638812 reported for successful calls, plus an unreported
failed-call charge bounded by $0.223232: **total at most $2.862044**, below $5.
Existing labels are reused, not re-purchased. The runs-only expansion driver
imports `judge.py`, uses its prompt, parser and main loop with `--dataset` v1,
`--results`, `--out` next to the saved results, and one worker. It adds output caps
(3072 initially, 8192 subsequently), disables retries, and checks a conservative
next-request cost bound before every call. The failed call's entire bound remains
reserved. Logs, driver, responses and spend receipts remain in the main checkout's
`runs/drydock/openrouter/`; none are committed. Scoring/evaluation makes no API calls.

## Features and evaluation

`finding_filter.py` uses whitespace-normalized, same-file evidence substring
matches and quoted spans (at least eight characters) in added/replacement lines;
new-side hunk membership and added-line membership; categorical severity/category;
confidence and missingness; explanation character/word counts; individual/total
hedges (may, might, could, potentially, ensure); external-library/protocol keyword
counts; review finding count and absolute/relative list position. These are cheap
heuristics, not proofs of correctness. No embeddings, source/model IDs, injected
metadata, judge rationale, severity_ok or suggestion text enter the feature vector.

Models are fixed, not hyperparameter-searched: standardized DictVectorizer features
with logistic regression (C=1), and gradient boosting (60 trees, depth 2, minimum
leaf 10, learning rate .05). Vectorization/scaling fit on training rows only. Seed
1337 is used throughout. `real_only` counts minor_valid as negative; `real_plus_minor`
counts it as positive. False positives and hallucinations are negative in both.

Five shuffled GroupKFold folds group by source_event_id, **stronger than case_id**:
clean/planted siblings and every config's findings for a source stay together.
Primary `source_and_config` CV additionally removes the tested config from training
(5 source folds crossed with six held-out configs). Thus neither the source patch
nor config is seen in an outer training set. This is config-, not model-family-,
holdout. Secondary `source` CV permits other cases from the same config in training.
Each finding is tested exactly once in each evaluation.

For adaptive operating points, inner grouped OOF scores select the threshold with
highest target precision while allowing 0/5/10 percentage points of absolute
planted-recall loss, relative to keeping all findings. Ties favor more positives,
then lower thresholds. Confidence receives the same inner selection. Outer labels
never select thresholds. The requested inner loss budget is **not** a guarantee
on held-out data; the tables report actual loss. No model/threshold was retuned
after seeing the pilot. The complete observed confidence-threshold curve is also
exported, to avoid choosing an artificially weak baseline.

Planted detection is counted **once per review**, not per finding: matches_injected,
a correct explanation, and a real/minor label. All 97 planted reviews, including
zero-finding reviews, form the denominator. Before filtering, 70/97 (72.16%) are
correct detections (matches_injected alone: 71/97). Dropping the last correct
matching finding loses that review's detection. The JSON reports matches_injected-only
counts separately at every operating point.

## Confidence-threshold baseline

Selected points from the full curve. P/R are finding-level percentages; planted
kept is out of 97. This descriptive curve does not certify a deployed threshold.

| Confidence >= | Real P / R | Real+minor P / R | Findings kept | Planted kept | Correct detections dropped | Loss pp |
|---|---:|---:|---:|---:|---:|---:|
| 0 (keep all) | 23.39 / 100.00 | 76.88 / 100.00 | 372 | 70 | 0 | 0.00 |
| .72 | 30.22 / 96.55 | 78.06 / 75.87 | 278 | 70 | 0 | 0.00 |
| .80 | 33.74 / 95.40 | 77.64 / 66.78 | 246 | 69 | 1 | 1.03 |
| .85 | 40.61 / 91.95 | 76.14 / 52.45 | 197 | 67 | 3 | 3.09 |
| .90 | 48.70 / 86.21 | 78.57 / 42.31 | 154 | 65 | 5 | 5.15 |
| .95 | 61.26 / 78.16 | 81.08 / 31.47 | 111 | 64 | 6 | 6.19 |
| .98 | 88.57 / 71.26 | 94.29 / 23.08 | 70 | 60 | 10 | 10.31 |

## Primary CV: unseen source and config

Policy is the **inner** allowed loss in pp; actual outer loss is the last column.
P/R are finding-level percentages. Every planted-kept count is out of 97.

| Target | Model | Policy | P | R | Findings kept | Planted kept | Dropped | Loss pp |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| real | confidence | 0 | 32.30 | 95.40 | 257 | 69 | 1 | 1.03 |
| real | confidence | 5 | 45.78 | 87.36 | 166 | 65 | 5 | 5.15 |
| real | confidence | 10 | 62.62 | 77.01 | 107 | 62 | 8 | 8.25 |
| real | logistic | 0 | 33.19 | 88.51 | 232 | 65 | 5 | 5.15 |
| real | logistic | 5 | 45.51 | 81.61 | 156 | 62 | 8 | 8.25 |
| real | logistic | 10 | 50.43 | 67.82 | 117 | 56 | 14 | 14.43 |
| real | tree | 0 | 28.57 | 98.85 | 301 | 70 | 0 | 0.00 |
| real | tree | 5 | 42.37 | 86.21 | 177 | 64 | 6 | 6.19 |
| real | tree | 10 | 57.66 | 73.56 | 111 | 59 | 11 | 11.34 |
| real+minor | confidence | 0 | 75.68 | 78.32 | 296 | 70 | 0 | 0.00 |
| real+minor | confidence | 5 | 72.77 | 56.99 | 224 | 66 | 4 | 4.12 |
| real+minor | confidence | 10 | 73.23 | 32.52 | 127 | 62 | 8 | 8.25 |
| real+minor | logistic | 0 | 77.91 | 93.71 | 344 | 69 | 1 | 1.03 |
| real+minor | logistic | 5 | 77.57 | 87.06 | 321 | 64 | 6 | 6.19 |
| real+minor | logistic | 10 | 78.21 | 85.31 | 312 | 62 | 8 | 8.25 |
| real+minor | tree | 0 | 77.01 | 97.20 | 361 | 68 | 2 | 2.06 |
| real+minor | tree | 5 | 77.97 | 94.06 | 345 | 67 | 3 | 3.09 |
| real+minor | tree | 10 | 78.95 | 78.67 | 285 | 60 | 10 | 10.31 |

## Secondary CV: unseen source, config may be seen

Same five-point inner policy; all other operating points are in the JSON artifact.

| Target | Model | P | R | Findings kept | Planted kept / 97 | Dropped | Loss pp |
|---|---|---:|---:|---:|---:|---:|---:|
| real | confidence | 49.67 | 87.36 | 153 | 65 | 5 | 5.15 |
| real | logistic | 50.70 | 82.76 | 142 | 64 | 6 | 6.19 |
| real | tree | 46.06 | 87.36 | 165 | 64 | 6 | 6.19 |
| real+minor | confidence | 77.78 | 48.95 | 180 | 65 | 5 | 5.15 |
| real+minor | logistic | 79.40 | 93.01 | 335 | 68 | 2 | 2.06 |
| real+minor | tree | 78.26 | 94.41 | 345 | 69 | 1 | 1.03 |

## Interpretation and limits

At the primary five-point policy, real-only logistic has **45.51% precision**
versus confidence's **45.78%**, while losing 8/97 planted detections (8.25 pp);
tree has **42.37% precision** and loses 6/97 (6.19 pp). Both miss the recall limit.
A fixed .3 real-only tree threshold reaches 82.05% precision / 73.56% finding recall,
but drops 10 correct planted detections (10.31 pp): high precision is not free.

The favorable broader-target result must not be hidden: primary tree at the
five-point policy improves precision by **5.20 pp** against fold-tuned confidence,
with only 3.09 pp loss. Its paired source-cluster bootstrap 95% interval is
[1.96, 8.24] pp. However, its 77.97% precision is no better than simple confidence
>= .72 (78.06%, zero planted loss); source-only gain is just 0.48 pp, interval
[-4.78, 4.61]. Primary broader-target logistic's +4.80 pp gain has interval
[1.44, 7.66], but fails the planted-loss cap (6.19 pp). Fixed .3 broader-target
logistic preserves all correct planted detections on primary CV, but gives only
78.12% precision, effectively the baseline's 78.06%. This is evidence for better
minor-valid recall, not a clear precision improvement warranting a new gate.

Bootstrap uses 2000 paired resamples of the 32 source groups, conditional on the
fitted OOF models, not independent model refits; it is descriptive, not deployment
acceptance. One judge, a small synthetic/planted benchmark, correlated prompt
variants, v1 line-number defects and sampled/missing reviews limit transfer.
Confidence is not calibrated as a probability of usefulness, but still ranks easy
planted detections strongly. This phase does not establish generalization to
unseen production repositories or model families. **Leave phase 2 unstarted.**

## Reproduce and verify

Run from the assigned `nostr-bench-filter` worktree, with the main checkout read-only
except its venv and runs directory:

```sh
V=/Users/bizarro/Documents/Projects/nostr-bench/.venv
B=/Users/bizarro/Documents/Projects/nostr-bench
R="$B/runs/drydock/openrouter"
"$V/bin/pip" install -r requirements.txt
"$V/bin/python" -m unittest discover -s suites/drydock -p test_finding_filter.py -v
"$V/bin/python" suites/drydock/finding_filter.py \
  --dataset "$B/suites/drydock/data/drydock-planted-v1.json" \
  --judges "$R/*.judge-claude-opus-5.5.jsonl" \
  --out "$R/finding-filter-cv.json"
```

Freeze the six judge inputs listed above when replaying; a future broader glob
is a different experiment. Each label filename is its result filename plus
`.judge-claude-opus-5.5.jsonl`. New result samples are named
`<config>#r1.filter-sample.jsonl`; the two existing runs use `<config>#r1.jsonl`.
The output records SHA256 for every input, OOF probabilities, threshold ranges,
all operating-point counts and paired intervals. Dataset-hash mismatches,
duplicate review identities and incomplete/non-bijective verdict indices fail closed.

Environment: Python 3.14.8, scikit-learn 1.8.0, numpy 2.5.4, scipy 1.18.1,
joblib 1.6.0, threadpoolctl 3.7.0 (sklearn pinned in requirements.txt).
Seven offline checks cover diff parsing, quote/file grounding, feature isolation,
confidence validation, planted deduplication/zero-finding denominators, nested
source/config separation, training-only thresholds, loader alignment and dataset
hash rejection. `pip check`, `py_compile` and `git diff --check` also pass.
Two complete offline executions produced byte-identical JSON artifacts, SHA256:
`06266a72f28762d7ef7d9ec73ecb6a08f8bc1833da5bcfc17a19ee798cbef46b`.
Navigation-only Jev calls selected source ranges (presence .97/.98; $0.000454),
separate from judge spend; Jev is not used in finding features, training or scoring.
