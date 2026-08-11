import { describe, it, expect } from "vitest";
import { serializeEvent, getEventHash, signEvent, verifyEvent } from "../src/nip01";
import { encodeBech32, decodeBech32 } from "../src/nip19";

describe("nip01 basic (visible)", () => {
  const e = { pubkey: "aabbcc", created_at: 1000, kind: 1,
              tags: [["e", "f00d"]], content: "hello" };

  it("serializes to the canonical 6-element array form", () => {
    expect(serializeEvent(e)).toBe(
      JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]),
    );
  });

  it("hashes to lowercase 64-hex", () => {
    const h = getEventHash(e);
    expect(h).toMatch(/^[0-9a-f]{64}$/);
  });

  it("signs then verifies round-trip", () => {
    const priv = "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa";
    const signed = signEvent(e, priv);
    expect(signed.id).toMatch(/^[0-9a-f]{64}$/);
    expect(signed.sig).toMatch(/^[0-9a-f]{128}$/);
    expect(verifyEvent(signed)).toBe(true);
  });
});

describe("nip19 basic (visible)", () => {
  it("round-trips an npub", () => {
    const hex = "7e7e9c42a91bfef19fa929e5fda1b72e0ebc1a4c1141673e2794234d86addf4e";
    const s = encodeBech32("npub", hex);
    expect(s.startsWith("npub1")).toBe(true);
    expect(decodeBech32(s)).toEqual({ prefix: "npub", dataHex: hex });
  });
});
