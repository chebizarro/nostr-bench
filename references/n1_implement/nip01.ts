import { schnorr } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "@noble/hashes/utils";

export interface NostrEvent {
  id?: string;
  pubkey: string;
  created_at: number;
  kind: number;
  tags: string[][];
  content: string;
  sig?: string;
}

export function serializeEvent(e: NostrEvent): string {
  return JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]);
}

export function getEventHash(e: NostrEvent): string {
  return bytesToHex(sha256(new TextEncoder().encode(serializeEvent(e))));
}

export function signEvent(e: NostrEvent, privHex: string): NostrEvent {
  const pubkey = bytesToHex(schnorr.getPublicKey(privHex));
  const withPub = { ...e, pubkey };
  const id = getEventHash(withPub);
  const sig = bytesToHex(schnorr.sign(id, privHex));
  return { ...withPub, id, sig };
}

export function verifyEvent(e: NostrEvent): boolean {
  try {
    if (!e.id || !e.sig || !/^[0-9a-f]{64}$/.test(e.pubkey)) return false;
    if (e.id !== getEventHash(e)) return false;
    return schnorr.verify(e.sig, e.id, e.pubkey);
  } catch {
    return false;
  }
}
