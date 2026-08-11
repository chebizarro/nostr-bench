import type { NostrEvent } from "./nostr";
export interface Filter {
  ids?: string[]; authors?: string[]; kinds?: number[];
  since?: number; until?: number; ["#e"]?: string[]; ["#p"]?: string[];
}
export function matchFilter(f: Filter, e: NostrEvent): boolean {
  if (f.ids && !f.ids.includes(e.id)) return false;
  if (f.authors && !f.authors.includes(e.pubkey)) return false;
  if (f.kinds && !f.kinds.includes(e.kind)) return false;
  if (f.since !== undefined && e.created_at < f.since) return false;
  if (f.until !== undefined && e.created_at > f.until) return false;
  for (const key of ["#e", "#p"] as const) {
    const want = f[key];
    if (!want) continue;
    const letter = key.slice(1);
    const tagValues = e.tags.filter((t) => t[0] === letter).map((t) => t[1]);
    if (!want.some((v) => tagValues.includes(v))) return false;
  }
  return true;
}
export class Relay {
  private events: NostrEvent[] = [];
  publish(e: NostrEvent) { this.events.push(e); }
  query(f: Filter): NostrEvent[] { return this.events.filter((e) => matchFilter(f, e)); }
}
