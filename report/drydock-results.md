# Drydock local-model benchmark (2x P40)

Hidden planted-bug suite built from drydock-test-corpus (see suites/drydock/README.md).
Ranked by strict recall among deployable configs (ok >= 90%, >120s <= 10%).

Hosted (OpenRouter) rows: $/review is billed cost and latency columns are not P40-representative.

| # | phase | config | reps | strict (min–max) | detected | sec / corr | |line err| | noise / hi | ok | repairs | p50 s | p95 s | >120s | pp t/s | tg t/s | think kch | $/review | Lemmy fit | ok? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | openrouter | `ref:deepseek-v4.1-flash` | 3 | 76 (73–80) | 87 | 97 / 81 | 0.0 | 3.2 / 0.4 | 97 | 1.85 | 78 | 554 | 19 | – | – | 102.9 | 2.26¢ | cloud only | ✓ |
| 2 | openrouter | `or:qwen3.8-27b` (tie) | 3 | 71 (70–73) | 84 | 97 / 77 | 0.0 | 4.8 / 1.4 | 99 | 1.95 | 150 | 345 | 36 | – | – | 58.0 | 4.20¢ | Q4_K_M 16.5 GB, 1xP40 | ✓ |
| 3 | openrouter | `ref:deepseek-v4-pro` | 3 | 57 (47–63) | 79 | 91 / 72 | 1.0 | 2.6 / 0.8 | 90 | 1.59 | 149 | 621 | 38 | – | – | 33.2 | 3.86¢ | cloud only | ✓ |
| 4 | openrouter | `or:qwen3.8-27b+think-off+typed-prompt` | 3 | 57 (50–63) | 78 | 100 / 65 | 0.5 | 1.8 / 0.4 | 100 | 0.01 | 12 | 24 | 0 | – | – | 0.0 | 0.33¢ | Q4_K_M 16.5 GB, 1xP40 | ✓ |
| 5 | openrouter | `or:qwen3.8-27b+think-off+calibrated-prompt` | 3 | 52 (47–57) | 66 | 100 / 46 | 1.0 | 1.4 / 0.3 | 100 | 0.02 | 13 | 27 | 0 | – | – | 0.0 | 0.35¢ | Q4_K_M 16.5 GB, 1xP40 | ✓ |
| 6 | openrouter | `ref:deepseek-v4.1-flash+think-off` | 3 | 50 (43–60) | 81 | 88 / 77 | 1.0 | 5.6 / 0.9 | 99 | 1.90 | 22 | 43 | 1 | – | – | 0.2 | 0.57¢ | cloud only | ✓ |
| 7 | openrouter | `or:qwen3.8-27b+think-off` | 3 | 50 (47–53) | 74 | 100 / 60 | 1.0 | 1.9 / 0.6 | 99 | 1.71 | 23 | 43 | 1 | – | – | 0.0 | 0.55¢ | Q4_K_M 16.5 GB, 1xP40 | ✓ |
| 8 | openrouter | `ref:deepseek-v4-pro+think-off` | 3 | 49 (43–53) | 76 | 91 / 67 | 1.0 | 3.7 / 0.8 | 96 | 1.96 | 53 | 109 | 1 | – | – | 0.0 | 1.95¢ | cloud only | ✓ |
| 9 | openrouter | `or:qwen3.6-27b+think-off` | 3 | 42 (37–50) | 66 | 94 / 49 | 1.0 | 3.4 / 0.7 | 98 | 1.83 | 57 | 113 | 4 | – | – | 0.0 | 1.28¢ | Q4_K_M 16.8 GB, 1xP40 | ✓ |
| 10 | openrouter | `or:qwen3.6-27b` | 3 | 41 (37–43) | 78 | 97 / 67 | 2.0 | 3.6 / 0.4 | 100 | 2.00 | 212 | 337 | 18 | – | – | 42.5 | 4.02¢ | Q4_K_M 16.8 GB, 1xP40 | ✓ |
| 11 | openrouter | `or:qwen3.6-35b-a3b+think-off` | 3 | 41 (37–47) | 56 | 85 / 39 | 1.0 | 4.2 / 1.0 | 97 | 1.90 | 40 | 89 | 3 | – | – | 0.0 | 0.48¢ | IQ4_XS 17.7 GB, 1xP40 | ✓ |
| 12 | openrouter | `or:qwen3.6-35b-a3b` | 3 | 40 (37–43) | 66 | 76 / 60 | 2.0 | 4.0 / 0.7 | 99 | 1.95 | 169 | 272 | 4 | – | – | 51.9 | 1.62¢ | IQ4_XS 17.7 GB, 1xP40 | ✓ |
| 13 | openrouter | `or:muse-glimmer-30b` | 3 | 38 (37–40) | 77 | 88 / 70 | 2.0 | 4.5 / 0.3 | 100 | 1.70 | 110 | 419 | 19 | – | – | 24.7 | 1.36¢ | UD-Q4_K_XL 15.9 GB, 1xP40 | ✓ |
| 14 | openrouter | `or:gemma-4-31b` | 3 | 31 (30–33) | 61 | 91 / 44 | 2.0 | 1.6 / 0.4 | 100 | 1.29 | 35 | 65 | 0 | – | – | 0.0 | 0.19¢ | Q4_K_M 18.3 GB, 1xP40 | ✓ |
| 15 | openrouter | `or:gemma-4-31b+think-off` | 3 | 28 (27–30) | 59 | 88 / 42 | 3.0 | 1.6 / 0.4 | 100 | 1.26 | 34 | 73 | 0 | – | – | 0.0 | 0.19¢ | Q4_K_M 18.3 GB, 1xP40 | ✓ |
| 16 | openrouter | `or:qwen3-coder-30b-a3b` | 3 | 28 (23–33) | 53 | 73 / 42 | 1.0 | 4.7 / 0.9 | 100 | 1.38 | 64 | 136 | 0 | – | – | 0.0 | 0.12¢ | IQ4_XS 16.4 GB, 1xP40 | ✓ |
| 17 | openrouter | `or:qwen3-coder-30b-a3b+typed-prompt` | 3 | 22 (17–27) | 48 | 73 / 33 | 1.0 | 4.3 / 0.5 | 99 | 0.01 | 48 | 89 | 1 | – | – | 0.0 | 0.10¢ | IQ4_XS 16.4 GB, 1xP40 | ✓ |
| 18 | openrouter | `or:glm-4.7-flash+think-off+typed-prompt` | 3 | 22 (20–23) | 43 | 70 / 28 | 1.0 | 3.7 / 1.3 | 93 | 0.07 | 43 | 604 | 9 | – | – | 0.0 | 0.12¢ | Q4_K_M 18.3 GB, 1xP40 | ✓ |
| 19 | openrouter | `or:gpt-oss-120b` | 3 | 21 (17–27) | 52 | 73 / 40 | 4.0 | 3.0 / 0.7 | 93 | 2.22 | 57 | 149 | 4 | – | – | 10.5 | 0.15¢ | MXFP4 63.4 GB, 2xP40 +CPU offload | ✓ |
| 20 | openrouter | `or:gemma-4-26b-a4b+think-off` | 3 | 20 (13–23) | 51 | 79 / 35 | 3.0 | 2.1 / 0.3 | 100 | 1.82 | 25 | 59 | 1 | – | – | 0.0 | 0.17¢ | Q4_K_M 16.9 GB, 1xP40 | ✓ |
| 21 | openrouter | `or:gemma-4-26b-a4b+think-off+typed-prompt` | 3 | 20 (20–20) | 40 | 55 / 32 | 2.5 | 1.8 / 0.5 | 99 | 0.15 | 17 | 51 | 1 | – | – | 0.0 | 0.14¢ | Q4_K_M 16.9 GB, 1xP40 | ✓ |
| 22 | openrouter | `or:gemma-4-26b-a4b` | 3 | 17 (13–20) | 44 | 73 / 28 | 3.0 | 2.2 / 0.4 | 100 | 1.82 | 25 | 43 | 0 | – | – | 0.0 | 0.14¢ | Q4_K_M 16.9 GB, 1xP40 | ✓ |
| 23 | openrouter | `or:gpt-oss-120b+think-low` | 3 | 14 (10–20) | 39 | 52 / 32 | 4.0 | 2.6 / 0.5 | 91 | 2.29 | 31 | 58 | 2 | – | – | 2.0 | 0.10¢ | MXFP4 63.4 GB, 2xP40 +CPU offload | ✓ |
| 24 | openrouter | `or:llama-3.3-70b` | 3 | 11 (3–20) | 19 | 36 / 9 | 1.0 | 2.1 / 0.1 | 95 | 1.99 | 44 | 79 | 0 | – | – | 0.0 | 0.21¢ | Q4_K_M 42.5 GB, 2xP40 | ✓ |
| 25 | openrouter | `or:llama-3.3-70b+typed-prompt` | 3 | 8 (7–10) | 18 | 33 / 9 | 5.0 | 2.4 / 0.0 | 96 | 0.13 | 33 | 75 | 0 | – | – | 0.0 | 0.20¢ | Q4_K_M 42.5 GB, 2xP40 | ✓ |
| 26 | openrouter | `or:gpt-oss-20b+think-low+typed-prompt` | 3 | 7 (3–10) | 29 | 21 / 33 | 6.5 | 0.7 / 0.2 | 96 | 0.34 | 23 | 209 | 9 | – | – | 2.6 | 0.05¢ | MXFP4 12.1 GB, 1xP40 | ✓ |
| 27 | openrouter | `or:granite-4.2-8b` | 3 | 4 (0–7) | 32 | 45 / 25 | 5.0 | 1.0 / 0.1 | 95 | 1.96 | 412 | 786 | 81 | – | – | 60.6 | 0.46¢ | Q8_0 9.3 GB, 1xP40 | ✓ |
| 28 | openrouter | `or:lfm2.5-24b-a2b` | 3 | 3 (0–7) | 10 | 12 / 9 | 3.0 | 1.0 / 0.2 | 100 | 1.90 | 49 | 66 | 0 | – | – | 75.7 | 1.45¢ | Q4_K_M 14.5 GB, 1xP40 | ✓ |
| 29 | openrouter | `or:qwen3.6-35b-a3b+think-off+typed-prompt` | 3 | 40 (33–47) | 57 | 76 / 46 | 1.0 | 3.1 / 0.9 | 90 | 0.03 | 21 | 603 | 10 | – | – | 0.0 | 0.26¢ | IQ4_XS 17.7 GB, 1xP40 | ✗ |
| 30 | openrouter | `or:qwen3-coder-next` | 3 | 26 (17–30) | 44 | 55 / 39 | 1.0 | 3.5 / 1.0 | 67 | 1.56 | 57 | 94 | 1 | – | – | 0.0 | 0.42¢ | MXFP4 48 GB, 2xP40 +CPU offload | ✗ |
| 31 | openrouter | `or:glm-4.7-flash+think-off` | 3 | 22 (20–23) | 42 | 64 / 30 | 2.0 | 3.1 / 1.0 | 86 | 1.84 | 66 | 615 | 12 | – | – | 0.0 | 0.17¢ | Q4_K_M 18.3 GB, 1xP40 | ✗ |
| 32 | openrouter | `or:glm-4.7-flash` | 3 | 18 (13–23) | 31 | 45 / 23 | 2.0 | 1.7 / 0.4 | 49 | 1.31 | 600 | 700 | 64 | – | – | 23.4 | 0.30¢ | Q4_K_M 18.3 GB, 1xP40 | ✗ |
| 33 | openrouter | `or:nemotron-3.5-lightning-30b-a3b+think-off` | 3 | 11 (10–13) | 29 | 39 / 23 | 2.0 | 1.5 / 0.3 | 58 | 2.52 | 23 | 163 | 7 | – | – | 0.0 | 0.17¢ | Q8_0 33.6 GB, 2xP40 | ✗ |
| 34 | openrouter | `or:nemotron-3.5-lightning-30b-a3b` | 3 | 7 (3–13) | 23 | 18 / 26 | 3.0 | 1.9 / 0.3 | 73 | 2.16 | 42 | 231 | 9 | – | – | 25.2 | 0.25¢ | Q8_0 33.6 GB, 2xP40 | ✗ |
| 35 | openrouter | `or:gpt-oss-20b+think-low` | 3 | 6 (0–10) | 20 | 12 / 25 | 5.0 | 1.0 / 0.2 | 81 | 2.01 | 35 | 605 | 16 | – | – | 3.4 | 0.05¢ | MXFP4 12.1 GB, 1xP40 | ✗ |
| 36 | openrouter | `or:qwen2.5-coder-32b` | 3 | 4 (0–7) | 10 | 9 / 11 | 2.0 | 1.7 / 0.2 | 43 | 2.83 | 71 | 111 | 0 | – | – | 0.0 | 0.85¢ | Q4_K_M 19.9 GB, 2xP40 | ✗ |
| 37 | openrouter | `or:ministral-3-14b` | 3 | 3 (3–3) | 18 | 33 / 9 | 9.5 | 2.1 / 0.6 | 51 | 2.86 | 100 | 150 | 0 | – | – | 0.0 | 0.37¢ | Q4_K_M 8.2 GB, 1xP40 | ✗ |
| 38 | openrouter | `or:qwen2.5-coder-32b+typed-prompt` | 3 | 3 (0–7) | 16 | 27 / 9 | 12.0 | 1.4 / 0.2 | 50 | 1.25 | 51 | 98 | 0 | – | – | 0.0 | 0.79¢ | Q4_K_M 19.9 GB, 2xP40 | ✗ |
| 39 | openrouter | `or:gpt-oss-20b` | 3 | 2 (0–7) | 32 | 48 / 23 | 7.0 | 1.6 / 0.3 | 72 | 1.69 | 142 | 653 | 43 | – | – | 27.9 | 0.11¢ | MXFP4 12.1 GB, 1xP40 | ✗ |

