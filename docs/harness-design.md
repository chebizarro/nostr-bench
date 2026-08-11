# Open-Weight Model Test Harness — Design Doc

**Companion to:** *Running the frontier at home* (2026-07-20)
**Status:** Draft for review · 2026-08-11
**Goal:** Identify the best bang-for-buck open-weight model (or model *combination*) for nostr-domain work and security work, across three ways of driving a model — one-shot prompting, an agent harness, and multi-model orchestration (Repo Prompt CE) — with a recommended pick for **cloud-run** (OpenRouter / Routstr) and **locally run**.

---

## 1. Research questions

The harness exists to answer four questions, in decreasing order of importance:

1. **Accuracy:** Which models actually *know* nostr — the NIP-01 serialization rules, bech32 entities, tag semantics — and which merely pattern-match? Same question for security judgment.
2. **Harness sensitivity:** How much does the *mode* matter? Does a mid-tier model in an agent loop (where it can run tests and self-correct) beat a frontier model one-shotting? Does a Repo Prompt oracle/editor pairing beat either?
3. **Ease of prompting:** How much prompt engineering does each model need before it performs? A model that scores 85 from a one-line ask beats a model that scores 90 only after a 400-word spec.
4. **Bang-for-buck:** Score per dollar (cloud) and score per wall-clock-hour on owned hardware (local). The output is two shortlists: best cloud pick, best local pick, plus the best *pairing* if orchestration wins.

## 2. Model roster

