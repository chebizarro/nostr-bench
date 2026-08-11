import { describe, it, expect } from "vitest";
import { createEvent, verifyEvent } from "../src/nostr";
import { Relay } from "../src/filter";

const sk = "67dea2ed018072d675f5415ecfaed7d2597555e202d85b3d65ea4e58d2d92ffa";

describe("happy path (visible)", () => {
  it("creates and self-verifies an event", () => {
    const e = createEvent(sk, { kind: 1, content: "gm" });
    expect(verifyEvent(e)).toBe(true);
  });

  it("relay returns events matching a kind filter", () => {
    const relay = new Relay();
    const e = createEvent(sk, { kind: 1, content: "note" });
    relay.publish(e);
    expect(relay.query({ kinds: [1] })).toHaveLength(1);
    expect(relay.query({ kinds: [7] })).toHaveLength(0);
  });
});
