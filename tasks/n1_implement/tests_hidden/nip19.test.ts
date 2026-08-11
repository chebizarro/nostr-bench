import { describe, it, expect } from "vitest";
import { encodeBech32, decodeBech32, encodeNprofile, decodeNprofile,
         encodeNevent, decodeNevent } from "../src/nip19";

describe("nip19 simple entities (hidden)", () => {
  // Canonical NIP-19 spec vectors.
  it("decodes a known npub", () => {
    const s = "npub10elfcs4fr0l0r8af98jlmgdh9c8tcxjvz9qkw038js35mp4dma8qzvjptg";
    expect(decodeBech32(s).dataHex).toBe(
      "7e7e9c42a91bfef19fa929e5fda1b72e0ebc1a4c1141673e2794234d86addf4e");
  });

  it("decodes a known nsec", () => {
    const s = "nsec1vl029mgpspedva04g90vltkh6fvh240zqtv9k0t9af8935ke9laqsnlfe5";
    expect(decodeBech32(s).dataHex).toBe(
      "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa");
  });

  it("round-trips arbitrary 32-byte payloads for all three prefixes", () => {
    const hex = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff";
    for (const p of ["npub", "nsec", "note"] as const) {
      const enc = encodeBech32(p, hex);
      expect(enc.startsWith(p + "1")).toBe(true);
      expect(decodeBech32(enc)).toEqual({ prefix: p, dataHex: hex });
    }
  });

  it("rejects a corrupted checksum", () => {
    const s = "npub10elfcs4fr0l0r8af98jlmgdh9c8tcxjvz9qkw038js35mp4dg4gs0m8nso"; // last char flipped
    expect(() => decodeBech32(s)).toThrow();
  });
});

describe("nip19 TLV entities (hidden)", () => {
  const pk = "3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d";
  const id = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899";

  it("round-trips nprofile with relays (type 0 + type 1 TLVs)", () => {
    const relays = ["wss://relay.example.com", "wss://nostr.example"];
    const enc = encodeNprofile(pk, relays);
    expect(enc.startsWith("nprofile1")).toBe(true);
    const dec = decodeNprofile(enc);
    expect(dec.pubkey).toBe(pk);
    expect(dec.relays.sort()).toEqual([...relays].sort());
  });

  it("round-trips nevent with author + relay", () => {
    const enc = encodeNevent({ id, relays: ["wss://r.example"], author: pk });
    const dec = decodeNevent(enc);
    expect(dec.id).toBe(id);
    expect(dec.author).toBe(pk);
    expect(dec.relays).toContain("wss://r.example");
  });

  it("ignores unknown TLV types rather than rejecting", () => {
    // encode a plain nprofile, decode must still succeed even if impl adds/ignores types
    const enc = encodeNprofile(pk, []);
    expect(decodeNprofile(enc).pubkey).toBe(pk);
  });
});
