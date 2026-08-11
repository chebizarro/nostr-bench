---
title: "Bring your own protocol"
description: "Meta's Muse Glimmer runs a frontier-ish agent on a single consumer GPU. So I built a harness to ask the only question that matters to me: can it do nostr — and can a $1000 box of old cards do real agentic coding? A field report on open weights, an unfamiliar protocol, and the orchestration trick that makes cheap models punch up."
date: "2026-08-11"
tags: ["sovereignty", "llm", "nostr", "self-hosting", "agents", "security"]
featured: true
heroImage: "/images/bring-your-own-protocol.png"
ogImage: "/og-images/bring-your-own-protocol.png"
---

> Numbers below come from a real harness run on August 11, 2026 — **421 model
> runs, three reps each (n=3)** across three modes, for about **$6.77** of
> OpenRouter credit. The code, the tasks, and every raw result are in the repo
> linked at the bottom. This is a snapshot of a market that moves ~30% a month.
> Treat it as a method, not a verdict.

Yesterday Meta walked back into the open-weights room it stormed out of and put
[Muse Glimmer](https://research.meta.ai/blog/introducing-muse-glimmer-open-agentic-model)
on the table: 30 billion parameters, Apache 2.0, explicitly tuned for *agents* —
tool calling, local coding, LLM-as-judge — and small enough to fit under 20 GB
at 4-bit. It runs on **one** consumer GPU. Every benchmark thread within the
hour was the usual leaderboard confetti: MMLU this, SWE-bench that.

I didn't care about any of it. I had one question, and it's the same question
from [last month's piece](/running-the-frontier-at-home) about self-hosting the
open frontier, just pointed at a specific model and a specific job: *can this
thing do my work, on my hardware?* My work is nostr. My hardware is a
thousand-dollar box with two pensioned-off Tesla P40s in it. So instead of
reading someone else's benchmark, I built a harness and ran the tape.

## Why nostr is the good test (even if you've never touched it)

If you don't know nostr — it's a dead-simple decentralized protocol, events are
signed JSON blobs, relays are dumb pipes — the useful thing here isn't nostr
itself. It's that **nostr is a proxy for any protocol the model didn't marinate
in.** React, Express, JWT: these are in every model's bloodstream a hundred
million times over. A model can fake competence on them by pattern-matching. But
the moment you ask for something whose rules are *strict, specific, and thinly
represented in the training data* — the exact byte-for-byte serialization an
event ID is hashed from, bech32 vs bech32m, the TLV layout of an `nevent` — the
faking stops working. You find out whether the model **knows the thing** or
whipped up something plausible.

Every shop has one of these. Your internal RPC format. A gnarly domain schema. A
compliance DSL nobody outside the building has ever seen. Nostr is my stand-in
for yours. Swap the tasks, keep the method. That's the whole point of a harness
instead of a leaderboard: **you bring your own protocol.**

## The shape of the thing

Four task suites, all TypeScript (the language with the deepest nostr corpus, so
we test models where they're strongest rather than punishing them with a
translation step):

- **Implement from scratch** — write NIP-01 event signing/verification and
  NIP-19 bech32 encoding, no nostr libraries allowed. Pure "do you know the
  protocol."
- **Debug real code** — a working-but-wrong mini relay with five planted
  protocol bugs (event ID computed from the wrong serialization, `created_at` in
  milliseconds instead of seconds, a signature check that trusts the *claimed*
  ID, inverted `since`/`until`, a tag filter that ignores the tag name). Find and
  fix them.
- **General security audit** — an Express service with eight planted
  vulnerabilities (SQL injection, path traversal, JWT `alg:none`, SSRF,
  prototype pollution, weak hashing…) plus three red herrings that *look* scary
  but are safe.
- **Nostr security audit** — where the two worlds collide: a NIP-47 wallet-connect
  handler leaking an `nsec` to logs, using NIP-04 where NIP-44 is required,
  acting on events *before* verifying signatures, no replay protection.

Each task runs through three modes — **one-shot** (a single prompt), an **agent
harness** (a model driving itself with a shell and the visible test suite as
feedback), and **multi-model orchestration** (a strong model plans, a cheap one
edits) — at two prompt tiers (terse vs. spelled-out), graded by *hidden* tests
the model never sees. Twelve models, from Kimi K3 and K2.6 and GLM-5.2 at the top
down to gpt-oss-20b at the floor, with Muse Glimmer dropped in as the guest of
honor. Everything runs three times; the dashboard shows the min–max spread as a
whisker so you can see which "wins" are real and which are a coin flip.

Everything is scored per dollar and per model tier, because the entire question
is bang-for-buck: **best cloud pick, best pick that runs on your own metal.**

## What the one-shot screen said

Ask each model, cold, to just *do* the four tasks, and you get a leaderboard that
looks about how you'd expect at the top — and surprising underneath.

**Kimi K3 (91.7) and K2.6 (91.3) tie at the top** — and that near-tie is itself
worth a beat. K3 is Moonshot's newer, much larger model; on raw one-shot
knowledge of nostr and security it's a coin-flip better than the K2.6 we'd have
reached for. (It earns its keep elsewhere — hold that thought until the agent
section.) But the story of the whole study is a few rows down: **DeepSeek V4
Flash scores 85 at a fraction of a cent per task** — one-sixtieth of Kimi's cost.
If you're paying for tokens, Flash is the answer to almost every question, and it
wasn't close.

The great discriminator is the from-scratch implementation task. Writing Schnorr
signatures and bech32 with no library separated the field violently: the Kimis
and Flash nailed it, and most of the rest — GLM included — fell into the single
digits when a burst of reasoning ran out before the code landed. (You can see it
in the whiskers: the models with wide min–max spreads are the ones gambling on
whether the reasoning finishes in time.) Implementing an unfamiliar protocol
correctly, in one shot, is genuinely hard, and it's exactly the axis where "knows
the protocol" stops being fakeable.

## The security half, in detail — because this is where it gets interesting

Here's the finding I didn't expect, and it's the cleanest evidence for the whole
"unfamiliar protocol" thesis. Watch what happens to each model between the
**general** security audit and the **nostr** one:

| Model | General security | Nostr security | The fall |
|---|---|---|---|
| kimi-k3 | 96 | 88 | −8 |
| qwen3.6-35b | 98 | 84 | −14 |
| deepseek-v4-pro | 88 | 81 | −7 |
| muse-glimmer-30b | 96 | 80 | −16 |
| gpt-oss-120b | 90 | 79 | −11 |
| kimi-k2.6 | 96 | 78 | −18 |
| deepseek-v4-flash | 90 | 78 | −12 |
| gemma-4-31b | 96 | 77 | −19 |
| glm-5.2 | 96 | 70 | −26 |
| llama-3.3-70b | 50 | 38 | −13 |
| **gpt-oss-20b** | **84** | **41** | **−43** |

**General security is a solved problem.** SQL injection, `alg:none`, SSRF,
prototype pollution — these are so thick in the training data that almost every
model, down to a 30B that fits on a single card, scores in the 90s with *near-
perfect precision*. Nobody cried wolf: the three red herrings I planted to punish
trigger-happy auditors barely caught anyone — only the ageing Llama 3.3 stumbled.
If your threat model is the OWASP top ten, a cheap local model is a competent
first-pass reviewer today. That's a real, usable result.

But slide the same vulnerabilities into a nostr context — a leaked `nsec`, the
NIP-04-instead-of-NIP-44 malleability trap, processing an event before checking
its signature — and the floor drops out from under the models with thin nostr
corpus. gpt-oss-20b falls the hardest, from a respectable 84 to **41**: it can
spot a hardcoded SQL string all day, but it doesn't reliably know that logging an
`nsec` is the same category of sin as printing a private key, because it hasn't
read enough nostr to have the reflex. The generic security checklist doesn't fire
when the danger wears unfamiliar clothes, and the thinner the model's exposure,
the bigger the fall.

And the model that holds up best relative to its size? **Muse Glimmer, at 80** —
matching frontier DeepSeek V4 Pro and beating Kimi K2.6, GLM, and Gemma. It can't
*implement* nostr from scratch (more on that in a second), but it can *recognize*
nostr security smells. Recognition and generation are different muscles, and
Glimmer has the first one. For a local security reviewer, that asymmetry is
exactly the good news.

The lesson generalizes: a model's security judgment is only as deep as its
exposure to *your* stack. Test it on your protocol, not on the benchmark's.

## The agent harness is a great equalizer

Now hand each model a loop instead of a single shot — let it write code, run the
visible tests, see the failures, and try again — and the leaderboard doesn't
just shift. It gets rewritten.

The models that couldn't one-shot hard code *leap*:

- **gpt-oss-120b: 29 → 86.** **gpt-oss-20b: 4 → 53.** The whole gpt-oss family
  is built for the loop, not the sound bite.
- **Muse Glimmer: 37 → 80** on the code tasks. The nostr-ignorant one-shot model
  becomes a genuinely useful engineer the moment it can iterate against tests.
  Meta built it for exactly this, and it delivers exactly here.
- **GLM-5.2: 83 → 99.**

And — this is the honest part — the harness *hurts* the models that were already
great cold. **Kimi K2.6 drops 96 → 68; DeepSeek V4 Pro 85 → 61; the Qwens fall
20–30 points.** A model that nails a task in one clean pass can get talked out of
its own correct answer by a multi-turn loop, especially with a terse prompt that
lets it under-scope and call it done early. Two of the Qwen models often declined
to drive the loop at all — bailing after a couple of turns without editing a
thing. Driving an agent is its own skill, distinct from writing good code, and
not every model has it.

**And here's where Kimi K3 earns its price.** On one-shot it merely tied K2.6.
But in the agent loop it goes the *other* way from its predecessor — **K3 climbs
to 99 while K2.6 falls to 68.** The generational upgrade from K2.6 to K3 isn't
really more nostr knowledge; it's *agentic robustness* — the discipline to drive
a tool loop without talking itself out of a correct answer. If you'd only run the
one-shot screen you'd have called them equivalent and saved the money. The agent
harness is the lens that tells them apart, which is the whole argument for
testing in the mode you'll actually deploy.

The takeaway that matters for sovereignty: **the one-shot leaderboard is the
wrong lens for a local agent fleet.** Nobody runs a local model by copy-pasting
one prompt; they run it behind a harness that tests and retries. On *that* axis,
a 30B that fits on a single 24 GB card does frontier-adjacent code work. The
gap to the cloud closes right where you actually stand.

## The orchestration trick: make the cheap model punch up

Last move, and the best one. Split the job in two: a **strong model plans**, a
**cheap model edits**. I ran this natively through [Repo
Prompt](https://repoprompt.com)'s agent orchestration, on-device, on the same
buggy-relay task.

The oracle — gpt-oss-120b — read a fuzzy bug report ("other relays reject our
events; filters return the wrong results") and produced an exact,
implementation-ready plan: all five bugs named, each with the precise corrected
code and a note that verification must *recompute* the event ID rather than trust
it. Then gpt-oss-20b — the 30B floor model — applied that plan.

Follow one model through all three modes on the debug task:

**gpt-oss-20b, N2 debug: 0 → 50 → 100.**

Zero one-shot. Fifty in the solo agent harness. **A perfect hundred** with the
oracle's plan in hand — every bug fixed, no regressions, no signatures touched. A
model that could not solve the task alone solved it *completely* once a smarter
model did the thinking and left it the typing.

Then I swept the oracle: same task, same editor, but I swapped in five different
planners and graded the fix each produced. The result is a small surprise:

| Oracle (planner) | Fix score |
|---|---|
| gpt-oss-120b | 100 |
| Kimi K2.6 | 100 |
| DeepSeek V4 Flash | 100 |
| **Muse Glimmer 30B** | **100** |
| GLM-5.2 | 83 |

**Four of five planners produce a fully correct fix — including the local
30B Muse Glimmer.** As an *oracle*, the model that scored a 7 trying to implement
nostr from scratch nails the plan at 100. The lone miss is the frontier one:
GLM-5.2 filtered the tag by comparing its name against `"#e"` instead of `"e"` —
a one-character, nostr-specific slip that a nostr-fluent planner doesn't make and
a generic one does. Which means, delightfully, your *planner* can also run on
your own box. You don't strictly need to rent a brain; you might just need a
nostr-literate one.

That is the shape of a real self-hosted setup. Not one giant model straining
your VRAM — a **division of labor**: a small, fast, cheap editor that lives on
your box and does the mechanical work, pointed at a good planner (which can also
be local). Which brings me to the part I have to say plainly.

## Repo Prompt's Oracle and Context Builder freakin' rule

I went in planning to test models. I came out having also tested a tool, and it
earned the paragraph. Repo Prompt's **Context Builder** — the agent that goes and
assembles exactly the right files for a task within a token budget — and its
**Oracle** — the second-opinion planner you consult before you let an editor
loose — are the quiet load-bearing walls of this whole result. The reason
gpt-oss-20b hit 100 isn't that gpt-oss-20b got smarter; it's that the Oracle
handed it a plan so precise that "editing" was all that was left. Curate the
context well, plan with something strong, and your cheap local model stops being
a liability and starts being a perfectly good pair of hands.

One caveat I owe you, because I hit it: the fully-autonomous, headless version of
the cheap-editor step was flaky — the open-model editor agent completed twice
without writing a byte until I drove it *interactively*, approving edits in the
app. So today this arm wants a human at the keyboard. That's a rough edge, not a
disqualifier, and it's exactly the kind of thing that gets sanded down in a
release cycle or two.

## So: can you run an agentic dev setup on your own laptop?

Yes. Here's the honest assembly, straight from the numbers:

- **The editor / hands** runs local. Muse Glimmer on a single 24 GB card, or
  gpt-oss-120b if you've got the 96 GB for it, or gpt-oss-20b on the 16 GB laptop
  you already own. Behind an agent harness, any of them does real work.
- **The oracle / brain** is where you spend, and you should. A local gpt-oss-120b
  makes a strong planner; but if the task is hard and you want the ceiling, this
  is the one place it's worth reaching for a better model — a cloud frontier, or
  the biggest thing your rig can hold — to write the plan your local editor then
  executes cheaply and privately.
- **The data never leaves the building** except, optionally, the plan — and you
  can keep even that local if you trade a little quality for total sovereignty.

That's a genuinely good developer loop that lives mostly on hardware you own,
with the expensive part rented by the plan rather than by the token. The frontier
stays a budget-cycle out of reach, same as always. But *competent, private,
agentic coding against your own weird protocol* is a thing you can run at home
today. Eighteen months ago the answer was no. It's yes now.

## The harness is the actual deliverable

The scores above are a snapshot; they'll be wrong in a month in the most
encouraging way. The thing worth keeping is the **harness**. It does two things
no leaderboard can:

1. **Crank the difficulty to match your world.** These tasks are small on
   purpose. Plant harder bugs, demand a fuller NIP-19 implementation, wire in
   your own protocol's test vectors — the grading is hidden tests, so you just
   add tests. The moment a benchmark saturates, you make it harder; the harness
   doesn't care.
2. **Pair and compare anything.** Every model is a config line; every oracle /
   editor pairing is two. Want to know if GLM-plans-Glimmer-edits beats
   Flash-solo on *your* codebase? It's a one-line change and an afternoon of
   cheap runs. That's the loop that actually answers "which combination is best
   for me," which is the only question that was ever real.

The whole study — four task suites, three drivers, the grader, all 127 raw
results, and the dashboard — is in the repo. Clone it, point it at your protocol,
and find out which cheap model you can trust with your own strange corner of the
world.

The floor is still rising faster than the ceiling. Muse Glimmer is this month's
proof. Bring your own protocol and go see for yourself.

---

*Method: 12 open-weight models × 4 task suites × 2 prompt tiers × 3 reps (n=3),
graded by hidden vitest suites (implement/debug) and a recall×precision findings
scorer (security), via OpenRouter; agent mode is a pinned 4-tool loop;
orchestration and the planner sweep ran natively in Repo Prompt CE on-device.
421 runs, ~$6.77 total. Scores are the median of three reps; the dashboard
whiskers show the min–max spread, so treat overlapping ranges as ties. Reasoning
models were given a generous token budget with a reasoning cap; where a model
ignored the cap or an editor wouldn't write headlessly, it's noted in the
dashboard.*
