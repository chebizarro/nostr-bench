#!/usr/bin/env python3
"""Sweep drydock model->role configurations on the 2x P40 rig.

Each run starts llama-server(s) for one configuration, points drydock's role
endpoints (DRYDOCK_{PLANNER,CODER32B,LLM70B,CODER14B}_*) at them, and runs
drydock-bench over the hidden dataset. Results are resumable JSONL under
runs/drydock/<phase>/; grade them with report.py.

Phases (see roster.yaml):
  screen      every model serves every role; first listed quant; n=1
  efficiency  one-factor-at-a-time variants of chosen models; n=3
                quant | thinking off/effort | speculative (ngram/MTP/DFlash) |
                split-mode row | annotated-line dataset
  deploy      a planner model and a reviewer model on separate cards; n=3

Examples:
  python3 sweep.py preflight
  python3 sweep.py run --phase screen --dry-run
  python3 sweep.py run --phase screen --models qwen3.8-27b,gemma-4-26b-a4b
  python3 sweep.py run --phase efficiency --models qwen3.6-35b-a3b,qwen3.8-27b
  python3 sweep.py run --phase deploy --planner gpt-oss-20b@MXFP4 --reviewer qwen3.8-27b@Q5_K_M
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml is required: pip install -r ../../requirements.txt")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
# Every route reviewengine.routeEndpoint can select. The security routes must
# point at the model under test too, or a planner choosing sec70b would hit
# an inherited endpoint (or none) instead.
REVIEWER_ROLES = ("CODER32B", "LLM70B", "CODER14B", "SEC70B", "SECCLASSIFY", "SECLOCALIZE")


# --------------------------------------------------------------------------
# configuration model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Variant:
    model: dict = field(hash=False, compare=False)
    quant: str = ""
    thinking: str = "auto"      # auto (production) | off | low | medium | high
    spec: str = "none"          # none | ngram-mod | draft-mtp | draft-dflash
    split_mode: str = ""        # '' = roster default
    annotate: bool = False      # use the annotated-lines dataset

    @property
    def mid(self) -> str:
        return self.model["id"]

    @property
    def tag(self) -> str:
        t = f"{self.mid}@{self.quant}"
        if self.thinking != "auto":
            t += f"+think-{self.thinking}"
        if self.spec != "none":
            t += f"+spec-{self.spec}"
        if self.split_mode:
            t += f"+sm-{self.split_mode}"
        return t

    def gpus_needed(self) -> int:
        m = self.model
        if self.quant in m.get("gpus_by_quant", {}):
            return int(m["gpus_by_quant"][self.quant])
        if "gpus" in m:
            return int(m["gpus"])
        return 1 if m["quants"][self.quant] <= 19.0 else 2


def parse_variant(spec: str, roster: dict) -> Variant:
    """'id@QUANT+think-off+spec-ngram-mod+sm-row' -> Variant."""
    head, *mods = spec.split("+")
    mid, _, quant = head.partition("@")
    model = model_by_id(roster, mid)
    v = Variant(model=model, quant=quant or next(iter(model["quants"])))
    if v.quant not in model["quants"]:
        sys.exit(f"{mid}: unknown quant {v.quant}; roster has {list(model['quants'])}")
    for mod in mods:
        k, _, val = mod.partition("-")
        if k == "think":
            v = replace(v, thinking=val)
        elif k == "spec":
            v = replace(v, spec=val)
        elif k == "sm":
            v = replace(v, split_mode=val)
        else:
            sys.exit(f"unknown modifier {mod!r} in {spec!r}")
    return v


def model_by_id(roster: dict, mid: str) -> dict:
    for m in roster["models"]:
        if m["id"] == mid:
            return m
    sys.exit(f"model {mid!r} not in roster")


# --------------------------------------------------------------------------
# llama-server lifecycle
# --------------------------------------------------------------------------

class Server:
    def __init__(self, v: Variant, gpus: list[int], port: int, roster: dict, args, log_dir: Path):
        self.v, self.gpus, self.port, self.roster, self.args = v, gpus, port, roster, args
        self.log_path = log_dir / f"server-{v.tag.replace('/', '_')}-{port}.log"
        self.proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    @property
    def alias(self) -> str:
        return self.v.tag

    def cmd(self) -> list[str]:
        d, m, v = self.roster["serve_defaults"], self.v.model, self.v
        repo = m["hf_mtp"] if v.spec == "draft-mtp" and m.get("hf_mtp") else m["hf"]
        a = [self.args.llama_bin, "-hf", f"{repo}:{v.quant}", "--host", "127.0.0.1", "--port", str(self.port),
             "-a", self.alias, "-c", str(m.get("ctx", d["ctx"])), "-ngl", "999", "-fa", str(d["flash_attn"]),
             "-ctk", d["cache_type"], "-ctv", d["cache_type"], "-np", str(d["parallel"])]
        if len(self.gpus) > 1:
            a += ["-sm", v.split_mode or d["split_mode"], "-ts", ",".join("1" for _ in self.gpus)]
        if m.get("offload"):
            a += ["--n-cpu-moe", str(m["offload"]["n_cpu_moe"])]
        if v.thinking == "off":
            a += ["--reasoning", "off"]
        elif v.thinking in ("low", "medium", "high"):
            a += ["--reasoning-effort", v.thinking]
        if v.spec != "none":
            a += ["--spec-type", v.spec]
            if v.spec in ("draft-dflash", "draft-simple", "draft-eagle3") or (v.spec == "draft-mtp" and not m.get("hf_mtp")):
                if not m.get("draft_hf"):
                    raise ValueError(f"{m['id']}: spec {v.spec} needs draft_hf in roster.yaml")
                a += ["-hfd", m["draft_hf"]]
        return a + list(d.get("extra", []))

    def start(self) -> None:
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(map(str, self.gpus)))
        self.log = open(self.log_path, "ab")
        self.log.write(f"\n=== {time.ctime()} {' '.join(self.cmd())}\n".encode())
        self.log.flush()
        self.proc = subprocess.Popen(self.cmd(), env=env, stdout=self.log, stderr=subprocess.STDOUT,
                                     start_new_session=True)

    def wait_healthy(self, timeout_s: int) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited ({self.proc.returncode}); see {self.log_path}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=5) as r:
                    if r.status == 200:
                        return
            except Exception:
                pass
            time.sleep(5)
        raise TimeoutError(f"llama-server not healthy after {timeout_s}s; see {self.log_path}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, 15)
            try:
                self.proc.wait(60)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, 9)
        if getattr(self, "log", None):
            self.log.close()


class GpuSampler(threading.Thread):
    """Samples nvidia-smi so reports can show peak VRAM and mean board power."""

    def __init__(self, every_s: float = 2.0):
        super().__init__(daemon=True)
        self.every_s, self.samples, self._stop = every_s, [], threading.Event()
        self.available = shutil.which("nvidia-smi") is not None

    def run(self) -> None:
        while self.available and not self._stop.is_set():
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used,power.draw,utilization.gpu",
                                      "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
                row = {}
                for line in out.strip().splitlines():
                    i, mem, pw, util = [x.strip() for x in line.split(",")]
                    row[i] = {"mem_mb": float(mem), "power_w": float(pw), "util": float(util)}
                self.samples.append(row)
            except Exception:
                pass
            self._stop.wait(self.every_s)

    def summary(self) -> dict:
        self._stop.set()
        if not self.samples:
            return {}
        gpus = sorted({g for s in self.samples for g in s})
        return {g: {"peak_mem_mb": max(s[g]["mem_mb"] for s in self.samples if g in s),
                    "mean_power_w": round(sum(s[g]["power_w"] for s in self.samples if g in s) / len(self.samples), 1),
                    "mean_util": round(sum(s[g]["util"] for s in self.samples if g in s) / len(self.samples), 1)}
                for g in gpus}


# --------------------------------------------------------------------------
# runs
# --------------------------------------------------------------------------

@dataclass
class Run:
    phase: str
    label: str
    servers: list[tuple[Variant, list[int]]]   # (variant, gpus); empty for hosted runs
    roles: dict[str, int]                       # role -> index into servers
    annotate: bool = False
    hosted: dict | None = None                  # {model, extra_body} for the OpenRouter arm


OPENROUTER_URL = "https://openrouter.ai/api/v1"


def dataset_for(run: Run, args) -> Path:
    if args.agentic:
        return Path(args.dataset_agentic)
    return Path(args.dataset_annotated if run.annotate else args.dataset)


def case_ids(path: Path) -> set[str]:
    return {c["case_id"] for c in json.loads(path.read_text())["cases"]}


def completed(out: Path, wanted: set[str], retry_errors: bool = False) -> int:
    """Cases already graded. Failed cases count as done: a timeout or
    unrepairable JSON is a measured outcome, and silently re-running it would
    turn the score into best-of-N. --retry-errors is for infra crashes only."""
    if not out.exists():
        return 0
    status: dict[str, bool] = {}
    for line in out.read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "case":
            status[d["case_id"]] = bool(d.get("ok"))
    return sum(1 for cid, ok in status.items() if cid in wanted and (ok or not retry_errors))


def execute(run: Run, reps: int, roster: dict, args) -> None:
    ds = dataset_for(run, args)
    wanted = case_ids(ds)
    total = len(wanted)
    out_dir = Path(args.runs_dir) / run.phase
    out_dir.mkdir(parents=True, exist_ok=True)
    pending = [r for r in range(1, reps + 1)
               if completed(out_dir / f"{run.label}#r{r}.jsonl", wanted, args.retry_errors) < total]
    if not pending:
        print(f"skip {run.label}: complete")
        return
    if run.hosted:
        return execute_hosted(run, pending, ds, wanted, out_dir, roster, args)
    servers = [Server(v, g, args.base_port + i, roster, args, out_dir) for i, (v, g) in enumerate(run.servers)]
    if args.dry_run:
        for s in servers:
            print(f"[dry-run] CUDA_VISIBLE_DEVICES={','.join(map(str, s.gpus))} {' '.join(s.cmd())}")
        print(f"[dry-run]   -> {run.label} reps {pending} on {ds.name}")
        return
    try:
        for s in servers:
            s.start()
        for s in servers:
            s.wait_healthy(args.load_timeout)
        env = dict(os.environ)
        for role in ("PLANNER",) + REVIEWER_ROLES:
            s = servers[run.roles[role]]
            env[f"DRYDOCK_{role}_BASE_URL"] = s.base_url
            env[f"DRYDOCK_{role}_MODEL"] = s.alias
        notes = " | ".join(f"gpus={','.join(map(str, s.gpus))} " + " ".join(s.cmd()[1:]) for s in servers)
        for r in pending:
            out = out_dir / f"{run.label}#r{r}.jsonl"
            sampler = GpuSampler()
            sampler.start()
            print(f"run {run.label} rep {r} ({completed(out, wanted)}/{total} done)", flush=True)
            cmd = [args.bench_bin, "-dataset", str(ds), "-out", str(out), "-label", run.label, "-notes", notes]
            if args.prompt_variant:
                cmd += ["-prompt-variant", args.prompt_variant]
            if args.agentic:
                cmd.append("-agentic")
            if args.max_tokens:
                cmd += ["-max-tokens", str(args.max_tokens)]
            if args.retry_errors:
                cmd.append("-retry-errors")
            subprocess.run(cmd, env=env, check=False)
            gpu = sampler.summary()
            if gpu:
                Path(str(out) + ".gpu.json").write_text(json.dumps(gpu, indent=1))
    except (RuntimeError, TimeoutError, ValueError) as e:
        print(f"FAILED {run.label}: {e}", file=sys.stderr)
        (out_dir / f"{run.label}.failed").write_text(str(e))
    finally:
        for s in servers:
            s.stop()


def execute_hosted(run: Run, pending: list[int], ds: Path, wanted: set[str], out_dir: Path, roster: dict, args) -> None:
    """OpenRouter arm: every drydock role points at one hosted model."""
    h = run.hosted
    extra = json.dumps(h["extra_body"], separators=(",", ":"))
    workers = args.workers or roster["phases"]["openrouter"].get("workers", 4)
    if args.dry_run:
        print(f"[dry-run] {run.label}: model={h['model']} reps {pending} workers={workers} extra_body={extra}")
        return
    env = dict(os.environ, DRYDOCK_LLM_API_KEY=openrouter_key())
    for role in ("PLANNER",) + REVIEWER_ROLES:
        env[f"DRYDOCK_{role}_BASE_URL"] = OPENROUTER_URL
        env[f"DRYDOCK_{role}_MODEL"] = h["model"]
        env.pop(f"DRYDOCK_{role}_API_KEY", None)
    for r in pending:
        out = out_dir / f"{run.label}#r{r}.jsonl"
        print(f"run {run.label} rep {r} ({completed(out, wanted)}/{len(wanted)} done)", flush=True)
        cmd = [args.bench_bin, "-dataset", str(ds), "-out", str(out), "-label", run.label,
               "-notes", f"openrouter {h['model']}", "-workers", str(workers), "-retries", "3",
               "-call-timeout", "10m", "-extra-body", extra]
        if args.prompt_variant:
            cmd += ["-prompt-variant", args.prompt_variant]
        if args.agentic:
            cmd.append("-agentic")
        if args.max_tokens:
            cmd += ["-max-tokens", str(args.max_tokens)]
        if args.retry_errors:
            cmd.append("-retry-errors")
        subprocess.run(cmd, env=env, check=False)


def openrouter_key() -> str:
    """OPENROUTER_API_KEY, else the gitignored nostr-bench/.orkey file."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    keyfile = ROOT / ".orkey"
    if not key and keyfile.exists():
        key = keyfile.read_text().strip()
    if not key:
        sys.exit("set OPENROUTER_API_KEY or write the key to nostr-bench/.orkey (gitignored)")
    return key


