# N2 — Debug real nostr code

<!-- KIND: debug -->
<!-- TARGET: src/nostr.ts -->

<!-- T1 -->
Clients report that events created by this library are rejected by other relays,
and that filters return the wrong events. Find and fix the protocol violations in
`src/`. Don't change the public API. Visible tests in `tests_visible/` pass today;
keep them passing.
<!-- /T1 -->

<!-- T2 -->
This is a small nostr client + in-memory relay. It works against *itself* but
violates NIP-01 in ways that break interop with real relays, and its filter
matching is wrong. There are **five** distinct protocol/logic bugs across `src/`.
Find and fix all five without changing the exported function signatures.

Symptoms reported:
- Events this library signs are rejected as having an invalid `id`/signature by
  other relays, even though this library accepts its own.
- `created_at` values look absurdly large to other relays.
- A filter with `#e` returns events that don't have that `e` tag.
- Filters with `since`/`until` return the complement of the intended time range.

Keep the visible tests green; there is also a hidden suite that checks each fix.
<!-- /T2 -->