Failures by stage: `ref:deepseek-v4.1-flash` {'planner': 1, 'reviewer': 3}; `or:qwen3.8-27b` {'reviewer': 1}; `ref:deepseek-v4-pro` {'planner': 4, 'reviewer': 9}; `ref:deepseek-v4.1-flash+think-off` {'reviewer': 1}; `or:qwen3.8-27b+think-off` {'reviewer': 1}; `ref:deepseek-v4-pro+think-off` {'reviewer': 5}; `or:qwen3.6-27b+think-off` {'reviewer': 3}; `or:qwen3.6-35b-a3b+think-off` {'planner': 2, 'reviewer': 2}; `or:qwen3.6-35b-a3b` {'reviewer': 2}; `or:qwen3-coder-30b-a3b+typed-prompt` {'reviewer': 1}; `or:glm-4.7-flash+think-off+typed-prompt` {'reviewer': 10}; `or:gpt-oss-120b` {'planner': 1, 'reviewer': 9}; `or:gemma-4-26b-a4b+think-off+typed-prompt` {'reviewer': 1}; `or:gpt-oss-120b+think-low` {'planner': 1, 'reviewer': 11}; `or:llama-3.3-70b` {'planner': 2, 'reviewer': 5}; `or:llama-3.3-70b+typed-prompt` {'planner': 2, 'reviewer': 3}; `or:gpt-oss-20b+think-low+typed-prompt` {'planner': 1, 'reviewer': 5}; `or:granite-4.2-8b` {'reviewer': 7}; `or:qwen3.6-35b-a3b+think-off+typed-prompt` {'reviewer': 14}; `or:qwen3-coder-next` {'planner': 6, 'reviewer': 38}; `or:glm-4.7-flash+think-off` {'planner': 6, 'reviewer': 13}; `or:glm-4.7-flash` {'planner': 3, 'reviewer': 66}; `or:nemotron-3.5-lightning-30b-a3b+think-off` {'planner': 1, 'reviewer': 56}; `or:nemotron-3.5-lightning-30b-a3b` {'planner': 2, 'reviewer': 34}; `or:gpt-oss-20b+think-low` {'planner': 10, 'reviewer': 15}; `or:qwen2.5-coder-32b` {'planner': 5, 'reviewer': 72}; `or:ministral-3-14b` {'reviewer': 66}; `or:qwen2.5-coder-32b+typed-prompt` {'reviewer': 67}; `or:gpt-oss-20b` {'planner': 14, 'reviewer': 24}

