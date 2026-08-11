// Mini nostr event core + client. Works against itself; violates NIP-01 for interop.
import { schnorr } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "@noble/hashes/utils";

export interface NostrEvent {
  id: string;
  pubkey: string;
  created_at: number;
  kind: number;
  tags: string[][];
  content: string;
  sig: string;
}

export type UnsignedEvent = Omit<NostrEvent, "id" | "sig" | "pubkey">;

/** Hash used for the event id. */
export function getEventHash(e: Partial<NostrEvent>): string {
  // Serialize the event to bytes and sha256 it.
  const serialized = JSON.stringify(e);
  return bytesToHex(sha256(new TextEncoder().encode(serialized)));
}

/** Build + sign an event with the given secret key (32-byte hex). */
export function createEvent(sk: string, draft: { kind: number; content: string; tags?: string[][] }): NostrEvent {
  const pubkey = bytesToHex(schnorr.getPublicKey(sk));
  const base = {
    pubkey,
    created_at: Date.now(),
    kind: draft.kind,
    tags: draft.tags ?? [],
    content: draft.content,
  };
  const id = getEventHash(base);
  const sig = bytesToHex(schnorr.sign(id, sk));
  return { ...base, id, sig };
}

/** Verify an event's id and signature. */
export function verifyEvent(e: NostrEvent): boolean {
  try {
    return schnorr.verify(e.sig, e.id, e.pubkey);
  } catch {
    return false;
  }
}
