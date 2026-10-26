#!/usr/bin/env python3
"""Build a drydock-eval dataset from the drydock-test-corpus.

Why planted bugs: the corpus has no labelled findings (review_feedback and
eval_runs are empty), and its 858 published reviews were generated from broken
inputs (see drydock/docs/investigations/review-mismatch-2026-08-12.md), so
neither can rank models. The corpus *inputs* are clean, though: kind-1617
events carry real `git format-patch` diffs from real nostr projects. We take
those diffs, plant one fresh bug per case at a known new-file line (that line
is the hidden expected finding), and keep untouched originals as clean
controls. Nothing here is lifted from public bug corpora, and the expected
findings are never shown to the model; drydock-bench only sends the bundle,
the diff and the changed-file list.

Usage:
  python3 -I build_dataset.py --db /path/drydock.db --out data/drydock-planted-v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sqlite3
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

CODE_LANGS = {
    "ts": "ts", "tsx": "ts", "js": "ts", "jsx": "ts", "mjs": "ts",
    "go": "go", "rs": "rs", "kt": "kt", "java": "java",
}
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
COMMENT_RE = re.compile(r"^\s*(//|/\*|\*|#|--)")
IMPORT_RE = re.compile(r"^\s*(import |from |use |package |#include|export \* from|export \{[^}]*\} from)")
TESTISH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|[._-](test|spec)\.[a-z]+$|_test\.go$")
# A bare `?` is deliberately not a condition marker: it is Rust's error
# propagation operator and TS optional chaining. Ternaries need spaces.
COND_RE = re.compile(r"\b(if|while|for|return|elif|when|guard|assert)\b|&&|\|\||\s\?\s")
CLOSURE_RE = re.compile(r"(move\s*|[(,=]\s*)\|\|")  # Rust `|| expr` closures


# --------------------------------------------------------------------------
# format-patch parsing
# --------------------------------------------------------------------------

@dataclass
class Line:
    tag: str            # '+', '-', ' ', '\\'
    text: str
    new_no: int | None  # new-file line number for '+' and ' '


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    tail: str
    lines: list[Line] = field(default_factory=list)


@dataclass
class FileDiff:
    header: list[str]   # 'diff --git', index, ---, +++ lines
    path: str
    hunks: list[Hunk] = field(default_factory=list)


def split_format_patch(content: str) -> tuple[str, str]:
    """Return (description, diff_text) from a git format-patch message."""
    i = content.find("\ndiff --git ")
    if i < 0:
        return "", ""
    head, diff = content[:i], content[i + 1:]
    # drop the trailing signature ("-- \n2.43.0"); parse_diff also stops each
    # hunk at its declared length, which covers "--" written without the space
    diff = re.split(r"^-- ?\n(?=[^\n]*\n*\Z)", diff, maxsplit=1, flags=re.M)[0]
    diff = re.split(r"^-- \n", diff, maxsplit=1, flags=re.M)[0].rstrip("\n") + "\n"
    subj = re.search(r"^Subject: (?:\[PATCH[^\]]*\] )?(.+(?:\n [^\n]+)*)", head, re.M)
    subject = re.sub(r"\n\s+", " ", subj.group(1)).strip() if subj else ""
    body = ""
    m = re.search(r"\n\n(.*?)(?:\n---\n|\Z)", head, re.S)
    if m:
        body = m.group(1).strip()
    desc = subject + ("\n\n" + body if body else "")
    return desc.strip(), diff


def parse_diff(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    new_no = old_left = new_left = 0
    for raw in diff.split("\n"):
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(\S+) b/(\S+)", raw)
            cur = FileDiff(header=[raw], path=m.group(2) if m else "")
            files.append(cur)
            hunk = None
            continue
        if cur is None:
            continue
        m = HUNK_RE.match(raw)
        if m:
            hunk = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1), m.group(5))
            cur.hunks.append(hunk)
            new_no = hunk.new_start
            old_left, new_left = hunk.old_len, hunk.new_len
            continue
        if hunk is None:
            if raw:
                cur.header.append(raw)
            continue
        if old_left <= 0 and new_left <= 0 and not raw.startswith("\\"):
            # Hunk complete: anything else before the next header is trailer,
            # e.g. a format-patch signature written as "--" without the space.
            continue
        if raw == "":
            if old_left > 0 and new_left > 0:
                raw = " "  # blank context line whose leading space was stripped
            else:
                continue  # separator / end of text
        tag, text = raw[0], raw[1:]
        if tag in "+ ":
            hunk.lines.append(Line(tag, text, new_no))
            new_no += 1
            new_left -= 1
            old_left -= tag == " "
        elif tag in "-\\":
            hunk.lines.append(Line(tag, text, None))
            old_left -= tag == "-"
    return files


def render_diff(files: list[FileDiff]) -> str:
    out: list[str] = []
    for f in files:
        out.extend(f.header)
        for h in f.hunks:
            old_len = sum(1 for l in h.lines if l.tag in "- ")
            new_len = sum(1 for l in h.lines if l.tag in "+ ")
            out.append(f"@@ -{h.old_start},{old_len} +{h.new_start},{new_len} @@{h.tail}")
            out.extend(l.tag + l.text for l in h.lines)
    return "\n".join(out) + "\n"


def renumber(f: FileDiff) -> None:
    """Recompute new-file numbering after an insertion (shifts later hunks)."""
    shift = 0
    for h in f.hunks:
        h.new_start += shift
        n = h.new_start
        before = h.new_len
        for l in h.lines:
            if l.tag in "+ ":
                l.new_no = n
                n += 1
        h.new_len = n - h.new_start
        shift += h.new_len - before


# --------------------------------------------------------------------------
# bug operators — each returns (new_text, category, severity, note) or None
# --------------------------------------------------------------------------

def fake_secret(rng: random.Random) -> tuple[str, str, str]:
    """Return (identifier stem, value, description) for a fresh fake secret."""
    bech32 = "023456789acdefghjklmnpqrstuvwxyz"
    kind = rng.choice(["nsec", "hexkey", "token"])
    if kind == "nsec":
        return (rng.choice(["signer_nsec", "bot_nsec", "relay_admin_nsec"]),
                "nsec1" + "".join(rng.choice(bech32) for _ in range(58)),
                "hardcoded Nostr private key (nsec) committed in source")
    if kind == "hexkey":
        return (rng.choice(["signing_key_hex", "default_privkey", "test_secret_key"]),
                "".join(rng.choice("0123456789abcdef") for _ in range(64)),
                "hardcoded secp256k1 private key (hex) committed in source")
    return (rng.choice(["blossom_api_token", "relay_auth_token", "push_service_secret"]),
            "sk_" + "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(40)),
            "hardcoded service credential committed in source")


def ident(stem: str, lang: str, const: bool) -> str:
    if lang == "rs" or (const and lang == "java"):
        return stem.upper()
    head, *rest = stem.split("_")
    return head + "".join(w.title() for w in rest)


def op_cmp_flip(text, lang, rng):
    if not COND_RE.search(text):
        return None
    swaps = [(" === ", " !== "), (" !== ", " === "), (" == ", " != "), (" != ", " == "),
             (" <= ", " < "), (" >= ", " > "), (" < ", " <= "), (" > ", " >= ")]
    for a, b in swaps:
        if a in text and text.count('"') % 2 == 0:
            i = text.index(a)
            if text[:i].count('"') % 2 or text[:i].count("'") % 2:
                continue  # inside a string literal
            return (text[:i] + b + text[i + len(a):], "correctness", "high",
                    f"comparison operator changed from '{a.strip()}' to '{b.strip()}'")
    return None


def op_bool_flip(text, lang, rng):
    if lang == "rs" and CLOSURE_RE.search(text):
        return None
    for a, b in ((" && ", " || "), (" || ", " && ")):
        if a in text and COND_RE.search(text):
            i = text.index(a)
            return (text[:i] + b + text[i + len(a):], "correctness", "high",
                    f"logical operator changed from '{a.strip()}' to '{b.strip()}'")
    return None


def op_off_by_one(text, lang, rng):
    pats = [(r"\.length - 1\b", ".length"), (r"\blen\(([^()]+)\) ?- ?1\b", r"len(\1)"),
            (r"\.len\(\) ?- ?1\b", ".len()"), (r"\.size ?- ?1\b", ".size"), (r"\.size\(\) ?- ?1\b", ".size()")]
    for p, r in pats:
        if re.search(p, text):
            return (re.sub(p, r, text, count=1), "correctness", "high",
                    "upper bound no longer subtracts one (off-by-one / out-of-range index)")
    return None


def op_drop_await(text, lang, rng):
    if lang != "ts":
        return None
    # `return await f()` -> `return f()` still propagates the promise, so it is
    # not a defect; only assignments and bare statements lose the await.
    m = re.search(r"(=|^\s*)\s*await\s+(?=[\w.(])", text)
    if not m or "for await" in text or re.match(r"\s*return\b", text):
        return None
    return (text[:m.start()] + m.group(0).replace("await ", "", 1) + text[m.end():], "correctness", "high",
            "await removed: promise is no longer awaited (unhandled rejection / use before resolution)")


def op_return_flip(text, lang, rng):
    m = re.search(r"\breturn (true|false)\b", text)
    if not m:
        return None
    flipped = "false" if m.group(1) == "true" else "true"
    return (text[:m.start(1)] + flipped + text[m.end(1):], "correctness", "high",
            f"boolean return value inverted ({m.group(1)} -> {flipped})")


def op_verify_bypass(text, lang, rng):
    m = re.search(r"\b(?:\w+\.)?(verify\w*|validate\w*|isValid\w*|checkSig\w*)\(([^()]*)\)", text)
    if not m or not COND_RE.search(text):
        return None
    return (text[:m.start()] + "true" + text[m.end():], "security", "critical",
            f"call to {m.group(1)}() replaced with constant true (verification bypass)")


def op_hardcoded_secret(text, lang, rng, indent):
    stem, s, note = fake_secret(rng)
    decl = {
        "ts": f'const {ident(stem, lang, False)} = "{s}";',
        "go": f'const {ident(stem, lang, False)} = "{s}"',
        "rs": f'const {ident(stem, lang, True)}: &str = "{s}";',
        "kt": f'val {ident(stem, lang, False)} = "{s}"',
        "java": f'final String {ident(stem, lang, True)} = "{s}";',
    }[lang]
    return (indent + decl, "security", "high", note)


def op_tls_off(text, lang, rng, indent):
    if lang != "ts":
        return None  # path check (no .tsx/.jsx UI code) happens in candidates()
    return (indent + 'process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";', "security", "high",
            "TLS certificate verification disabled process-wide")


REPLACE_OPS = {"cmp_flip": op_cmp_flip, "bool_flip": op_bool_flip, "off_by_one": op_off_by_one,
               "drop_await": op_drop_await, "return_flip": op_return_flip, "verify_bypass": op_verify_bypass}
INSERT_OPS = {"hardcoded_secret": op_hardcoded_secret, "tls_off": op_tls_off}
SECURITY_OPS = {"verify_bypass", "hardcoded_secret", "tls_off"}


def eligible(path: str, text: str) -> bool:
    s = text.strip()
    return bool(s) and len(s) < 200 and not COMMENT_RE.match(text) and not IMPORT_RE.match(text)


def candidates(files: list[FileDiff], rng: random.Random):
    """Yield (op, file_idx, hunk_idx, line_idx, kind) for every applicable mutation."""
    for fi, f in enumerate(files):
        lang = CODE_LANGS.get(f.path.rsplit(".", 1)[-1])
        if not lang or TESTISH_RE.search(f.path):
            continue
        for hi, h in enumerate(f.hunks):
            # Rust hunks that embed other languages in format!/raw strings
            # (`{{`, `r#"`) would get a Rust decl inserted into JS/HTML text.
            embedded = lang == "rs" and any("{{" in x.text or 'r#"' in x.text for x in h.lines)
            for li, l in enumerate(h.lines):
                if l.tag != "+" or not eligible(f.path, l.text):
                    continue
                for name, fn in REPLACE_OPS.items():
                    if fn(l.text, lang, rng):
                        yield name, fi, hi, li, "replace"
                prev = next((p for p in reversed(h.lines[:li]) if p.tag in "+ "), None)
                if prev is not None and not embedded and insertion_point_ok(prev.text, l.text):
                    for name in INSERT_OPS:
                        if name == "tls_off" and not re.search(r"\.(ts|js|mjs)$", f.path):
                            continue
                        yield name, fi, hi, li, "insert"


# A line that opens a function/control block (not a struct, class, interface,
# enum or object literal, where a declaration would not compile).
BLOCK_OPEN_RE = re.compile(r"(\)\s*(->\s*[^{]+|:\s*[\w<>\[\]|, ]+)?|=>|\b(else|try|do|finally|loop|unsafe))\s*\{$"
                           r"|^\s*(\}\s*else\s+)?(if|for|while|func|fn|pub fn|async fn)\b.*\{$")
# match/switch/select/when bodies hold arms or cases, not statements.
NOT_BODY_RE = re.compile(r"\b(struct|interface|enum|class|object|impl|trait|type|union|match|switch|select|when)\b"
                         r"|[=:]\s*\{$|\(\{$")
# The anchor must itself look like a statement, so the insertion lands in a
# statement list rather than among fields, arguments or array elements.
STATEMENT_RE = re.compile(
    r"\s*(const|let|var|val|return|if|for|while|await|throw|try|switch|defer|go|match|self\.|this\."
    r"|[A-Za-z_][\w.]*(\s*(:=|=(?![=>])|\+=|-=)|\(|\.[A-Za-z_]))")


def insertion_point_ok(prev: str, anchor: str) -> bool:
    p = prev.rstrip()
    if not STATEMENT_RE.match(anchor) or re.match(r"\s*(\}|\)|\]|\.|&&|\|\||else|catch|case|default)", anchor):
        return False
    if p.endswith("{"):
        return bool(BLOCK_OPEN_RE.search(p)) and not NOT_BODY_RE.search(p)
    if re.fullmatch(r"\s*\}\s*;?", p):
        return True  # a bare closing brace (not `key={x}` JSX or `})`)
    return p.endswith(";") and STATEMENT_RE.match(prev) is not None


def apply(files: list[FileDiff], op: str, fi: int, hi: int, li: int, rng: random.Random):
    f = files[fi]
    h = f.hunks[hi]
    lang = CODE_LANGS[f.path.rsplit(".", 1)[-1]]
    anchor = h.lines[li]
    if op in REPLACE_OPS:
        new_text, cat, sev, note = REPLACE_OPS[op](anchor.text, lang, rng)
        before = anchor.text
        anchor.text = new_text
        return {"category": cat, "file": f.path, "line": anchor.new_no, "severity": sev}, note, before, new_text
    indent = re.match(r"\s*", anchor.text).group(0)
    new_text, cat, sev, note = INSERT_OPS[op](anchor.text, lang, rng, indent)
    h.lines.insert(li, Line("+", new_text, None))
    renumber(f)
    return {"category": cat, "file": f.path, "line": h.lines[li].new_no, "severity": sev}, note, "", new_text


def self_check(files: list[FileDiff], diff_text: str) -> None:
    """Parsing the rendered diff must reproduce identical new-file numbering."""
    again = parse_diff(diff_text)
    a = [(f.path, l.new_no, l.text) for f in files for h in f.hunks for l in h.lines if l.tag == "+"]
    b = [(f.path, l.new_no, l.text) for f in again for h in f.hunks for l in h.lines if l.tag == "+"]
    if a != b:
        raise AssertionError("rendered diff does not round-trip")


# --------------------------------------------------------------------------
# corpus selection
# --------------------------------------------------------------------------

def load_patches(db_path: str, min_added: int, max_added: int, max_files: int, per_repo: int):
    db = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    repos = {r[0]: (r[1] or r[2], r[3] or "") for r in
             db.execute("select repo_id, name, identifier, description from repositories")}
    seen: set[str] = set()
    per: dict[str, int] = {}
    out = []
    rows = db.execute("select event_id, repo_id, content from patch_events where kind = 1617 order by created_at, event_id")
    for eid, repo_id, content in rows:
        desc, diff = split_format_patch(content)
        if not diff:
            continue
        files = parse_diff(diff)
        if not files or len(files) > max_files:
            continue
        if not any(CODE_LANGS.get(f.path.rsplit(".", 1)[-1]) and not TESTISH_RE.search(f.path) for f in files):
            continue
        added = sum(1 for f in files for h in f.hunks for l in h.lines if l.tag == "+")
        if not (min_added <= added <= max_added):
            continue
        key = hashlib.sha256(render_diff(files).encode()).hexdigest()
        if key in seen:
            continue  # same diff re-sent as a revision / to another repo id
        seen.add(key)
        name, rdesc = repos.get(repo_id, (repo_id.split(":")[-1], ""))
        name = name or repo_id.split(":")[-1] or repo_id[:12]
        if per.get(name, 0) >= per_repo:
            continue
        per[name] = per.get(name, 0) + 1
        out.append({"event_id": eid, "repo_id": repo_id, "repo": name, "repo_description": rdesc,
                    "description": desc, "diff": diff, "added": added})
    return out


def bundle(p: dict, files: list[FileDiff] | None = None) -> str:
    parts = [f"## repository\n{p['repo']}" + (f" — {p['repo_description']}" if p["repo_description"] else "")]
    if p["description"]:
        parts.append("## patch description\n" + p["description"])
    if files is not None:
        # Experimental layer (not in production drydock): explicit new-file line
        # numbers for added lines, so the reviewer need not count hunk offsets.
        rows = [f"{f.path}:{l.new_no}: {l.text}" for f in files for h in f.hunks for l in h.lines if l.tag == "+"]
        parts.append("## added lines (new-file line numbers)\n" + "\n".join(rows[:600]))
    return "\n\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--min-added", type=int, default=8)
    ap.add_argument("--max-added", type=int, default=500)
    ap.add_argument("--max-files", type=int, default=10)
    ap.add_argument("--per-repo", type=int, default=6, help="cap patches per repo for diversity")
    ap.add_argument("--clean-every", type=int, default=3, help="also emit an unmutated control for every Nth patch")
    ap.add_argument("--smoke", type=int, default=6, help="also write <out>.smoke.json with N cases")
    ap.add_argument("--annotate-lines", action="store_true",
                    help="add an experimental layer listing new-file line numbers of added lines")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    patches = load_patches(args.db, args.min_added, args.max_added, args.max_files, args.per_repo)
    cases, op_use, skipped = [], {}, 0
    for idx, p in enumerate(patches):
        files = parse_diff(p["diff"])
        changed = [f.path for f in files]
        short = p["event_id"][:10]
        base_meta = {"source_event_id": p["event_id"], "repo": p["repo"], "added_lines": p["added"], "files": len(files)}
        if idx % args.clean_every == 0:
            clean_diff = render_diff(files)
            self_check(files, clean_diff)
            cases.append({"case_id": f"clean-{short}", "patch_diff": clean_diff, "changed_files": changed,
                          "context_bundle": bundle(p, files if args.annotate_lines else None), "expected_findings": [],
                          "bench_meta": {**base_meta, "kind": "clean"}})
        cands = list(candidates(files, rng))
        if not cands:
            skipped += 1
            continue
        # Balance operators across the dataset; aim for ~30% security plants.
        by_op: dict[str, list] = {}
        for c in cands:
            by_op.setdefault(c[0], []).append(c)
        sec_share = sum(op_use.get(o, 0) for o in SECURITY_OPS) / max(1, sum(op_use.values()))
        pool = [o for o in by_op if (o in SECURITY_OPS) == (sec_share < 0.30)] or list(by_op)
        op = min(sorted(pool), key=lambda o: (op_use.get(o, 0), rng.random()))
        op_use[op] = op_use.get(op, 0) + 1
        _, fi, hi, li, _kind = rng.choice(by_op[op])
        expected, note, before, after = apply(files, op, fi, hi, li, rng)
        mut_diff = render_diff(files)
        self_check(files, mut_diff)
        cases.append({"case_id": f"mut-{short}-{op}", "patch_diff": mut_diff, "changed_files": changed,
                      "context_bundle": bundle(p, files if args.annotate_lines else None), "expected_findings": [expected],
                      "bench_meta": {**base_meta, "kind": "planted", "op": op, "note": note,
                                     "before": before.strip(), "after": after.strip()}})

    ds = {"id": f"drydock-planted-v1-seed{args.seed}" + ("-annotated" if args.annotate_lines else ""), "cases": cases}
    with open(args.out, "w") as fh:
        json.dump(ds, fh, indent=1)
    if args.smoke:
        planted = [c for c in cases if c["bench_meta"]["kind"] == "planted"][: args.smoke - 1]
        clean = [c for c in cases if c["bench_meta"]["kind"] == "clean"][:1]
        out = Path(args.out)
        with open(out.with_name(out.stem + ".smoke.json"), "w") as fh:
            json.dump({"id": ds["id"] + "-smoke", "cases": planted + clean}, fh, indent=1)
    kinds = {}
    for c in cases:
        kinds[c["bench_meta"]["kind"]] = kinds.get(c["bench_meta"]["kind"], 0) + 1
    print(f"patches={len(patches)} cases={len(cases)} {kinds} no-candidate={skipped}", file=sys.stderr)
    print("operators:", dict(sorted(op_use.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