Excluded incomplete reps: `or:lfm2.5-24b-a2b+typed-prompt#r1.jsonl` 39/45, `or:qwen3.8-27b+think-off+calibrated-prompt#r1.jsonl.judge-claude-opus-5.5.jsonl` 45/?, `or:qwen3.8-27b+think-off+typed-prompt#r1.jsonl.judge-claude-opus-5.5.jsonl` 45/?

OpenRouter spend: $41.00; provider retries: `or:qwen3-coder-30b-a3b+typed-prompt` 1, `or:qwen3-coder-next` 307

Providers that served each hosted config (quantization varies by provider):

- `ref:deepseek-v4.1-flash`: {'Relace': 76, 'InferenceNet': 72, 'Morph': 15, 'ModelRun': 71, 'Wafer': 50, 'Cohere': 18, 'Reka': 5, 'PrimeIntellect': 25, 'Parasail': 13, 'Venice': 9, 'CoreWeave': 52, 'DigitalOcean': 94, 'Together': 33, 'Novita': 10, 'Fireworks': 63, 'OpenInference': 3, 'Makora': 15, 'DeepInfra': 4, 'Decart': 18, 'Nebius': 1}
- `or:qwen3.8-27b`: {'Modal': 188, 'ModelRun': 95, 'CoreWeave': 15, 'AkashML': 58, 'Parasail': 35, 'Near AI': 98, 'DekaLLM': 64, 'Ionstream': 39, 'Reka': 39, 'Wafer': 33, 'Phala': 1, 'Darkbloom': 1}
- `ref:deepseek-v4-pro`: {'Reka': 82, 'Alibaba': 69, 'Relace': 93, 'DigitalOcean': 51, 'Novita': 160, 'Cloudflare': 49, 'SiliconFlow': 21, 'Azure': 2, 'Baidu': 21, 'AtlasCloud': 6, 'StreamLake': 35, 'GMICloud': 1}
- `or:qwen3.8-27b+think-off+typed-prompt`: {'Reka': 25, 'ModelRun': 71, 'Modal': 108, 'Parasail': 30, 'AkashML': 18, 'Near AI': 45, 'Darkbloom': 7, 'DekaLLM': 40, 'Ionstream': 29, 'Wafer': 30, 'CoreWeave': 2, 'Venice': 1, 'Chutes': 1}
- `or:qwen3.8-27b+think-off+calibrated-prompt`: {'Modal': 123, 'ModelRun': 60, 'Parasail': 50, 'Near AI': 28, 'Wafer': 50, 'Reka': 21, 'DekaLLM': 40, 'AkashML': 20, 'Ionstream': 3, 'Novita': 6, 'Phala': 6, 'Mancer 2': 1}
- `ref:deepseek-v4.1-flash+think-off`: {'DigitalOcean': 98, 'Cohere': 25, 'Wafer': 65, 'Relace': 72, 'CoreWeave': 41, 'Fireworks': 64, 'Morph': 24, 'InferenceNet': 74, 'ModelRun': 67, 'Parasail': 18, 'PrimeIntellect': 24, 'Novita': 9, 'Makora': 6, 'Together': 30, 'Venice': 13, 'DeepInfra': 3, 'Reka': 8, 'OpenInference': 4, 'Decart': 14, 'AtlasCloud': 1, 'Crusoe': 1}
- `or:qwen3.8-27b+think-off`: {'ModelRun': 83, 'Near AI': 109, 'Modal': 173, 'Parasail': 39, 'AkashML': 53, 'Ionstream': 37, 'DekaLLM': 54, 'Reka': 42, 'Chutes': 4, 'CoreWeave': 14, 'Darkbloom': 1, 'Wafer': 22, 'DeepInfra': 1, 'Alibaba': 1, 'Phala': 1}
- `ref:deepseek-v4-pro+think-off`: {'Novita': 163, 'Baidu': 22, 'Cloudflare': 59, 'DigitalOcean': 102, 'Reka': 81, 'Alibaba': 77, 'Relace': 113, 'SiliconFlow': 16, 'Azure': 2, 'AtlasCloud': 4, 'StreamLake': 24}
- `or:qwen3.6-27b+think-off`: {'DeepInfra': 132, 'Reka': 275, 'Alibaba': 161, 'SiliconFlow': 38, 'Venice': 39, 'Phala': 1}
- `or:qwen3.6-27b`: {'Reka': 265, 'DeepInfra': 147, 'Alibaba': 153, 'Venice': 71, 'SiliconFlow': 36, 'Phala': 3}
- `or:qwen3.6-35b-a3b+think-off`: {'AkashML': 249, 'DeepInfra': 264, 'Parasail': 87, 'CoreWeave': 30, 'AtlasCloud': 3, 'DekaLLM': 17, 'SiliconFlow': 2}
- `or:qwen3.6-35b-a3b`: {'DeepInfra': 283, 'AkashML': 252, 'Parasail': 77, 'CoreWeave': 32, 'AtlasCloud': 3, 'DekaLLM': 15, 'Darkbloom': 1, 'SiliconFlow': 1}
- `or:muse-glimmer-30b`: {'Together': 314, 'DeepInfra': 320}
- `or:gemma-4-31b`: {'CoreWeave': 382, 'DeepInfra': 195, 'ModelRun': 2}
- `or:gemma-4-31b+think-off`: {'CoreWeave': 387, 'DeepInfra': 186, 'ModelRun': 1, 'Io Net': 1}
- `or:qwen3-coder-30b-a3b`: {'SiliconFlow': 591}
- `or:qwen3-coder-30b-a3b+typed-prompt`: {'SiliconFlow': 404}
- `or:glm-4.7-flash+think-off+typed-prompt`: {'Cloudflare': 382, 'Novita': 12}
- `or:gpt-oss-120b`: {'CoreWeave': 92, 'Novita': 25, 'AkashML': 84, 'Mancer 2': 35, 'Near AI': 215, 'DekaLLM': 86, 'Crusoe': 30, 'BaseTen': 14, 'DeepInfra': 66, 'Parasail': 18, 'Groq': 3, 'Together': 4, 'Nebius': 7, 'Phala': 4, 'SiliconFlow': 3, 'Mara': 4}
- `or:gemma-4-26b-a4b+think-off`: {'DekaLLM': 101, 'Cloudflare': 42, 'Google': 8, 'Darkbloom': 142, 'NextBit': 93, 'SiliconFlow': 21, 'Makora': 108, 'CoreWeave': 41, 'Venice': 21, 'DeepInfra': 52, 'Parasail': 12, 'Novita': 10}
- `or:gemma-4-26b-a4b+think-off+typed-prompt`: {'DekaLLM': 55, 'Makora': 107, 'NextBit': 45, 'Venice': 7, 'Cloudflare': 37, 'Parasail': 12, 'Darkbloom': 87, 'DeepInfra': 35, 'CoreWeave': 23, 'SiliconFlow': 10, 'Google': 4, 'Novita': 1}
- `or:gemma-4-26b-a4b`: {'DekaLLM': 119, 'CoreWeave': 39, 'Makora': 88, 'Cloudflare': 28, 'SiliconFlow': 25, 'Darkbloom': 151, 'Parasail': 22, 'NextBit': 85, 'DeepInfra': 58, 'Venice': 17, 'Novita': 8, 'Google': 11}
- `or:gpt-oss-120b+think-low`: {'CoreWeave': 86, 'DeepInfra': 65, 'AkashML': 97, 'Novita': 28, 'Near AI': 189, 'DekaLLM': 102, 'Crusoe': 33, 'SiliconFlow': 6, 'Parasail': 23, 'Mancer 2': 35, 'Groq': 4, 'BaseTen': 17, 'Mara': 2, 'Together': 4, 'Phala': 6, 'Nebius': 3}
- `or:llama-3.3-70b`: {'DeepInfra': 358, 'AkashML': 157, 'Parasail': 84, 'SambaNova': 18, 'Cloudflare': 25, 'CoreWeave': 9, 'Groq': 10}
- `or:llama-3.3-70b+typed-prompt`: {'AkashML': 169, 'DeepInfra': 182, 'CoreWeave': 6, 'Cloudflare': 13, 'SambaNova': 5, 'Parasail': 30, 'Groq': 5}
- `or:gpt-oss-20b+think-low+typed-prompt`: {'CoreWeave': 46, 'DeepInfra': 14, 'Darkbloom': 129, 'Groq': 7, 'AkashML': 82, 'Parasail': 98, 'DekaLLM': 47, 'SiliconFlow': 17}
- `or:granite-4.2-8b`: {'DeepInfra': 516, 'CoreWeave': 138}
- `or:lfm2.5-24b-a2b`: {'Liquid': 662}
- `or:qwen3.6-35b-a3b+think-off+typed-prompt`: {'DeepInfra': 250, 'Parasail': 47, 'AkashML': 55, 'CoreWeave': 21, 'SiliconFlow': 2, 'DekaLLM': 6}
- `or:qwen3-coder-next`: {'Parasail': 548}
- `or:glm-4.7-flash+think-off`: {'Cloudflare': 606, 'Novita': 9}
- `or:glm-4.7-flash`: {'Cloudflare': 431, 'Novita': 10}
- `or:nemotron-3.5-lightning-30b-a3b+think-off`: {'CoreWeave': 201, 'DeepInfra': 403, 'Io Net': 70, 'Darkbloom': 13}
- `or:nemotron-3.5-lightning-30b-a3b`: {'CoreWeave': 209, 'DeepInfra': 351, 'Io Net': 84, 'Darkbloom': 14}
- `or:gpt-oss-20b+think-low`: {'Groq': 10, 'DeepInfra': 37, 'CoreWeave': 73, 'Darkbloom': 205, 'AkashML': 123, 'DekaLLM': 65, 'Parasail': 100, 'SiliconFlow': 18}
- `or:qwen2.5-coder-32b`: {'Cloudflare': 705}
- `or:ministral-3-14b`: {'Mistral': 725}
- `or:qwen2.5-coder-32b+typed-prompt`: {'Cloudflare': 507}
- `or:gpt-oss-20b`: {'Parasail': 91, 'AkashML': 87, 'Darkbloom': 175, 'DekaLLM': 54, 'Groq': 17, 'CoreWeave': 85, 'DeepInfra': 31, 'SiliconFlow': 6}

