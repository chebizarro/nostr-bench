// NIP-01 filter matching for an in-memory relay.
import type { NostrEvent } from "./nostr";

export interface Filter {
  ids?: string[];
  authors?: string[];
  kinds?: number[];
  since?: number;
  until?: number;
  ["#e"]?: string[];
  ["#p"]?: string[];
}

/** Return true if the event matches the filter. */
export function matchFilter(f: Filter, e: NostrEvent): boolean {
  if (f.ids && !f.ids.includes(e.id)) return false;
  if (f.authors && !f.authors.includes(e.pubkey)) return false;
  if (f.kinds && !f.kinds.includes(e.kind)) return false;

  if (f.since !== undefined && e.created_at > f.since) return false;
  if (f.until !== undefined && e.created_at < f.until) return false;

  for (const key of ["#e", "#p"] as const) {
    const want = f[key];
    if (!want) continue;
    const tagValues = e.tags.map((t) => t[1]);
    if (!want.some((v) => tagValues.includes(v))) return false;
  }
  return true;
}

/** In-memory relay store. */
export class Relay {
  private events: NostrEvent[] = [];
  publish(e: NostrEvent) { this.events.push(e); }
  query(f: Filter): NostrEvent[] { return this.events.filter((e) => matchFilter(f, e)); }
}
