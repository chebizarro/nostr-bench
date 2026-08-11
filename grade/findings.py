"""Score an audit task: recall over planted vulns, penalized for false positives.

Answer key (tasks/<t>/answer_key.json):
  {
    "vulns":  [{"id":"sqli","aliases":["sql injection"],"file":"src/db.ts","cwe":"CWE-89"}, ...],
    "red_herrings": [{"id":"rh_helmet","desc":"missing helmet header is not one of the graded issues"}]
  }

Model emits a JSON array of findings, each {title, file?, severity?, description}.
Matching is by keyword/alias against title+description (kept deliberately lenient
on wording, strict on concept). Score:

  recall     = matched_vulns / total_vulns
  fp         = findings that match neither a vuln nor a red herring  (hallucinations)
  rh_hits    = findings matching a red herring                        (fell for the trap)
  precision  = matched_vulns / (matched_vulns + fp + rh_hits)
  score      = 100 * recall * precision        (F-ish; both matter)
"""
from __future__ import annotations

import re

# Lightweight matcher: normalize, tokenize, crude-stem (prefix), drop stopwords,
# then match an alias if it is a substring OR enough of its distinctive tokens
# appear in the finding text. This tolerates paraphrase ("processed before
# verifying" vs "process before verify") without hand-listing every wording,
# while staying fully deterministic (no LLM in the loop) for reproducibility.

_STOP = {"a", "an", "the", "of", "in", "on", "to", "is", "are", "be", "via",
         "and", "or", "with", "for", "as", "at", "by", "not", "no", "it"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


def _stem(tok: str) -> str:
    return tok[:5]  # crude: collapses verify/verified/verifyevent, process/processed


def _tokset(s: str) -> set[str]:
    return {_stem(t) for t in _norm(s).split() if t and t not in _STOP and len(t) > 1}


def _alias_hit(finding_toks: set[str], finding_norm: str, alias: str) -> bool:
    if _norm(alias) in finding_norm:
        return True
    at = _tokset(alias)
    if not at:
        return False
    if len(at) == 1:                       # single distinctive token (ssrf, md5, replay)
        return at.issubset(finding_toks)
    overlap = len(at & finding_toks) / len(at)
    return overlap >= 0.6


def _matches(finding_text: str, entry: dict) -> bool:
    finding_norm = _norm(finding_text)
    finding_toks = _tokset(finding_text)
    needles = [entry["id"].replace("_", " ")] + entry.get("aliases", [])
    return any(_alias_hit(finding_toks, finding_norm, n) for n in needles)


def score_findings(findings: list[dict] | None, answer_key: dict) -> dict:
    vulns = answer_key["vulns"]
    red_herrings = answer_key.get("red_herrings", [])
    findings = findings or []

    matched_ids = set()
    rh_hits = 0
    false_pos = 0

    for f in findings:
        text = f"{f.get('title','')} {f.get('description','')} {f.get('file','')}"
        hit_vuln = next((v for v in vulns if _matches(text, v) and v["id"] not in matched_ids), None)
        if hit_vuln:
            matched_ids.add(hit_vuln["id"])
            continue
        if any(_matches(text, rh) for rh in red_herrings):
            rh_hits += 1
            continue
        # already-claimed vuln repeats aren't penalized; genuinely-unknown = FP
        if not any(_matches(text, v) for v in vulns):
            false_pos += 1

    recall = len(matched_ids) / len(vulns) if vulns else 0.0
    denom = len(matched_ids) + false_pos + rh_hits
    precision = (len(matched_ids) / denom) if denom else 0.0
    return {
        "score": round(100 * recall * precision, 1),
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "matched": sorted(matched_ids),
        "missed": [v["id"] for v in vulns if v["id"] not in matched_ids],
        "red_herring_hits": rh_hits,
        "false_positives": false_pos,
    }
