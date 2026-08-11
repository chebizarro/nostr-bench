import { schnorr } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "@noble/hashes/utils";

export interface NostrEvent {
  id: string; pubkey: string; created_at: number; kind: number;
  tags: string[][]; content: string; sig: string;
}
export type UnsignedEvent = Omit<NostrEvent, "id" | "sig" | "pubkey">;

export function getEventHash(e: Partial<NostrEvent>): string {
  const serialized = JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]);
  return bytesToHex(sha256(new TextEncoder().encode(serialized)));
}
export function createEvent(sk: string, draft: { kind: number; content: string; tags?: string[][] }): NostrEvent {
  const pubkey = bytesToHex(schnorr.getPublicKey(sk));
  const base = { pubkey, created_at: Math.floor(Date.now() / 1000), kind: draft.kind,
                 tags: draft.tags ?? [], content: draft.content };
  const id = getEventHash(base);
  const sig = bytesToHex(schnorr.sign(id, sk));
  return { ...base, id, sig };
}
export function verifyEvent(e: NostrEvent): boolean {
  try {
    if (e.id !== getEventHash(e)) return false;
    return schnorr.verify(e.sig, e.id, e.pubkey);
  } catch { return false; }
}
