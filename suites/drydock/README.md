# drydock suite — choosing local models for drydock on 2x Tesla P40

Benchmarks drydock's **real review engine** (planner → reviewer → walkthrough,
`internal/reviewengine`) against a hidden planted-bug dataset built from
`drydock-test-corpus`, and sweeps model→role assignments that fit 48 GB of
Pascal VRAM. Each config is measured on accuracy (drydock's own grader), on
deployability (pipeline completion, JSON repairs, drydock's 120 s per-call
timeout) and on throughput (prefill and decode tok/s, $/review).

## Why the dataset is synthetic-on-real

The corpus has no labelled findings: `review_feedback` and `eval_runs` are
empty, and only a handful of patches have merged/closed outcomes. Its 858
published reviews **cannot rank models**. Per
`drydock/docs/investigations/review-mismatch-2026-08-12.md` they were produced
from broken inputs: cover letters used as diffs, 1,700–4,600-file stale-base
diffs, and checkout races. The corpus *inputs* are clean, though: kind-1617
events carry real `git format-patch` diffs from 18 nostr projects.

`build_dataset.py` therefore takes the 44 distinct code patches (8–500 added
lines, ≤10 files, ≤6 per repo) and builds:

* **30 planted cases**: one fresh bug per patch on a non-test added line, at
  an exact new-file line. Inserted lines only go where they would compile:
  statement lists, not struct, match or JSX bodies, and not Rust strings
  embedding JS. The operators are flipped comparisons, `&&`/`||`
  swaps, dropped `await`, inverted boolean returns, verification bypass,
  hardcoded nsec/hex key/token, and TLS verification disabled. The mix is
  roughly 37% security and 63% correctness. `return await` is never
  stripped, because that change is not a bug.
* **15 clean controls**: untouched originals, used to measure noise.

Line numbers are checked by re-parsing the rendered diff. Expected findings
live only in the dataset file. The model receives only what production would
send: the bundle, `## patch` and the changed files. `data/` is gitignored and
must never be published.

## Pieces

| file | what |
|---|---|
| `build_dataset.py` | corpus (read-only, `immutable=1`) → `data/drydock-planted-v2{,-annotated}.json` + `.smoke.json` |
| `drydock/cmd/drydock-bench` | Go runner using drydock's engine + `eval.ScoreCase`; JSONL with per-call stage, latency, tokens, llama.cpp timings, repairs; resumable |
| `roster.yaml` | P40-sized candidates (live scan 2026-10-26: real HF repos + GGUF sizes), serve defaults, phase plans |
| `sweep.py` | starts llama-server(s) per config, wires `DRYDOCK_*` role env, runs reps, samples nvidia-smi |
| `report.py` | ranked Markdown/JSON in `report/drydock-results.*`, prompt A/B and role-signal tables |
| `judge.py` | frontier-model quality pass over saved results: per-finding real/minor/false-positive/hallucinated labels, reference review, usefulness |
| `render_reviews.py` | renders saved results as readable Markdown reviews (planted bug, each finding, judge verdict, diff) into `runs/drydock/reviews/` (gitignored: contains hidden answers) |
| `build_agentic.py` | clones each case's repo from corpus clone URLs, finds a base commit where the patch applies, writes `data/drydock-agentic-v2.json` for `sweep.py --agentic` |

## Step 1: OpenRouter screen (full precision, before touching Lemmy)

Every roster model on OpenRouter (16 of 19), plus two cloud-only ceilings, runs
the same engine and hidden dataset with every drydock role pointed at the
hosted model. Reasoning models run twice: provider default and thinking off.
In total that is 29 configs × 3 reps × 45 cases, roughly $20–50.

```bash
echo 'sk-or-...' > .orkey             # or export OPENROUTER_API_KEY; .orkey is gitignored
cd suites/drydock
python3 sweep.py verify-or            # one 20-token call per id (~$0.01 total)
python3 sweep.py plan --phase openrouter --include-offload
python3 sweep.py run --phase openrouter --reps 1 --models gpt-oss-20b   # ~$0.05 pilot
setsid nohup python3 -u sweep.py run --phase openrouter --include-offload >> ../../.work/or.log 2>&1 < /dev/null & disown
python3 report.py --phase openrouter
```

Read it as: **accuracy and JSON reliability at full precision**. The `Lemmy fit`
column shows the quant and cards each model would need. Shortlist the top
deployable configs, then run them on Lemmy (steps below) to measure what Q4 and
the P40s cost in accuracy and speed. Hosted latency is not P40 latency.
`qwen2.5-coder-14b`, `devstral-small-2` and `seed-oss-36b` aren't on OpenRouter,
so they can only be tested on Lemmy.

## Step 2: run it on Lemmy (2x P40)

```bash
# once: llama.cpp for Pascal (needs a build new enough for --spec-type/--reasoning)
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=61 && cmake --build build -j
export LLAMA_SERVER_BIN=$PWD/build/bin/llama-server

# once: bench binary + dataset (or copy them over from the Mac)
(cd ../drydock && go build -o ../nostr-bench/.work/drydock-bench ./cmd/drydock-bench)
python3 -I suites/drydock/build_dataset.py --db /path/drydock.db --out suites/drydock/data/drydock-planted-v2.json
python3 -I suites/drydock/build_dataset.py --db /path/drydock.db --out suites/drydock/data/drydock-planted-v2-annotated.json --annotate-lines

cd suites/drydock
python3 sweep.py preflight                    # flags, GPUs (expect 2x P40, compute 6.1), files
python3 sweep.py plan --phase screen          # dry run: exact llama-server commands

# phase 1 — screen every model as an all-roles server (n=1, ~53 cases each)
setsid nohup python3 -u sweep.py run --phase screen >> ../../.work/screen.log 2>&1 < /dev/null & disown
python3 report.py --phase screen

# phase 2 — efficiency on the top 3-4 (quant, thinking off/effort, ngram/MTP spec, -sm row, annotated lines; n=3)
python3 sweep.py run --phase efficiency --models qwen3.6-35b-a3b,qwen3.8-27b,gpt-oss-20b

# phase 3 — role split across the two cards (planner on GPU1, reviewer on GPU0; n=3)
python3 sweep.py run --phase deploy --planner gpt-oss-20b@MXFP4 --reviewer qwen3.8-27b@Q4_K_M+think-off
python3 report.py
```

`--max-tokens N` adds a `+capN` variant. Production sends no cap, and the Mac
smoke test caught gemma-4-26b-a4b in a 22k-token thinking loop on a single
call. On P40s that means a timed-out review, so test a cap like 8192 on the
finalists.

Everything resumes: completed cases are skipped. Failed cases are outcomes and
are **not** retried; use `--retry-errors` only after an infrastructure crash.

## Reading the report

* **strict**: drydock's grade (category + file + line ±2). Use it as the headline.
* **detected**: right file, plus the line within tolerance or the planted code quoted in
  the evidence. A wide gap between strict and detected with a large `|line err|`
  means the model found the bug but miscounted diff lines. Production drydock sends
  raw diffs with no line numbers, so the `+annot` variant tests whether adding a
  line-number layer (a drydock change) beats a model swap.
* **noise / hi**: findings per clean control. The originals may hold real bugs,
  so read this as a noise rate, not a strict false-positive rate.
* **>120s**: share of cases with any call over the production per-call timeout.
  Configs above 10% are marked not deployable unless the timeout is raised.
* **Speculative variants** should match their baseline's accuracy (decoding is
  lossless). A drop points to a serving bug.
* n=3 is the floor for claims. Gaps ≤5 points with overlapping rep ranges are ties.

## Dataset versions

`v1` diffs carried a parser artifact: a format-patch `--` trailer without its trailing space became a
phantom deletion line, so 39/45 diffs had an off-by-one last-hunk header. Planted lines and expected
findings were unaffected, and every model saw identical inputs, so the OpenRouter screen in
`report/drydock-results.md` (run on v1) still ranks fairly; v1 diffs just do not `git apply`. All
defaults now use `v2`.

## Known limits / next steps

* No file-context layer: the bundle is repo name + description + diff, so there is
  no repo checkout. Production adds changed-file contents when a checkout exists.
* 1618/1619 PRs (1,919 events) aren't used yet. Their diffs need a clone plus a
  provenance-checked base, which is exactly the bug the investigation found. That
  route would also unlock the 8 maintainer rebuttals in `conversations` as
  false-positive traps.
* Meta-review (strict JSON, 31/50 production schema failures) and the security
  routes aren't exercised yet. The planner path's repair rate is the closest
  proxy for strict-JSON reliability.
