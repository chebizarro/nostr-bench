const CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";
const GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];

function polymod(values: number[]): number {
  let chk = 1;
  for (const v of values) {
    const top = chk >> 25;
    chk = ((chk & 0x1ffffff) << 5) ^ v;
    for (let i = 0; i < 5; i++) if ((top >> i) & 1) chk ^= GEN[i];
  }
  return chk;
}
function hrpExpand(hrp: string): number[] {
  const out: number[] = [];
  for (let i = 0; i < hrp.length; i++) out.push(hrp.charCodeAt(i) >> 5);
  out.push(0);
  for (let i = 0; i < hrp.length; i++) out.push(hrp.charCodeAt(i) & 31);
  return out;
}
function createChecksum(hrp: string, data: number[]): number[] {
  const values = hrpExpand(hrp).concat(data).concat([0, 0, 0, 0, 0, 0]);
  const mod = polymod(values) ^ 1;
  const out: number[] = [];
  for (let i = 0; i < 6; i++) out.push((mod >> (5 * (5 - i))) & 31);
  return out;
}
function verifyChecksum(hrp: string, data: number[]): boolean {
  return polymod(hrpExpand(hrp).concat(data)) === 1;
}
function convertBits(data: number[], from: number, to: number, pad: boolean): number[] {
  let acc = 0, bits = 0;
  const out: number[] = [];
  const maxv = (1 << to) - 1;
  for (const value of data) {
    acc = (acc << from) | value;
    bits += from;
    while (bits >= to) { bits -= to; out.push((acc >> bits) & maxv); }
  }
  if (pad) { if (bits > 0) out.push((acc << (to - bits)) & maxv); }
  else if (bits >= from || ((acc << (to - bits)) & maxv)) throw new Error("bad padding");
  return out;
}
function bech32Encode(hrp: string, data: number[]): string {
  const combined = data.concat(createChecksum(hrp, data));
  return hrp + "1" + combined.map((d) => CHARSET[d]).join("");
}
function bech32Decode(s: string): { hrp: string; data: number[] } {
  const lower = s.toLowerCase();
  if (s !== lower && s !== s.toUpperCase()) throw new Error("mixed case");
  const pos = lower.lastIndexOf("1");
  if (pos < 1) throw new Error("no separator");
  const hrp = lower.slice(0, pos);
  const data: number[] = [];
  for (const c of lower.slice(pos + 1)) {
    const idx = CHARSET.indexOf(c);
    if (idx === -1) throw new Error("bad char");
    data.push(idx);
  }
  if (!verifyChecksum(hrp, data)) throw new Error("bad checksum");
  return { hrp, data: data.slice(0, -6) };
}

function hexToBytes(hex: string): number[] {
  const out: number[] = [];
  for (let i = 0; i < hex.length; i += 2) out.push(parseInt(hex.slice(i, i + 2), 16));
  return out;
}
function bytesToHexArr(b: number[]): string {
  return b.map((x) => x.toString(16).padStart(2, "0")).join("");
}

export function encodeBech32(prefix: "npub" | "nsec" | "note", dataHex: string): string {
  return bech32Encode(prefix, convertBits(hexToBytes(dataHex), 8, 5, true));
}
export function decodeBech32(s: string): { prefix: string; dataHex: string } {
  const { hrp, data } = bech32Decode(s);
  const bytes = convertBits(data, 5, 8, false);
  if (bytes.length !== 32) throw new Error("bad length");
  return { prefix: hrp, dataHex: bytesToHexArr(bytes) };
}

// TLV
function encodeTLV(entries: [number, number[]][]): number[] {
  const out: number[] = [];
  for (const [t, v] of entries) { out.push(t, v.length); out.push(...v); }
  return out;
}
function decodeTLV(bytes: number[]): Record<number, number[][]> {
  const out: Record<number, number[][]> = {};
  let i = 0;
  while (i < bytes.length) {
    const t = bytes[i++], l = bytes[i++];
    const v = bytes.slice(i, i + l); i += l;
    (out[t] ||= []).push(v);
  }
  return out;
}
const enc = (s: string) => Array.from(new TextEncoder().encode(s));
const dec = (b: number[]) => new TextDecoder().decode(new Uint8Array(b));

export function encodeNprofile(pubkeyHex: string, relays: string[]): string {
  const tlv = encodeTLV([[0, hexToBytes(pubkeyHex)], ...relays.map((r) => [1, enc(r)] as [number, number[]])]);
  return bech32Encode("nprofile", convertBits(tlv, 8, 5, true));
}
export function decodeNprofile(s: string): { pubkey: string; relays: string[] } {
  const { hrp, data } = bech32Decode(s);
  if (hrp !== "nprofile") throw new Error("bad prefix");
  const tlv = decodeTLV(convertBits(data, 5, 8, false));
  return { pubkey: bytesToHexArr(tlv[0][0]), relays: (tlv[1] || []).map(dec) };
}
export interface NeventData { id: string; relays?: string[]; author?: string; }
export function encodeNevent(d: NeventData): string {
  const entries: [number, number[]][] = [[0, hexToBytes(d.id)]];
  for (const r of d.relays || []) entries.push([1, enc(r)]);
  if (d.author) entries.push([2, hexToBytes(d.author)]);
  return bech32Encode("nevent", convertBits(encodeTLV(entries), 8, 5, true));
}
export function decodeNevent(s: string): NeventData {
  const { hrp, data } = bech32Decode(s);
  if (hrp !== "nevent") throw new Error("bad prefix");
  const tlv = decodeTLV(convertBits(data, 5, 8, false));
  return {
    id: bytesToHexArr(tlv[0][0]),
    relays: (tlv[1] || []).map(dec),
    author: tlv[2] ? bytesToHexArr(tlv[2][0]) : undefined,
  };
}
