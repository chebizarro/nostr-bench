# S2 — Security audit of a nostr bot + NIP-47 handler

<!-- KIND: audit -->
<!-- TARGET: findings.json -->

<!-- T1 -->
Audit the TypeScript nostr bot and NIP-47 (Nostr Wallet Connect) handler in
`src/` for security problems. Return a JSON array of findings, each
`{ "title", "file", "severity", "description" }`. Real issues only.
<!-- /T1 -->

<!-- T2 -->
Security review of a nostr bot and its NIP-47 wallet-connect handler in `src/`.
This is where nostr-specific knowledge matters: key handling, event
authentication ordering, the NIP-04 vs NIP-44 encryption choice, replay
protection (`created_at` windows and event-id dedup), and relay/URL handling are
all in scope, alongside ordinary web issues.

For each real vulnerability output `{ "title", "file", "severity":
"low|medium|high|critical", "description" }`. Return **only** a JSON array. A
generic web-security checklist will miss the nostr-specific issues; precision is
scored, so don't invent problems that aren't there.
<!-- /T2 -->
