"""Grade a Repo Prompt oracle's full-file output for the N2 debug task.

Usage: python grade_oracle.py <oracle_name> <export_md_path>
Reads the export markdown, extracts src/nostr.ts + src/filter.ts from fenced
blocks, overlays them on the n2 starter, runs the hidden suite, prints score.
"""
import json, os, sys, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade.extract import extract_files

TASK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", "n2_debug")

def main():
    name, md_path = sys.argv[1], sys.argv[2]
    text = open(md_path).read()
    files = extract_files(text, "src/nostr.ts")
    # normalize keys to src/*.ts
    norm = {}
    for k, v in files.items():
        base = k.split("/")[-1]
        if base in ("nostr.ts", "filter.ts"):
            norm[f"src/{base}"] = v
    work = tempfile.mkdtemp(prefix="oracle_", dir=os.path.join(TASK, "..", "..", ".work"))
    shutil.copytree(os.path.join(TASK, "starter"), work, dirs_exist_ok=True)
    shutil.copytree(os.path.join(TASK, "tests_hidden"), os.path.join(work, "tests_hidden"), dirs_exist_ok=True)
    for rel, content in norm.items():
        with open(os.path.join(work, rel), "w") as f:
            f.write(content)
    # node_modules cache
    cache = os.path.join(TASK, ".nmcache")
    if os.path.isdir(cache) and not os.path.isdir(os.path.join(work, "node_modules")):
        subprocess.run(["cp", "-al", cache, os.path.join(work, "node_modules")])
    r = subprocess.run(["npx", "vitest", "run", "--reporter=json", "--outputFile=o.json"],
                       cwd=work, capture_output=True, text=True, timeout=180)
    out = os.path.join(work, "o.json")
    passed = failed = 0
    per = {}
    if os.path.exists(out):
        data = json.load(open(out))
        for s in data.get("testResults", []):
            for t in s.get("assertionResults", []):
                ok = t.get("status") == "passed"
                per[t.get("fullName") or t.get("title")] = ok
                passed += ok; failed += (not ok)
    total = passed + failed
    score = round(passed / total * 100, 1) if total else 0.0
    print(json.dumps({"oracle": name, "extracted_files": list(norm.keys()),
                      "passed": passed, "total": total, "score": score,
                      "failed_tests": [k for k, v in per.items() if not v]}))
    shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