Role signals: planner/walkthrough need strict JSON; output tokens per review drive P40 latency
(decode is bandwidth-bound, so time is roughly out-tokens / tg-rate).

| config | planner repairs/case | planner fail | reviewer repairs/case | reviewer fail | walkthrough fail | out tok/review (P / R / W) | in tok/review |
|---|---|---|---|---|---|---|---|
| `ref:deepseek-v4.1-flash` | 0.99 | 1% | 0.86 | 2% | 0% | 10635 / 19435 / 420 | 12898 |
| `or:qwen3.8-27b` | 0.97 | 0% | 0.98 | 1% | 0% | 2358 / 15600 / 864 | 13545 |
| `ref:deepseek-v4-pro` | 0.83 | 3% | 0.76 | 7% | 0% | 1551 / 8091 / 546 | 10813 |
| `or:qwen3.8-27b+think-off+typed-prompt` | 0.00 | 0% | 0.01 | 0% | 0% | 167 / 727 / 276 | 11185 |
| `or:qwen3.8-27b+think-off+calibrated-prompt` | 0.00 | 0% | 0.02 | 0% | 0% | 163 / 654 / 267 | 11400 |
| `ref:deepseek-v4.1-flash+think-off` | 0.99 | 0% | 0.91 | 1% | 0% | 793 / 4671 / 263 | 13023 |
| `or:qwen3.8-27b+think-off` | 1.00 | 0% | 0.71 | 1% | 0% | 511 / 1405 / 264 | 12109 |
| `ref:deepseek-v4-pro+think-off` | 0.89 | 0% | 1.07 | 4% | 0% | 444 / 2487 / 263 | 12195 |
| `or:qwen3.6-27b+think-off` | 1.00 | 0% | 0.83 | 2% | 0% | 584 / 2868 / 254 | 12442 |
| `or:qwen3.6-27b` | 0.97 | 0% | 0.96 | 0% | 0% | 3311 / 8270 / 1967 | 12684 |
| `or:qwen3.6-35b-a3b+think-off` | 0.95 | 1% | 0.96 | 1% | 0% | 452 / 2933 / 270 | 12695 |
| `or:qwen3.6-35b-a3b` | 0.98 | 0% | 0.97 | 1% | 0% | 4189 / 9736 / 1957 | 12354 |
| `or:muse-glimmer-30b` | 0.96 | 0% | 0.74 | 0% | 0% | 2184 / 5205 / 652 | 11427 |
| `or:gemma-4-31b` | 0.79 | 0% | 0.50 | 0% | 0% | 366 / 789 / 205 | 12478 |
| `or:gemma-4-31b+think-off` | 0.79 | 0% | 0.47 | 0% | 0% | 360 / 824 / 206 | 12476 |
| `or:qwen3-coder-30b-a3b` | 1.01 | 0% | 0.36 | 0% | 0% | 342 / 1112 / 206 | 10954 |
| `or:qwen3-coder-30b-a3b+typed-prompt` | 0.00 | 0% | 0.01 | 1% | 0% | 143 / 707 / 202 | 10361 |
| `or:glm-4.7-flash+think-off+typed-prompt` | 0.00 | 0% | 0.07 | 7% | 0% | 149 / 1139 / 174 | 9529 |
| `or:gpt-oss-120b` | 1.14 | 1% | 1.08 | 7% | 0% | 1175 / 3354 / 389 | 11698 |
| `or:gemma-4-26b-a4b+think-off` | 1.00 | 0% | 0.76 | 0% | 0% | 396 / 2202 / 221 | 12922 |
| `or:gemma-4-26b-a4b+think-off+typed-prompt` | 0.00 | 0% | 0.10 | 1% | 0% | 142 / 1613 / 216 | 12059 |
| `or:gemma-4-26b-a4b` | 1.00 | 0% | 0.74 | 0% | 0% | 398 / 1245 / 230 | 12923 |
| `or:gpt-oss-120b+think-low` | 1.13 | 1% | 1.16 | 8% | 0% | 566 / 2645 / 247 | 11377 |
| `or:llama-3.3-70b` | 1.03 | 1% | 0.94 | 4% | 0% | 123 / 692 / 202 | 10051 |
| `or:llama-3.3-70b+typed-prompt` | 0.00 | 1% | 0.13 | 2% | 0% | 86 / 382 / 195 | 9711 |
| `or:gpt-oss-20b+think-low+typed-prompt` | 0.13 | 1% | 0.19 | 4% | 0% | 553 / 1411 / 295 | 10376 |
| `or:granite-4.2-8b` | 1.05 | 0% | 0.87 | 5% | 0% | 4250 / 10693 / 2060 | 12167 |
| `or:lfm2.5-24b-a2b` | 0.83 | 0% | 1.06 | 0% | 0% | 6710 / 11276 / 1933 | 11741 |
| `or:qwen3.6-35b-a3b+think-off+typed-prompt` | 0.00 | 0% | 0.03 | 10% | 0% | 170 / 1140 / 249 | 10225 |
| `or:qwen3-coder-next` | 0.33 | 4% | 1.22 | 28% | 0% | 430 / 3332 / 158 | 10837 |
| `or:glm-4.7-flash+think-off` | 0.96 | 4% | 0.89 | 10% | 0% | 544 / 2038 / 162 | 10478 |
| `or:glm-4.7-flash` | 0.84 | 2% | 0.47 | 49% | 0% | 2817 / 3093 / 556 | 7043 |
| `or:nemotron-3.5-lightning-30b-a3b+think-off` | 0.87 | 1% | 1.64 | 41% | 0% | 674 / 4719 / 172 | 12100 |
| `or:nemotron-3.5-lightning-30b-a3b` | 0.84 | 1% | 1.30 | 25% | 0% | 1545 / 7614 / 865 | 11738 |
| `or:gpt-oss-20b+think-low` | 1.06 | 7% | 0.94 | 11% | 0% | 466 / 1887 / 178 | 10186 |
| `or:qwen2.5-coder-32b` | 1.04 | 4% | 1.64 | 53% | 0% | 229 / 1702 / 120 | 9773 |
| `or:ministral-3-14b` | 1.00 | 0% | 1.86 | 49% | 0% | 984 / 5284 / 152 | 14048 |
| `or:qwen2.5-coder-32b+typed-prompt` | 0.00 | 0% | 1.09 | 50% | 0% | 87 / 1258 / 148 | 9752 |
| `or:gpt-oss-20b` | 1.04 | 10% | 0.64 | 18% | 0% | 2096 / 5267 / 390 | 8732 |