Full article roster plus two additions: **Muse Glimmer 30B** ([released by Meta yesterday](https://research.meta.ai/blog/introducing-muse-glimmer-open-agentic-model) — Apache 2.0, 30B, explicitly tuned for agentic tool use and LLM-as-judge work, <20 GB at 4-bit, already on [OpenRouter](https://openrouter.ai/meta/muse-glimmer-30b) and [Ollama](https://ollama.com/library/muse-glimmer)) and **DeepSeek V4 Flash** (the cheapest credible agentic model on the market at ~$0.054/$0.242 per M tokens — it would be malpractice to run a bang-for-buck study without it).

| # | Model | Tier | Cloud (OpenRouter/Routstr) | Local (realistic) | Indicative cloud price in/out per M† |
|---|---|---|---|---|---|
| 1 | DeepSeek V4 Pro | Frontier | ✓ | ✗ (0.8 TB) | ~$1.74 / $3.48 |
| 2 | Kimi K2.6 | Frontier | ✓ | ✗ for most | ~$0.58 / $2.44 |
| 3 | GLM-5.2 | Frontier | ✓ | ✗ for most | ~$0.45 / $3.31 |
| 4 | DeepSeek V4 Flash | Value cloud | ✓ | ✗ | ~$0.05 / $0.24 |
| 5 | Qwen3.5-397B | Upper-mid | ✓ | Marginal (256 GB unified) | ~$0.5–1 / $1.5–3 |
| 6 | gpt-oss-120b | Mid | ✓ | ✓ (96 GB card / 128 GB unified) | ~$0.1 / $0.5 |
| 7 | Llama 3.3 70B | Mid (dense, old) | ✓ | ✓ (48 GB) | ~$0.1 / $0.4 |
| 8 | **Muse Glimmer 30B** | Small-agentic | ✓ (new) | ✓ (24 GB card — fits one P40) | TBD (fresh listing) |
| 9 | Gemma 4 31B | Small | ✓ | ✓ (24 GB) | ~$0.1 / $0.3 |
| 10 | Qwen3.6 35B-A3B | Small-MoE | ✓ | ✓ (24 GB) | ~$0.1 / $0.3 |
| 11 | gpt-oss-20b | Floor | ✓ | ✓ (16 GB) | ~$0.05 / $0.2 |

† Prices to be captured live at run time by the harness (OpenRouter returns cost per request in the `usage` field; Routstr debits sats per token). The table is for planning only. Routstr availability ebbs with who's announcing — the harness treats Routstr as an *alternative transport* for whichever roster models happen to be offered that day, and records which ones were.

**Local baseline hardware:** your P40 rig (2× 24 GB) covers models 8–11 and Llama 70B split across both cards. gpt-oss-120b and Qwen3.5-397B need the bigger boxes from the article's table; they stay in the cloud arm unless you have access to one. Local runs are via **llama.cpp / Ollama serving an OpenAI-compatible endpoint**, so the harness code is identical for cloud and local — only the base URL changes. Quantization is pinned and recorded per run (Q4_K_M as default; Muse Glimmer's official K-Quant 4-bit).

## 3. The matrix: three modes

All three modes consume the same task definitions and the same grader. A mode is just a *driver*.

### Mode A — One-shot prompt
Single completion, no tools, no retries. The model gets the task statement (+ any provided code files inlined) and must return complete code/findings in one reply. Grader extracts fenced code blocks and runs the hidden test suite.

### Mode B — Agent harness
A deliberately minimal, pinned reference agent (~200 LOC Python, part of the harness — not an external product, so results aren't confounded by someone else's system prompt churn). OpenAI-compatible tool-calling loop with exactly four tools: `read_file`, `write_file`, `run` (sandboxed shell, can execute the *visible* half of the test suite), and `done`. Caps: 25 turns, 300s wall clock, token budget recorded. This measures what the article calls the thing you actually want — can the model drive itself, use tests as feedback, and recover from failure?

### Mode C — Multi-model orchestration (Repo Prompt CE)
The mode Repo Prompt CE is built for: **context engineering plus role-split models.** Driven over its MCP server (`context_builder`, `oracle_send`, `agent_run`, `apply_edits`, `manage_worktree`), each task repo opened as a workspace, one app-managed worktree per run. Two sub-configurations:

- **C1 — Oracle/editor pairing:** a strong "architect" model gets curated context and produces the plan/diff spec (`oracle_send`); a cheap fast "editor" model applies the edits. Pairings to test: GLM-5.2 → gpt-oss-20b, Kimi K2.6 → Qwen3.6, DeepSeek V4 Flash → Muse Glimmer, and the all-local pairing Muse Glimmer → gpt-oss-20b (Glimmer is explicitly marketed for exactly this planner/judge role).
- **C2 — Context-engineered single model:** same model as Mode B, but Repo Prompt's Context Builder curates the context first. Isolates how much of orchestration's win is *context quality* vs. *role splitting*.

## 4. Task suites

Four suites, all repo-shaped (a directory the model/agent works in), all graded by hidden tests plus a rubric. **All task code is TypeScript** — it's the language with the strongest nostr ecosystem (nostr-tools, NDK, the reference implementations most models trained on), so it tests the models where their corpus is deepest rather than penalizing them with a translation step. Node 22 + vitest for grading; strict `tsconfig`. Nostr is a good discriminator precisely because the canonical rules are strict and poorly represented in training data relative to, say, React.

### N1 — Implement a nostr feature (from scratch)
Two independent sub-tasks, TypeScript, no nostr libraries allowed (`nostr-tools`/`ndk` banned; the `@noble/curves` secp256k1 primitive allowed):

- **N1a: NIP-01 event core.** `compute_event_id`, `sign_event`, `verify_event`. Graded against known-good vectors including the traps: canonical serialization as `[0, pubkey, created_at, kind, tags, content]` with no whitespace, correct UTF-8 handling, the exact character-escaping rules, BIP-340 Schnorr (not ECDSA), lowercase hex.
- **N1b: NIP-19 entities.** bech32 encode/decode for `npub`/`nsec`/`note` plus TLV for `nprofile`/`nevent`. Graded against vectors including relay-hint TLVs and invalid-checksum rejection.

Score: hidden vitest pass rate (70%) + property checks e.g. round-tripping, rejection of malformed input (30%).

### N2 — Debug/extend real nostr code
A ~500-line working-but-wrong mini relay + client library (TypeScript, `ws`-based) with **5 planted protocol bugs**, e.g.: event ID computed by `JSON.stringify` of the event *object* (key order + extra fields) instead of the canonical `[0, pubkey, ...]` array; `created_at` populated from `Date.now()` (milliseconds) instead of Unix seconds; `#e` tag filter matching against all tags; `since`/`until` inverted; signature checked against the *claimed* id rather than the recomputed one. Task: "clients report events rejected by other relays — find and fix the protocol violations." Score: bugs fixed (each verified by a targeted hidden test) minus regressions on the passing visible suite.

### S1 — Seeded vulnerability audit (general security)
~800-line Express (TypeScript) service with **8 planted vulns** (SQLi via string-built query, path traversal, JWT `alg=none`, SSRF in webhook fetch, timing-unsafe token compare, missing authz on one route, prototype pollution via a recursive merge of user JSON, weak password hashing) and **3 deliberate red herrings** that look scary but are safe. Output format: structured findings (JSON). Score: recall (found/8) × precision penalty for flagging red herrings or hallucinated vulns. Precision matters — a model that cries wolf on everything is expensive to work with.

### S2 — Nostr-flavored security audit
Where the two domains overlap and generic security training doesn't help: a ~400-line TypeScript nostr bot + NIP-47 wallet-connect handler with planted issues — `nsec` written to log, NIP-04 used where NIP-44 is required (no auth tag → malleability), events processed before signature verification, no `created_at` window or event-id dedup (replay), relay URL taken from user input and fetched (SSRF into local network), `nsec` accepted via query parameter. Scored like S1. This suite is the sharpest test of the study's core question: does the model's nostr knowledge and security sense *compose*?

## 5. Ease-of-prompting: measured, not vibes

Every (model × mode × task) cell runs at **two prompt tiers**:

- **T1 terse:** one or two sentences, the way you'd actually type it. "Implement NIP-19 encode/decode for these entity types, tests in tests/."
- **T2 engineered:** full spec — requirements enumerated, edge cases named, output format dictated, relevant NIP text excerpted.

**Prompt sensitivity = score(T2) − score(T1).** Low sensitivity + high T1 score = the model "just gets it" — that's the ease-of-prompting winner. Secondary ease signals recorded per run: format-compliance failures (code not extractable, JSON findings malformed), agent-mode turns used, and tool-call error rate.

## 6. Scoring and the bang-for-buck metric

Per run we record: task score (0–100), tokens in/out, measured cost (cloud: provider-reported $ or sats; local: wall-clock × the rig's marginal $/hr — electricity + amortization, defaulting to $0.15/hr for the P40 box), wall-clock, turns, failures. Each cell is run **n=3** (temperature 0.2) and reported as median with range — single runs of agentic tasks are noise.

Headline metrics:

- **Accuracy:** mean of the four suite scores (nostr pair and security pair also reported separately).
- **Ease:** T1 score and prompt sensitivity.
- **Bang-for-buck (cloud):** accuracy points per dollar per task, at the model's best mode.
- **Bang-for-buck (local):** accuracy points per hour on the reference rig, plus a simple "fits your hardware: yes/no."
- **Pairing verdict:** best Mode C pairing vs. best single model at equal cost.

Grading is deterministic (vitest, JSON diff against the planted-vuln answer key) everywhere possible. The only judged component is audit finding *descriptions* (is the writeup actionable?), scored by a **fixed judge model** (a strong closed frontier model, pinned version, rubric in the repo) that never appears in the roster — judge bias toward its own family is a known failure mode.

## 7. Fairness controls

Same task files, same prompts, same tool schemas, same caps for every model. Temperature 0.2, top-p default, seed recorded. Local quant pinned and reported next to every local score (a Q4 model losing to its own cloud FP8 self is a *finding*, not noise — it's exactly the sovereignty tax the article is about). Context window capped at 128k for all (lowest common denominator across roster). No model-specific system prompts except the provider-required chat template. All artifacts (transcripts, diffs, grades) archived per run for audit.

## 8. Phased run plan (cost control)

Full matrix naively = 11 models × 3 modes × 4 suites × 2 tiers × 3 reps ≈ 800 runs. We don't run that. Phases prune:

1. **Phase 1 — One-shot screen (all 11 models):** 11 × 4 suites × 2 tiers × 3 reps = 264 short runs. Estimated ~5M tokens total ≈ **$10–25** on OpenRouter, an afternoon. Produces the raw-knowledge leaderboard.
2. **Phase 2 — Agent harness (top ~6 + all locals):** every model that either scored ≥ threshold in Phase 1 or runs on 24 GB (the local contingent is the point of the study, so it always advances). ~6–8 models × 4 suites × 2 tiers × 3 reps of long agentic runs ≈ 15–30M tokens ≈ **$40–120** cloud; local runs cost only time.
3. **Phase 3 — Repo Prompt CE (4 pairings + 2 C2 controls):** runs on your Mac against cloud and local endpoints. ~150 orchestrated runs' worth of oracle calls, dominated by the oracle model's pricing ≈ **$30–80**.
4. **Phase 4 — Report:** results dashboard (HTML) + a follow-up article's worth of tables: the two shortlists, the mode-sensitivity finding, and where Muse Glimmer actually lands versus Meta's launch-day claims.

Total cloud budget estimate: **$80–225.** Routstr arm adds whatever sats you allocate; it reruns Phase 1 only (transport comparison, not a new matrix dimension).

## 9. Harness repo layout

```
nostr-bench/
├── tasks/
│   ├── n1_implement/      # task.md (T1+T2), starter files, tests_visible/, tests_hidden/
│   ├── n2_debug/          # buggy repo, bug answer key, hidden regression tests
│   ├── s1_audit/          # vulnerable service, vulns.json answer key, red_herrings.json
│   └── s2_nostr_sec/      # bot + NIP-47 handler, answer key
├── drivers/
│   ├── oneshot.py         # Mode A
│   ├── microagent.py      # Mode B: pinned 4-tool loop
│   └── repoprompt.py      # Mode C: drives RP-CE over MCP (oracle_send / apply_edits / worktrees)
├── providers/             # openrouter.py, routstr.py (cashu token auth), local.py — one interface
├── grade/                 # extractors, sandboxed node/vitest runner, findings scorer, judge rubric
├── runmatrix.yaml         # roster, modes, tiers, reps, caps, prices
└── report/                # aggregation → results.html dashboard
```

Sandboxing note: graded code and agent `run` calls execute in a no-network container (or `firejail`) — S1/S2 deliberately contain exploitable code, and Mode B hands models a shell.

## 10. Risks and honest caveats

**Contamination:** planted bugs and vulns must be authored fresh, not copied from CTF corpora these models trained on. Test vectors for N1 will be generated, not lifted from nostr-tools' test suite verbatim (models have read that repo).
**Tool-calling variance:** some open models' tool-calling is template-fragile; Mode B failures may measure the provider's chat template rather than the model. Mitigation: record tool-call parse errors separately from task failure, and use each provider's native tool API.
**Muse Glimmer freshness:** day-one serving stacks are often broken (chat template bugs, wrong EOS). If Glimmer's early numbers look anomalous, rerun after the first llama.cpp/Ollama patch cycle before drawing conclusions.
**Repo Prompt CE mode is macOS-bound** and semi-interactive; Phase 3 is the least automatable arm and will need you at the keyboard for the first runs while we script the MCP flow.
**n=3 is small.** It bounds cost, but close calls (≤5 points) should be treated as ties, and the report will say so.

## 11. What you get at the end

A ranked answer to the original question in four lines: best cloud model, best local model, best pairing, and whether the agent harness or orchestration changes the ranking enough to matter — each with the measured $/task or tok/s to back it. Plus every transcript, so the follow-up article can quote models being confidently wrong about NIP-01 serialization, which, let's be honest, is half the fun.

---

*Next step on approval: I scaffold `nostr-bench/`, author the four task suites and answer keys, build the three drivers, and hand you a repo where `make phase1` runs against your OpenRouter key.*
