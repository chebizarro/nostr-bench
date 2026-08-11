import { describe, it, expect } from "vitest";
import { schnorr } from "@noble/curves/secp256k1";
import { bytesToHex } from "@noble/hashes/utils";
import { serializeEvent, getEventHash, signEvent, verifyEvent } from "../src/nip01";

const priv = "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa";
const pub = bytesToHex(schnorr.getPublicKey(priv)); // x-only, 32 bytes

function ev(overrides = {}) {
  return { pubkey: pub, created_at: 1673347337, kind: 1,
           tags: [["e", "abc"], ["p", "def"]], content: "hello", ...overrides };
}

describe("nip01 serialization (hidden)", () => {
  it("uses compact separators, numbers unquoted", () => {
    const e = ev();
    expect(serializeEvent(e)).toBe(
      JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]),
    );
  });

  it("escapes exactly the NIP-01 control chars (trap: whitespace/escaping)", () => {
    const e = ev({ content: 'line1\nline2\ttab "quote" back\\slash \r end' });
    // JSON.stringify is the canonical oracle for these escapes.
    expect(serializeEvent(e)).toBe(
      JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]),
    );
    // forward slash must NOT be escaped
    const e2 = ev({ content: "a/b" });
    expect(serializeEvent(e2)).toContain("a/b");
  });

  it("hash is sha256 of the serialization", async () => {
    const { sha256 } = await import("@noble/hashes/sha256");
    const e = ev();
    const expected = bytesToHex(sha256(new TextEncoder().encode(serializeEvent(e))));
    expect(getEventHash(e)).toBe(expected);
  });
});

describe("nip01 sign/verify (hidden)", () => {
  it("sets x-only pubkey and a 64-byte schnorr sig", () => {
    const s = signEvent(ev(), priv);
    expect(s.pubkey).toBe(pub);
    expect(s.id).toBe(getEventHash(s));
    expect(s.sig).toMatch(/^[0-9a-f]{128}$/);
    // signature verifies with a real schnorr verifier
    expect(schnorr.verify(s.sig!, s.id!, s.pubkey)).toBe(true);
  });

  it("verifyEvent true on good, false on tampered content", () => {
    const s = signEvent(ev(), priv);
    expect(verifyEvent(s)).toBe(true);
    expect(verifyEvent({ ...s, content: "tampered" })).toBe(false);
  });

  it("verifyEvent false when id doesn't match recomputed hash (trap: trust claimed id)", () => {
    const s = signEvent(ev(), priv);
    const badId = "0".repeat(64);
    expect(verifyEvent({ ...s, id: badId })).toBe(false);
  });

  it("verifyEvent returns false, never throws, on malformed input", () => {
    expect(verifyEvent({ pubkey: "zz", created_at: 1, kind: 1, tags: [], content: "",
                         id: "x", sig: "y" } as any)).toBe(false);
  });
});