Prompt fix A/B (`+typed-prompt` adds field types and allowed values to the planner and
reviewer system prompts; everything else identical). Δ = typed − production.

| config | strict | Δ strict | ok Δ | planner repairs/case | reviewer repairs/case | calls/review | out tok/review |
|---|---|---|---|---|---|---|---|
| `or:qwen3.8-27b+think-off` | 50 → 57 | +7 | +1 | 1.00 → 0.00 | 0.71 → 0.01 | 4.71 → 3.01 | 2181 → 1169 |
| `or:qwen3.8-27b+think-off` | 50 → 52 | +2 | +1 | 1.00 → 0.00 | 0.71 → 0.02 | 4.71 → 3.02 | 2181 → 1084 |
| `or:qwen3-coder-30b-a3b` | 28 → 22 | -6 | -1 | 1.01 → 0.00 | 0.36 → 0.01 | 4.38 → 3.01 | 1660 → 1052 |
| `or:glm-4.7-flash+think-off` | 22 → 22 | +0 | +7 | 0.96 → 0.00 | 0.89 → 0.07 | 4.84 → 3.07 | 2744 → 1462 |
| `or:gemma-4-26b-a4b+think-off` | 20 → 20 | +0 | -1 | 1.00 → 0.00 | 0.76 → 0.10 | 4.82 → 3.15 | 2819 → 1971 |
| `or:llama-3.3-70b` | 11 → 8 | -3 | +1 | 1.03 → 0.00 | 0.94 → 0.13 | 4.99 → 3.13 | 1017 → 663 |
| `or:gpt-oss-20b+think-low` | 6 → 7 | +1 | +14 | 1.06 → 0.13 | 0.94 → 0.19 | 5.01 → 3.34 | 2531 → 2258 |
| `or:qwen3.6-35b-a3b+think-off` | 41 → 40 | -1 | -7 | 0.95 → 0.00 | 0.96 → 0.03 | 4.90 → 3.03 | 3655 → 1560 |
| `or:qwen2.5-coder-32b` | 4 → 3 | -1 | +7 | 1.04 → 0.00 | 1.64 → 1.09 | 5.83 → 4.25 | 2051 → 1493 |

