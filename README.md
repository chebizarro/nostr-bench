# nostr-bench

[![CI](https://github.com/chebizarro/nostr-bench/actions/workflows/ci.yml/badge.svg)](https://github.com/chebizarro/nostr-bench/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![nostr](https://img.shields.io/badge/nostr-NIP--34_ready-8e44ad)

**Bring your own protocol.** A test harness for comparing open-weight models on
**nostr-domain** and **security** work — because an unfamiliar protocol is a
proxy for any codebase a model didn't marinate in. Companion write-up:
[`docs/bring-your-own-protocol.md`](docs/bring-your-own-protocol.md). To publish
this repo to GitHub and Nostr, see [`PUBLISHING.md`](PUBLISHING.md).

It compares models across three ways of driving them:

- **Mode A — one-shot prompt** (`drivers/oneshot.py`)
- **Mode B — agent harness** (`drivers/microagent.py`, a pinned 4-tool loop)
- **Mode C — multi-model orchestration** via Repo Prompt CE (`drivers/repoprompt.py`)

Companion to the article *Running the frontier at home*. Design rationale lives in
[`docs/harness-design.md`](docs/harness-design.md).

## What it measures

For each `(model × mode × task × prompt-tier)` cell it records a task score (0–100),
tokens, measured cost, wall-clock, and agent turns — then rolls those up into:
accuracy, prompt sensitivity (ease of prompting), and bang-for-buck for **cloud**
(points/$) and **local** (points/hour on your own rig).

## Task suites (all TypeScript, Node 22 + vitest)

| id | what | grading |
|----|------|---------|
| `n1_implement` | Implement NIP-01 event core + NIP-19 entities from scratch (no nostr libs) | hidden vitest vectors |
| `n2_debug` | Find & fix 5 planted protocol bugs in a mini relay/client | targeted regression tests |
| `s1_audit` | Audit an Express service: 8 planted vulns + 3 red herrings | recall × precision |
| `s2_nostr_sec` | Audit a nostr bot + NIP-47 handler: nostr-flavored vulns | recall × precision |

## Quick start

```bash
# 1. Python deps for the harness (drivers/providers/grader)
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# 2. Node toolchain for grading task code (Node 22+)
#    each task dir is a self-contained npm project; the grader installs on first run

# 3. Point at a provider
export OPENROUTER_API_KEY=sk-or-...          # cloud arm
export LOCAL_BASE_URL=http://localhost:11434/v1   # llama.cpp / Ollama for the local arm
export ROUTSTR_BASE_URL=...  ROUTSTR_CASHU_TOKEN=cashuA...   # optional sovereign arm

# 4. Run a single cell to sanity-check wiring
python -m drivers.oneshot --model openai/gpt-oss-20b --task n1_implement --tier T1

# 5. Run a phase from the matrix
make phase1    # one-shot screen, all models, all suites, both tiers, n=3
```

## Layout

```
nostr-bench/
├── tasks/            # the four suites: task.md (T1+T2), starter, tests_visible/, tests_hidden/, answer keys
├── drivers/          # oneshot.py (A), microagent.py (B), repoprompt.py (C)
├── providers/        # openrouter.py, routstr.py, local.py — one OpenAI-compatible interface
├── grade/            # code extraction, sandboxed vitest runner, findings scorer, LLM judge
├── report/           # aggregate runs/*.json → results.html dashboard
├── runmatrix.yaml    # roster, modes, tiers, reps, caps, prices
└── runs/             # per-cell result JSON + archived transcripts (created at run time)
```

## Safety

S1/S2 contain deliberately exploitable code, and Mode B hands the model a shell.
All graded code and agent `run` calls execute in a **no-network sandbox**
(`grade/sandbox.py` uses a container if available, else `firejail`, else refuses
unless `NOSTR_BENCH_ALLOW_UNSANDBOXED=1`). Never run this harness with live
credentials mounted in the working tree.

## Status

Scaffold. `n1_implement` is fully authored end-to-end (starter, visible + hidden
tests, answer key). `n2/s1/s2` ship with their vulnerable/buggy code, answer keys,
and representative tests; expand the hidden suites before a scored run. Drivers A
and B are functional against any OpenAI-compatible endpoint; driver C is a
scripted skeleton over the Repo Prompt CE MCP server (see its header).
