import { describe, it, expect } from "vitest";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "@noble/hashes/utils";
import { createEvent, getEventHash, verifyEvent, type NostrEvent } from "../src/nostr";
import { matchFilter } from "../src/filter";

const sk = "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa";

function canonical(e: any): string {
  return bytesToHex(sha256(new TextEncoder().encode(
    JSON.stringify([0, e.pubkey, e.created_at, e.kind, e.tags, e.content]))));
}

describe("bug 1: canonical event id", () => {
  it("getEventHash matches NIP-01 canonical serialization (not JSON of the object)", () => {
    const e = { pubkey: "aa".repeat(32), created_at: 1673347337, kind: 1,
                tags: [["e", "abc"]], content: "hello" };
    expect(getEventHash(e)).toBe(canonical(e));
  });
  it("hash ignores id/sig fields if present on the object", () => {
    const base = { pubkey: "bb".repeat(32), created_at: 1000, kind: 1, tags: [], content: "x" };
    const withExtra = { ...base, id: "deadbeef", sig: "cafe" };
    expect(getEventHash(withExtra)).toBe(getEventHash(base));
  });
});

describe("bug 2: created_at in seconds", () => {
  it("createEvent stamps Unix seconds, not milliseconds", () => {
    const e = createEvent(sk, { kind: 1, content: "gm" });
    expect(e.created_at).toBeGreaterThan(1_000_000_000);   // after 2001 in seconds
    expect(e.created_at).toBeLessThan(100_000_000_000);     // ms would be ~1.7e12
  });
});

describe("bug 3: #e tag filter matches only e-tags", () => {
  it("does not match a value that appears only in a #p tag", () => {
    const e = { id: "x", pubkey: "y", created_at: 1000, kind: 1,
                tags: [["p", "TARGET"]], content: "", sig: "z" } as NostrEvent;
    expect(matchFilter({ ["#e"]: ["TARGET"] }, e)).toBe(false);
    expect(matchFilter({ ["#p"]: ["TARGET"] }, e)).toBe(true);
  });
});

describe("bug 4: since/until direction", () => {
  const at = (t: number) => ({ id: "x", pubkey: "y", created_at: t, kind: 1,
                               tags: [], content: "", sig: "z" } as NostrEvent);
  it("since is a lower bound, until an upper bound", () => {
    expect(matchFilter({ since: 500 }, at(1000))).toBe(true);
    expect(matchFilter({ since: 500 }, at(100))).toBe(false);
    expect(matchFilter({ until: 500 }, at(100))).toBe(true);
    expect(matchFilter({ until: 500 }, at(1000))).toBe(false);
  });
});

describe("bug 5: verify recomputes the id", () => {
  it("rejects an event whose content was tampered after signing", () => {
    const e = createEvent(sk, { kind: 1, content: "original" });
    expect(verifyEvent(e)).toBe(true);
    const tampered = { ...e, content: "tampered" }; // id + sig unchanged
    expect(verifyEvent(tampered)).toBe(false);
  });
});