def verify_openrouter(roster: dict, args) -> int:
    """One 20-token JSON-mode request per model id before paying for a sweep."""
    key, bad = openrouter_key(), 0
    for m in [m for m in roster["models"] if m.get("openrouter")] + roster.get("references", []):
        body = json.dumps({"model": m["openrouter"], "max_tokens": 20, "temperature": 0,
                           "response_format": {"type": "json_object"}, "usage": {"include": True},
                           "provider": {"require_parameters": True},
                           "messages": [{"role": "user", "content": 'Reply with {"ok": true}'}]}).encode()
        req = urllib.request.Request(OPENROUTER_URL + "/chat/completions", data=body, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            print(f"ok   {m['openrouter']:42} provider={d.get('provider')} cost=${(d.get('usage') or {}).get('cost', 0):.5f}")
        except Exception as e:  # HTTPError carries the provider message
            bad += 1
            detail = e.read().decode()[:200] if hasattr(e, "read") else str(e)
            print(f"FAIL {m['openrouter']:42} {detail}")
    return 1 if bad else 0


def plan_openrouter(roster: dict, args) -> list[Run]:
    """Full-precision accuracy screen of every roster model available on
    OpenRouter, plus cloud-only references as a ceiling. Hosted latency says
    nothing about P40 speed; throughput is measured later on Lemmy."""
    entries = [m for m in roster["models"] if m.get("openrouter")]
    if not args.no_references:
        entries += [dict(r, reference=True) for r in roster.get("references", [])]
    runs = []
    for m in entries:
        if args.models and m["id"] not in args.models:
            continue
        if m.get("offload") and not args.include_offload and not m.get("reference"):
            continue
        base = {"usage": {"include": True}, "provider": {"require_parameters": True}}
        variants = [("", base)]
        if args.thinking in ("both", "off"):
            if m.get("thinking") is True:
                variants.append(("+think-off", dict(base, reasoning={"enabled": False})))
            elif m.get("thinking") == "effort":
                variants.append(("+think-low", dict(base, reasoning={"effort": "low"})))
        if args.thinking == "off" and len(variants) > 1:
            variants = variants[1:]
        prefix = "ref:" if m.get("reference") else "or:"
        for suffix, body in variants:
            runs.append(Run("openrouter", f"{prefix}{m['id']}{suffix}", [], {}, hosted={"model": m["openrouter"], "extra_body": body}))
    return runs


def single(v: Variant, phase: str, annotate: bool = False) -> Run:
    gpus = [0] if v.gpus_needed() == 1 else [0, 1]
    label = v.tag + ("+annot" if annotate else "")
    return Run(phase, label, [(v, gpus)], {r: 0 for r in ("PLANNER",) + REVIEWER_ROLES}, annotate)


def plan_screen(roster: dict, args) -> list[Run]:
    runs = []
    for m in roster["models"]:
        if args.models and m["id"] not in args.models:
            continue
        if m.get("offload") and not args.include_offload:
            continue
        runs.append(single(Variant(model=m, quant=next(iter(m["quants"]))), "screen"))
    return runs


def plan_efficiency(roster: dict, args) -> list[Run]:
    if not args.models:
        sys.exit("efficiency: pass --models (pick the top of `report.py --phase screen`)")
    runs = []
    for spec in args.models:
        # A full spec (id@QUANT+think-off...) sets the baseline every axis varies from.
        base = parse_variant(spec, roster)
        m, mid = base.model, base.mid
        if "@" not in spec and args.base_quant.get(mid):
            base = replace(base, quant=args.base_quant[mid])
        variants = [base]
        variants += [replace(base, quant=q) for q in m["quants"] if q != base.quant
                     and replace(base, quant=q).gpus_needed() <= 2 and not m.get("offload")]
        if m.get("thinking") is True:
            variants.append(replace(base, thinking="auto" if base.thinking == "off" else "off"))
        elif m.get("thinking") == "effort":
            variants += [replace(base, thinking="low"), replace(base, thinking="high")]
        variants += [replace(base, spec=s) for s in m.get("spec", [])]
        if base.gpus_needed() == 2 and "dense" in m.get("arch", ""):
            variants.append(replace(base, split_mode="row"))
        runs += [single(v, "efficiency") for v in variants]
        runs.append(single(base, "efficiency", annotate=True))
    return runs


def plan_deploy(roster: dict, args) -> list[Run]:
    if not (args.planner and args.reviewer):
        sys.exit("deploy: pass --planner id@QUANT[+mods] and --reviewer id@QUANT[+mods]")
    p, r = parse_variant(args.planner, roster), parse_variant(args.reviewer, roster)
    if p.gpus_needed() + r.gpus_needed() > 2:
        sys.exit(f"deploy: {p.tag} ({p.gpus_needed()} GPU) + {r.tag} ({r.gpus_needed()} GPU) exceeds 2 cards")
    small = 0 if args.coder14b_on == "planner" else 1
    roles = {"PLANNER": 0, **{role: 1 for role in REVIEWER_ROLES}, "CODER14B": small}
    label = f"deploy[P={p.tag}|R={r.tag}" + ("|14b=P" if small == 0 else "") + "]"
    return [Run("deploy", label, [(p, [1]), (r, [0])], roles)]


def preflight(args) -> int:
    ok = True
    help_text = subprocess.run([args.llama_bin, "--help"], capture_output=True, text=True).stdout
    for flag in ("--spec-type", "--reasoning", "--n-cpu-moe", "-hf,"):
        has = flag in help_text
        ok &= has
        print(f"llama-server {flag:14} {'ok' if has else 'MISSING (update llama.cpp)'}")
    if shutil.which("nvidia-smi"):
        print(subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,compute_cap,driver_version",
                              "--format=csv"], capture_output=True, text=True).stdout)
    else:
        print("nvidia-smi not found (not the GPU rig?)")
    for p in (args.bench_bin, args.dataset, args.dataset_annotated):
        exists = Path(p).exists() or shutil.which(p)
        ok &= bool(exists)
        print(f"{'ok' if exists else 'MISSING':8} {p}")
    print("build llama.cpp for Pascal with: cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=61 && cmake --build build -j")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["preflight", "verify-or", "run", "plan"])
    ap.add_argument("--phase", choices=["openrouter", "screen", "efficiency", "deploy"], default="screen")
    ap.add_argument("--roster", default=str(HERE / "roster.yaml"))
    ap.add_argument("--dataset", default=str(HERE / "data/drydock-planted-v2.json"))
    ap.add_argument("--dataset-annotated", default=str(HERE / "data/drydock-planted-v2-annotated.json"))
    ap.add_argument("--dataset-agentic", default=str(HERE / "data/drydock-agentic-v2.json"))
    ap.add_argument("--agentic", action="store_true",
                    help="drydock's default agentic path (discovery + tool-using reviewer) on real repo snapshots")
    ap.add_argument("--runs-dir", default=str(ROOT / "runs/drydock"))
    ap.add_argument("--bench-bin", default=os.environ.get("DRYDOCK_BENCH_BIN", str(ROOT / ".work/drydock-bench")))
    ap.add_argument("--llama-bin", default=os.environ.get("LLAMA_SERVER_BIN", "llama-server"))
    ap.add_argument("--models", type=lambda s: [x for x in s.split(",") if x], default=[])
    ap.add_argument("--base-quant", type=lambda s: dict(x.split("@") for x in s.split(",") if x), default={},
                    help="efficiency baseline quant per model, e.g. qwen3.8-27b@Q5_K_M")
    ap.add_argument("--planner")
    ap.add_argument("--reviewer")
    ap.add_argument("--coder14b-on", choices=["planner", "reviewer"], default="reviewer",
                    help="deploy: which server answers the small coder14b route")
    ap.add_argument("--reps", type=int)
    ap.add_argument("--include-offload", action="store_true")
    ap.add_argument("--thinking", choices=["both", "default", "off"], default="both",
                    help="openrouter: provider-default reasoning, reasoning disabled, or both as separate configs")
    ap.add_argument("--no-references", action="store_true", help="openrouter: skip the cloud-only ceiling models")
    ap.add_argument("--workers", type=int, help="openrouter: concurrent cases per model (default from roster)")
    ap.add_argument("--parallel-configs", type=int, default=1, help="openrouter: configs run concurrently")
    ap.add_argument("--prompt-variant", choices=["calibrated"],
                    help="experimental prompt fix (drydock-bench -prompt-variant); compare against the same label without it")
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="cap completion tokens per call (production sends none; tests the runaway-generation fix)")
    ap.add_argument("--retry-errors", action="store_true",
                    help="re-run failed cases (only after an infrastructure crash, e.g. the server died)")
    ap.add_argument("--base-port", type=int, default=18100)
    ap.add_argument("--load-timeout", type=int, default=3600, help="seconds; first start downloads the GGUF")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.cmd == "preflight":
        return preflight(args)
    roster = yaml.safe_load(Path(args.roster).read_text())
    if args.cmd == "verify-or":
        return verify_openrouter(roster, args)
    runs = {"openrouter": plan_openrouter, "screen": plan_screen, "efficiency": plan_efficiency,
            "deploy": plan_deploy}[args.phase](roster, args)
    reps = args.reps or roster["phases"][args.phase]["reps"]
    if args.max_tokens:
        for run in runs:  # a capped run is a different configuration
            run.label += f"+cap{args.max_tokens}"
    if args.prompt_variant:
        for run in runs:  # so is a run with modified system prompts
            run.label += f"+{args.prompt_variant}-prompt"
    if args.agentic:
        for run in runs:  # and the agentic review path
            run.label += "+agentic"
    if args.cmd == "plan":
        args.dry_run = True
    if args.phase == "openrouter" and args.parallel_configs > 1 and not args.dry_run:
        # Hosted configs share no hardware, so run several at once.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(args.parallel_configs) as pool:
            list(pool.map(lambda run: execute(run, reps, roster, args), runs))
        return 0
    for run in runs:
        execute(run, reps, roster, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
