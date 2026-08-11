# Reference solutions (NOT served to models)

Verified passing solutions, kept outside `tasks/*/starter` so the drivers never
include them in model context. They exist to (a) prove each task is solvable and
(b) provide a "reference ceiling" score. Verified on Node 22 + vitest:

- `n1_implement/`: passes all 14 hidden+visible tests. Matches nostr-tools bech32
  output exactly (npub/nsec/note vectors generated from nostr-tools).
- `n2_debug/`: all 5 planted bugs fixed; buggy starter fails 6 bug-tests, this
  fixes them to 8/8.

S1/S2 are audit tasks (no code fix); their answer keys live in
`tasks/*/answer_key.json` and the scorer is validated in `grade/selfcheck.py`
and by the samples in the delivery notes.
