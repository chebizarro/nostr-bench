# N1 — Implement a nostr feature from scratch

<!-- KIND: implement -->
<!-- TARGET: src/nip01.ts -->

Two independent modules, TypeScript. **You may not import `nostr-tools`, `ndk`, or
any nostr library.** You *may* use `@noble/curves` (secp256k1 / schnorr) and
`@noble/hashes` (sha256) — they're already in package.json. Everything else you
write yourself.

<!-- T1 -->
Implement the NIP-01 event functions in `src/nip01.ts` and the NIP-19 entity
functions in `src/nip19.ts` so the exports listed in the stub files work
correctly. Visible tests are in `tests_visible/`.
<!-- /T1 -->

<!-- T2 -->
Implement two modules to their stubs. There is a hidden test suite; make the
behaviour correct, not just green on the visible tests.

## `src/nip01.ts` — NIP-01 event core

- `serializeEvent(e)`: return the canonical serialization string that the event id
  is hashed from. It is the UTF-8 JSON of the array
  `[0, pubkey, created_at, kind, tags, content]` with **no insignificant
  whitespace** (compact separators) and with these characters in `content`
  escaped **and no others**: `\n`→`\n`, `\"`→`\"`, `\\`→`\\`, `\r`→`\r`,
  `\t`→`\t`, `\b`→`\b`, `\f`→`\f`. Note: `created_at` and `kind` are numbers, not
  strings; `pubkey` and `content` are inserted verbatim (after escaping).
- `getEventHash(e)`: lowercase hex sha256 of the serialization.
- `signEvent(e, privHex)`: return the event with `id` and `sig` set. `sig` is a
  BIP-340 **Schnorr** signature (not ECDSA) over the 32-byte id, hex-encoded.
  `pubkey` must be the 32-byte x-only public key, lowercase hex.
- `verifyEvent(e)`: return `true` iff `id` equals the recomputed hash **and** the
  Schnorr `sig` verifies against `pubkey` over that id. Must return `false`
  (never throw) on malformed input, wrong id, or bad signature.

## `src/nip19.ts` — NIP-19 bech32 entities

- `encodeBech32(prefix, dataHex)` / `decodeBech32(str)` for the simple types
  `npub`, `nsec`, `note` (32-byte payloads). Use bech32 (not bech32m), lowercase,
  the standard 6-char checksum, 5-bit grouping.
- `encodeNprofile(pubkeyHex, relays)` / `decodeNprofile(str)` and
  `encodeNevent({id, relays?, author?})` / `decodeNevent(str)` using **TLV**:
  type `0` = special (the 32-byte id/pubkey), type `1` = relay (ascii, may repeat),
  type `2` = author (32 bytes). Unknown TLV types must be ignored on decode, not
  rejected.
- Decoding must **reject** an invalid checksum, a wrong/oversized payload length,
  or a mismatched prefix by throwing.
<!-- /T2 -->