Per-operator detection (pooled over reps):

- `ref:deepseek-v4.1-flash`: {'bool_flip': '15/15', 'cmp_flip': '13/15', 'drop_await': '11/15', 'hardcoded_secret': '23/24', 'return_flip': '7/12', 'tls_off': '9/9'}
- `or:qwen3.8-27b`: {'bool_flip': '12/15', 'cmp_flip': '13/15', 'drop_await': '12/15', 'hardcoded_secret': '23/24', 'return_flip': '7/12', 'tls_off': '9/9'}
- `ref:deepseek-v4-pro`: {'bool_flip': '12/15', 'cmp_flip': '12/15', 'drop_await': '9/15', 'hardcoded_secret': '21/24', 'return_flip': '8/12', 'tls_off': '9/9'}
- `or:qwen3.8-27b+think-off+typed-prompt`: {'bool_flip': '13/15', 'cmp_flip': '12/15', 'drop_await': '9/15', 'hardcoded_secret': '24/24', 'return_flip': '3/12', 'tls_off': '9/9'}
- `or:qwen3.8-27b+think-off+calibrated-prompt`: {'bool_flip': '10/15', 'cmp_flip': '11/15', 'drop_await': '2/15', 'hardcoded_secret': '24/24', 'return_flip': '3/12', 'tls_off': '9/9'}
- `ref:deepseek-v4.1-flash+think-off`: {'bool_flip': '15/15', 'cmp_flip': '14/15', 'drop_await': '10/15', 'hardcoded_secret': '21/24', 'return_flip': '5/12', 'tls_off': '8/9'}
- `or:qwen3.8-27b+think-off`: {'bool_flip': '13/15', 'cmp_flip': '12/15', 'drop_await': '6/15', 'hardcoded_secret': '24/24', 'return_flip': '3/12', 'tls_off': '9/9'}
- `ref:deepseek-v4-pro+think-off`: {'bool_flip': '14/15', 'cmp_flip': '12/15', 'drop_await': '6/15', 'hardcoded_secret': '21/24', 'return_flip': '6/12', 'tls_off': '9/9'}
- `or:qwen3.6-27b+think-off`: {'bool_flip': '11/15', 'cmp_flip': '12/15', 'drop_await': '1/15', 'hardcoded_secret': '23/24', 'return_flip': '4/12', 'tls_off': '8/9'}
- `or:qwen3.6-27b`: {'bool_flip': '12/15', 'cmp_flip': '10/15', 'drop_await': '7/15', 'hardcoded_secret': '24/24', 'return_flip': '9/12', 'tls_off': '8/9'}
- `or:qwen3.6-35b-a3b+think-off`: {'bool_flip': '6/15', 'cmp_flip': '12/15', 'drop_await': '2/15', 'hardcoded_secret': '19/24', 'return_flip': '2/12', 'tls_off': '9/9'}
- `or:qwen3.6-35b-a3b`: {'bool_flip': '10/15', 'cmp_flip': '11/15', 'drop_await': '6/15', 'hardcoded_secret': '17/24', 'return_flip': '7/12', 'tls_off': '8/9'}
- `or:muse-glimmer-30b`: {'bool_flip': '15/15', 'cmp_flip': '13/15', 'drop_await': '10/15', 'hardcoded_secret': '20/24', 'return_flip': '2/12', 'tls_off': '9/9'}
- `or:gemma-4-31b`: {'bool_flip': '9/15', 'cmp_flip': '12/15', 'drop_await': '3/15', 'hardcoded_secret': '21/24', 'return_flip': '1/12', 'tls_off': '9/9'}
- `or:gemma-4-31b+think-off`: {'bool_flip': '8/15', 'cmp_flip': '10/15', 'drop_await': '3/15', 'hardcoded_secret': '20/24', 'return_flip': '3/12', 'tls_off': '9/9'}
- `or:qwen3-coder-30b-a3b`: {'bool_flip': '5/15', 'cmp_flip': '15/15', 'drop_await': '4/15', 'hardcoded_secret': '15/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:qwen3-coder-30b-a3b+typed-prompt`: {'bool_flip': '3/15', 'cmp_flip': '14/15', 'drop_await': '2/15', 'hardcoded_secret': '15/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:glm-4.7-flash+think-off+typed-prompt`: {'bool_flip': '7/15', 'cmp_flip': '8/15', 'drop_await': '1/15', 'hardcoded_secret': '14/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:gpt-oss-120b`: {'bool_flip': '6/15', 'cmp_flip': '9/15', 'drop_await': '7/15', 'hardcoded_secret': '15/24', 'return_flip': '1/12', 'tls_off': '9/9'}
- `or:gemma-4-26b-a4b+think-off`: {'bool_flip': '8/15', 'cmp_flip': '12/15', 'drop_await': '0/15', 'hardcoded_secret': '17/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:gemma-4-26b-a4b+think-off+typed-prompt`: {'bool_flip': '4/15', 'cmp_flip': '12/15', 'drop_await': '2/15', 'hardcoded_secret': '9/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:gemma-4-26b-a4b`: {'bool_flip': '5/15', 'cmp_flip': '11/15', 'drop_await': '0/15', 'hardcoded_secret': '15/24', 'return_flip': '0/12', 'tls_off': '9/9'}
- `or:gpt-oss-120b+think-low`: {'bool_flip': '5/15', 'cmp_flip': '7/15', 'drop_await': '6/15', 'hardcoded_secret': '12/24', 'return_flip': '0/12', 'tls_off': '5/9'}
- `or:llama-3.3-70b`: {'bool_flip': '2/15', 'cmp_flip': '2/15', 'drop_await': '0/15', 'hardcoded_secret': '6/24', 'return_flip': '1/12', 'tls_off': '6/9'}
- `or:llama-3.3-70b+typed-prompt`: {'bool_flip': '2/15', 'cmp_flip': '3/15', 'drop_await': '0/15', 'hardcoded_secret': '5/24', 'return_flip': '0/12', 'tls_off': '6/9'}
- `or:gpt-oss-20b+think-low+typed-prompt`: {'bool_flip': '5/15', 'cmp_flip': '6/15', 'drop_await': '8/15', 'hardcoded_secret': '4/24', 'return_flip': '0/12', 'tls_off': '3/9'}
- `or:granite-4.2-8b`: {'bool_flip': '5/15', 'cmp_flip': '7/15', 'drop_await': '0/15', 'hardcoded_secret': '8/24', 'return_flip': '2/12', 'tls_off': '7/9'}
- `or:lfm2.5-24b-a2b`: {'bool_flip': '3/15', 'cmp_flip': '2/15', 'drop_await': '0/15', 'hardcoded_secret': '1/24', 'return_flip': '0/12', 'tls_off': '3/9'}
- `or:qwen3.6-35b-a3b+think-off+typed-prompt`: {'bool_flip': '6/15', 'cmp_flip': '14/15', 'drop_await': '2/15', 'hardcoded_secret': '18/24', 'return_flip': '4/12', 'tls_off': '7/9'}
- `or:qwen3-coder-next`: {'bool_flip': '8/15', 'cmp_flip': '7/15', 'drop_await': '3/15', 'hardcoded_secret': '12/24', 'return_flip': '4/12', 'tls_off': '6/9'}
- `or:glm-4.7-flash+think-off`: {'bool_flip': '6/15', 'cmp_flip': '11/15', 'drop_await': '0/15', 'hardcoded_secret': '13/24', 'return_flip': '0/12', 'tls_off': '8/9'}
- `or:glm-4.7-flash`: {'bool_flip': '5/15', 'cmp_flip': '7/15', 'drop_await': '0/15', 'hardcoded_secret': '10/24', 'return_flip': '1/12', 'tls_off': '5/9'}
- `or:nemotron-3.5-lightning-30b-a3b+think-off`: {'bool_flip': '4/15', 'cmp_flip': '8/15', 'drop_await': '0/15', 'hardcoded_secret': '8/24', 'return_flip': '1/12', 'tls_off': '5/9'}
- `or:nemotron-3.5-lightning-30b-a3b`: {'bool_flip': '5/15', 'cmp_flip': '9/15', 'drop_await': '1/15', 'hardcoded_secret': '4/24', 'return_flip': '0/12', 'tls_off': '2/9'}
- `or:gpt-oss-20b+think-low`: {'bool_flip': '4/15', 'cmp_flip': '5/15', 'drop_await': '5/15', 'hardcoded_secret': '1/24', 'return_flip': '0/12', 'tls_off': '3/9'}
- `or:qwen2.5-coder-32b`: {'bool_flip': '1/15', 'cmp_flip': '4/15', 'drop_await': '0/15', 'hardcoded_secret': '2/24', 'return_flip': '1/12', 'tls_off': '1/9'}
- `or:ministral-3-14b`: {'bool_flip': '2/15', 'cmp_flip': '0/15', 'drop_await': '3/15', 'hardcoded_secret': '5/24', 'return_flip': '0/12', 'tls_off': '6/9'}
- `or:qwen2.5-coder-32b+typed-prompt`: {'bool_flip': '0/15', 'cmp_flip': '5/15', 'drop_await': '0/15', 'hardcoded_secret': '3/24', 'return_flip': '0/12', 'tls_off': '6/9'}
- `or:gpt-oss-20b`: {'bool_flip': '3/15', 'cmp_flip': '6/15', 'drop_await': '4/15', 'hardcoded_secret': '8/24', 'return_flip': '0/12', 'tls_off': '8/9'}

Speculative-decoding guard: speculative variants must match their baseline's
accuracy within the rep range (decoding is lossless); a drop means a serving bug.
