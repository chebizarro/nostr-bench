// NIP-19 bech32 entities. Implement to these signatures.
// bech32 (NOT bech32m), lowercase, standard 6-char checksum, 5-bit grouping.
// Do NOT import a bech32 library — implement the encoding yourself.

/** Encode a 32-byte hex payload as npub/nsec/note. */
export function encodeBech32(_prefix: "npub" | "nsec" | "note", _dataHex: string): string {
  throw new Error("not implemented");
}

/** Decode npub/nsec/note -> {prefix, dataHex}. Throw on bad checksum/prefix/length. */
export function decodeBech32(_s: string): { prefix: string; dataHex: string } {
  throw new Error("not implemented");
}

export function encodeNprofile(_pubkeyHex: string, _relays: string[]): string {
  throw new Error("not implemented");
}

export function decodeNprofile(_s: string): { pubkey: string; relays: string[] } {
  throw new Error("not implemented");
}

export interface NeventData {
  id: string;
  relays?: string[];
  author?: string;
}

export function encodeNevent(_d: NeventData): string {
  throw new Error("not implemented");
}

export function decodeNevent(_s: string): NeventData {
  throw new Error("not implemented");
}
