// NIP-01 event core. Implement to these signatures.
// Allowed deps: @noble/curves/secp256k1 (schnorr), @noble/hashes/sha256.
// Do NOT import nostr-tools or any nostr library.

export interface NostrEvent {
  id?: string;
  pubkey: string;
  created_at: number;
  kind: number;
  tags: string[][];
  content: string;
  sig?: string;
}

/** Canonical serialization string that the event id is hashed from. */
export function serializeEvent(_e: NostrEvent): string {
  throw new Error("not implemented");
}

/** Lowercase-hex sha256 of the canonical serialization. */
export function getEventHash(_e: NostrEvent): string {
  throw new Error("not implemented");
}

/** Return the event with id + Schnorr sig set. `priv` is 32-byte hex. */
export function signEvent(_e: NostrEvent, _privHex: string): NostrEvent {
  throw new Error("not implemented");
}

/** True iff id matches the recomputed hash AND the Schnorr sig verifies. Never throws. */
export function verifyEvent(_e: NostrEvent): boolean {
  throw new Error("not implemented");
}
