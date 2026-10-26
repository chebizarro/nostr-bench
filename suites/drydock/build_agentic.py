#!/usr/bin/env python3
"""Attach real repository snapshots to the planted-bug dataset for agentic mode.

drydock's default review path is agentic: it freezes a pinned Git snapshot,
applies the patch, and lets discovery/reviewer loops read the repository via
tools. That needs, per case, a clone that contains a base commit where the
patch applies. For each kind-1617 source patch this script:

  1. clones the repo (blobless partial clone) from the first reachable clone URL
     found in the corpus (exact repo_id first, then any announcement with the
     same identifier);
  2. picks the base: the parent of the patch's own commit if that commit exists
     upstream, else the newest default-branch commit at or before the patch's
     created_at where `git apply --check` of the ORIGINAL diff succeeds;
  3. verifies the case's (possibly mutated) diff also applies at that base.

Cases whose repo is unreachable or that never apply are dropped and reported.
Output: data/drydock-agentic-v1.json (same cases + bench_meta.agentic).

  python3 -I build_agentic.py --db /path/drydock.db
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ENV = {"GIT_TERMINAL_PROMPT": "0", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def git(repo: Path, *args: str, timeout: int = 300, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout,
                          env=ENV, input=input_text)


def reachable(url: str) -> bool:
    try:
        r = subprocess.run(["git", "ls-remote", "--heads", url], capture_output=True, text=True, timeout=25, env=ENV)
        return r.returncode == 0 and bool(r.stdout.strip())
    except subprocess.TimeoutExpired:
        return False


def clone_urls(db: sqlite3.Connection, repo_id: str) -> list[str]:
    urls: list[str] = []
    rows = list(db.execute("select clone_urls from repositories where repo_id=?", (repo_id,)))
    ident = repo_id.split(":", 1)[-1]
    rows += list(db.execute("select clone_urls from repositories where identifier=? and clone_urls!=''", (ident,)))
    for (cu,) in rows:
        for u in (cu or "").split(","):
            if u.startswith("http") and u not in urls:
                urls.append(u)
    return urls


def ensure_clone(urls: list[str], dest: Path) -> str | None:
    if (dest / ".git").exists() or (dest / "HEAD").exists():
        return "cached"
    for u in urls:
        if not reachable(u):
            continue
        r = subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", u, str(dest)],
                           capture_output=True, text=True, timeout=900, env=ENV)
        if r.returncode == 0:
            return u
        subprocess.run(["rm", "-rf", str(dest)])
    return None


def applies(repo: Path, base: str, diff: str) -> bool:
    """git apply --check against `base` using a throwaway index (no checkout)."""
    with tempfile.TemporaryDirectory() as tmp:
        idx = Path(tmp) / "index"
        env = dict(ENV, GIT_INDEX_FILE=str(idx))
        if subprocess.run(["git", "-C", str(repo), "read-tree", base], env=env, capture_output=True,
                          timeout=300).returncode:
            return False
        r = subprocess.run(["git", "-C", str(repo), "apply", "--check", "--cached", "-"], env=env,
                           input=diff, capture_output=True, text=True, timeout=300)
        return r.returncode == 0


def find_base(repo: Path, commit: str | None, created_at: int, diff: str, max_scan: int) -> str | None:
    if commit and git(repo, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0:
        parent = git(repo, "rev-parse", f"{commit}^").stdout.strip()
        if parent and applies(repo, parent, diff):
            return parent
    head = git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip() or "HEAD"
    revs = git(repo, "rev-list", f"--before={created_at}", f"--max-count={max_scan}", head).stdout.split()
    for rev in revs:
        if applies(repo, rev, diff):
            return rev
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--dataset", default=str(HERE / "data/drydock-planted-v2.json"))
    ap.add_argument("--out", default=str(HERE / "data/drydock-agentic-v2.json"))
    ap.add_argument("--repos", default=str(ROOT / ".work/agentic-repos"))
    ap.add_argument("--max-scan", type=int, default=400, help="commits to try when the patch commit is not upstream")
    args = ap.parse_args()

    db = sqlite3.connect(f"file:{args.db}?mode=ro&immutable=1", uri=True)
    ds = json.loads(Path(args.dataset).read_text())
    repos_root = Path(args.repos)
    repos_root.mkdir(parents=True, exist_ok=True)

    src: dict[str, dict] = {}
    for c in ds["cases"]:
        eid = c["bench_meta"]["source_event_id"]
        if eid not in src:
            repo_id, content, created = db.execute(
                "select repo_id, content, created_at from patch_events where event_id=?", (eid,)).fetchone()
            commit = content.split()[1] if content.startswith("From ") else None
            src[eid] = {"repo_id": repo_id, "commit": commit, "created_at": created}

    by_repo: dict[str, list[str]] = {}
    for eid, s in src.items():
        by_repo.setdefault(s["repo_id"], []).append(eid)

    urls = {rid: clone_urls(db, rid) for rid in by_repo}  # sqlite handle stays on this thread

    def prepare_repo(repo_id: str) -> tuple[str, Path | None, str | None]:
        dest = repos_root / (repo_id.replace(":", "_")[:120])
        how = ensure_clone(urls[repo_id], dest)
        return repo_id, (dest if how else None), how

    with ThreadPoolExecutor(6) as pool:
        cloned = {rid: (path, how) for rid, path, how in pool.map(prepare_repo, by_repo)}

    # Base per source patch, chosen with the ORIGINAL diff (the clean control
    # case shares it; planted cases are checked separately below).
    originals = {c["bench_meta"]["source_event_id"]: c["patch_diff"] for c in ds["cases"]
                 if c["bench_meta"]["kind"] == "clean"}
    bases: dict[str, str | None] = {}
    for eid, s in src.items():
        path, _ = cloned.get(s["repo_id"], (None, None))
        if path is None:
            bases[eid] = None
            continue
        content = db.execute("select content from patch_events where event_id=?", (eid,)).fetchone()[0]
        diff = originals.get(eid) or content[content.find("\ndiff --git ") + 1:]
        bases[eid] = find_base(path, s["commit"], s["created_at"], diff, args.max_scan)

    kept, dropped = [], []
    for c in ds["cases"]:
        eid = c["bench_meta"]["source_event_id"]
        s = src[eid]
        path, _ = cloned.get(s["repo_id"], (None, None))
        base = bases.get(eid)
        if path is None:
            dropped.append((c["case_id"], "repo unreachable"))
        elif base is None:
            dropped.append((c["case_id"], "no base where the patch applies"))
        elif not applies(path, base, c["patch_diff"]):
            dropped.append((c["case_id"], "case diff does not apply at base"))
        else:
            c = json.loads(json.dumps(c))
            c["bench_meta"]["agentic"] = {"repo_dir": path.name, "base": base,
                                          "upstream_commit": base == git(path, "rev-parse", f"{s['commit']}^").stdout.strip()
                                          if s["commit"] else False}
            kept.append(c)

    out = {"id": ds["id"].replace("planted", "agentic"), "repos_root": str(repos_root), "cases": kept}
    Path(args.out).write_text(json.dumps(out, indent=1))
    kinds: dict[str, int] = {}
    for c in kept:
        kinds[c["bench_meta"]["kind"]] = kinds.get(c["bench_meta"]["kind"], 0) + 1
    print(f"kept {len(kept)}/{len(ds['cases'])} cases {kinds}; repos cloned {sum(1 for p, _ in cloned.values() if p)}/{len(cloned)}",
          file=sys.stderr)
    reasons: dict[str, int] = {}
    for _, why in dropped:
        reasons[why] = reasons.get(why, 0) + 1
    print("dropped:", reasons, file=sys.stderr)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
