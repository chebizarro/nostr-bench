"""Run untrusted task code with no network.

Priority: docker (best isolation) -> firejail -> refuse. S1/S2 contain
exploitable code and Mode B hands the model a shell, so grading MUST NOT run
against the host network or filesystem. Set NOSTR_BENCH_ALLOW_UNSANDBOXED=1 to
override on a machine you've isolated yourself.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class RunOut:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: list[str], cwd: str, timeout: int = 300, env: dict | None = None) -> RunOut:
    full_env = {**os.environ, **(env or {})}
    if _have("docker") and os.environ.get("NOSTR_BENCH_SANDBOX", "auto") != "off":
        wrapped = [
            "docker", "run", "--rm", "--network=none",
            "--cpus=2", "--memory=4g", "--pids-limit=512",
            "-v", f"{os.path.abspath(cwd)}:/work", "-w", "/work",
            "node:22-alpine", *cmd,
        ]
        return _exec(wrapped, cwd, timeout, full_env)
    if _have("firejail"):
        wrapped = ["firejail", "--quiet", "--net=none", "--private-tmp", f"--private={cwd}", *cmd]
        return _exec(wrapped, cwd, timeout, full_env)
    if os.environ.get("NOSTR_BENCH_ALLOW_UNSANDBOXED") == "1":
        return _exec(cmd, cwd, timeout, full_env)
    raise RuntimeError(
        "No sandbox available (docker/firejail). Refusing to run untrusted task "
        "code. Install docker, or set NOSTR_BENCH_ALLOW_UNSANDBOXED=1 if this host "
        "is already isolated."
    )


def _exec(cmd: list[str], cwd: str, timeout: int, env: dict) -> RunOut:
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return RunOut(p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired as e:
        return RunOut(124, e.stdout or "", (e.stderr or "") + "\n[timeout]", timed_out=True)
