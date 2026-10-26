# drydock: OpenRouter screen → Lemmy shortlist (2026-10-26)

Full table: `report/drydock-results.md` (regenerate with `python3 suites/drydock/report.py --phase openrouter`).
Setup: 37 configs × 3 reps × 45 hidden cases (30 planted bugs, 15 clean). drydock's real engine ran on
OpenRouter at provider precision. Total spend $38.57. Strict = drydock's own grader. Gaps ≤5 points
with overlapping rep ranges count as ties.

## Headline

| config | strict (range) | ok | calls/review | out tok/review | on Lemmy |
|---|---|---|---|---|---|
| ref: deepseek-v4.1-flash (thinking) | 76 (73–80) | 97 | 4.85 | 30,490 | cloud only (ceiling) |
| **qwen3.8-27b (thinking)** | **71 (70–73)** | 99 | 4.95 | 18,821 | Q4_K_M 16.5 GB, 1 card |
| **qwen3.8-27b, think-off, typed prompt** | **57 (50–63)** | 100 | 3.01 | 1,169 | Q4_K_M 16.5 GB, 1 card |
| qwen3.8-27b, think-off | 50 (47–53) | 99 | 4.71 | 2,181 | same |
| qwen3.6-27b, think-off | 42 (37–50) | 98 | 4.83 | 3,706 | 1 card |
| qwen3.6-35b-a3b, think-off (+typed: 40) | 41 (37–47) | 97 | 4.90 | 3,655 | IQ4_XS 17.7 GB, 1 card, MoE 3B active |
| muse-glimmer-30b | 38 (37–40) | 100 | 4.70 | 8,041 | 1 card |
| gemma-4-26b-a4b (production) | 17–20 | 100 | 4.82 | 1,874–2,819 | 1 card |
| llama-3.3-70b (production) | 11 (3–20) | 95 | 4.99 | 1,017 | 2 cards |
| qwen2.5-coder-32b (production) | 4 (0–7) | 43 | 5.83 | 2,051 | 2 cards |

* qwen3.8-27b with thinking (71) ties the cloud references (deepseek-v4.1-flash 76, deepseek-v4-pro 57).
  So the suite discriminates: it isn't too hard, and the best local-size model is near the ceiling.
* Thinking costs 8–16× the output tokens. P40 decode is bandwidth-bound, so on Lemmy thinking means
  minutes per review against drydock's 120 s per-call timeout. **Think-off is the deployable default.**
* **Typed prompt** (field types and allowed values added to the planner and reviewer system prompts):
  planner repairs fell from ~1.0 to 0.00 per review for every model, calls per review from ~4.8 to ~3.0,
  and output tokens by 35–57% for the leaders. Accuracy stayed within noise. Recommended drydock change,
  independent of the model choice.
* Ruled out, mostly for failing drydock's pipeline ("ok" = reviews that complete): qwen2.5-coder-32b (43%),
  glm-4.7-flash thinking (49%), ministral-3-14b (51%), nemotron-3.5 (58–73%), qwen3-coder-next (67%, plus
  307 provider retries), gpt-oss-20b (72–81%, strict ≤7). Also gpt-oss-120b (strict 14–21, needs CPU
  offload), granite-4.2-8b (strict 4).

## Lemmy shortlist (measure on the P40s)

The typed prompt is now part of drydock (branch `bench/local-model-eval`, commit 891daaf), so build
`drydock-bench` from that branch and no prompt flag is needed. Until the agentic run below is done,
Lemmy should run drydock with `DRYDOCK_AGENTIC_REVIEW_FALLBACK=true` (single-shot path).

1. **Reviewer: qwen3.8-27b think-off.** Quant sweep Q4_K_M / Q5_K_M / Q8_0 (Q8 splits across both cards),
   ngram speculative decoding, thinking on as the accuracy-vs-latency check, and annotated lines.
2. **Fast alternative: qwen3.6-35b-a3b think-off** (MoE, ~3B active, so it should decode several times
   faster on P40). It's a candidate planner/walkthrough, or the reviewer if qwen3.8 can't meet the timeout.
   Includes the MTP speculative variant.
3. **Deploy splits to compare:**
   * A: qwen3.8-27b@Q4_K_M on each card, all roles, two replicas for concurrent reviews (run one, then
     scale).
   * B: planner + walkthrough on qwen3.6-35b-a3b (GPU1) with the reviewer on qwen3.8-27b (GPU0).
   * C: qwen3.8-27b@Q8_0 across both cards (if the quant sweep shows Q4 losing accuracy).

```bash
cd suites/drydock
python3 sweep.py preflight
python3 sweep.py run --phase efficiency \
  --models qwen3.8-27b@Q4_K_M+think-off,qwen3.6-35b-a3b@IQ4_XS+think-off
python3 sweep.py run --phase deploy \
  --planner qwen3.6-35b-a3b@IQ4_XS+think-off --reviewer qwen3.8-27b@Q4_K_M+think-off
python3 report.py --phase efficiency && python3 report.py --phase deploy
```

Compare each Lemmy row against its OpenRouter twin. A Q4 drop beyond the rep range is a real
quantization cost. A speculative-decoding drop is a serving bug, because speculation is lossless.
Pass bar: ok ≥ 90% and ≤ 10% of reviews with a call over 120 s, or raise drydock's timeout deliberately.

## Follow-ups after the OpenRouter screen

* **Frontier judge (Claude Opus 5.5) on qwen3.8-27b, think-off, typed prompt, rep 1:** planted bug found in
  23/30 cases with every explanation correct; 1/81 findings hallucinated. But 25% false positives and only
  31% high-value findings, severity too high on 44/81, and 3/15 real pre-existing defects caught.
  Usefulness 3.16/5. A "calibrated" severity/precision prompt was measured and rejected (false positives
  rose to 38%, usefulness fell to 2.80). Use `suites/drydock/judge.py` to reproduce.
* **LFM2.5-24B-A2B** (Oct 2026, fits one P40): 3% strict, ~20k output tokens per review. Ruled out.
* **Agentic path** (drydock's default): 0 of 16 smoke reviews published findings because the
  model could not see the tool-call IDs it must cite. With the drydock fixes (visible IDs, budget warning,
  finding-level needs_more_context, full coverage errors) and a larger reviewer budget, 12/16 completed.
  qwen3.8-27b with thinking was the most reliable (4/4). Each review sends 100k-1M cumulative prompt
  tokens, so measure on Lemmy with llama.cpp prompt caching before switching off the fallback.
  Dataset: `build_agentic.py` (28 cases on 8 cloneable repos); run with `sweep.py --agentic`.
