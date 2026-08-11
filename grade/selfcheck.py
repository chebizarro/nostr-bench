"""`make smoke` entrypoint: verify the harness wiring without hitting any API.

Checks: config parses, every task dir has the required files, extractors work on
a synthetic reply, findings scorer math is sane.
"""
from __future__ import annotations

import os
import sys

import yaml

from .extract import extract_files, extract_findings
from .findings import score_findings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED = {
    "n1_implement": ["task.md", "starter", "tests_hidden", "answer_key.json"],
    "n2_debug": ["task.md", "starter", "tests_hidden", "answer_key.json"],
    "s1_audit": ["task.md", "starter", "answer_key.json"],
    "s2_nostr_sec": ["task.md", "starter", "answer_key.json"],
}


def main() -> int:
    ok = True

    cfg = yaml.safe_load(open(os.path.join(ROOT, "runmatrix.yaml")))
    n_models = len(cfg["models"])
    print(f"[ok] runmatrix.yaml parses: {n_models} models, {len(cfg['tasks'])} tasks")

    for task, files in REQUIRED.items():
        for fn in files:
            p = os.path.join(ROOT, "tasks", task, fn)
            if not os.path.exists(p):
                print(f"[MISSING] tasks/{task}/{fn}")
                ok = False

    reply = "Here you go:\n```ts title=src/nip01.ts\nexport const x = 1\n```"
    files = extract_files(reply, "src/main.ts")
    assert files.get("src/nip01.ts", "").strip() == "export const x = 1", files
    print("[ok] code extractor")

    findings = extract_findings('```json\n[{"title":"SQL injection in db.ts"}]\n```')
    assert findings and findings[0]["title"].startswith("SQL"), findings
    print("[ok] findings extractor")

    key = {"vulns": [{"id": "sqli", "aliases": ["sql injection"]},
                     {"id": "ssrf", "aliases": ["server side request forgery"]}],
           "red_herrings": [{"id": "rh_cors", "aliases": ["permissive cors"]}]}
    sc = score_findings([{"title": "SQL injection", "description": "user input in query"},
                         {"title": "permissive CORS everywhere"}], key)
    assert sc["recall"] == 0.5 and sc["red_herring_hits"] == 1, sc
    print(f"[ok] findings scorer: {sc}")

    print("SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
