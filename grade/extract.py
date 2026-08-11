"""Pull code / JSON out of a model's free-text reply.

Mode A returns prose with fenced blocks; we need to reconstruct files. We accept
two conventions and prefer the explicit one:

  1. Explicit per-file:  ```ts title=src/nip01.ts  ... ```   (or `// file: src/nip01.ts`
     as the first line of the block)
  2. Single unlabeled ```ts block -> written to the task's primary target file.
"""
from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?P<info>[^\n]*)\n(?P<body>.*?)```", re.DOTALL)
_FILE_HINT = re.compile(r"(?:title=|file:|filename:)\s*(?P<path>[\w./-]+)")


def extract_files(text: str, default_target: str) -> dict[str, str]:
    """Return {relative_path: contents}. Falls back to default_target."""
    out: dict[str, str] = {}
    for m in _FENCE.finditer(text):
        info = m.group("info").strip()
        body = m.group("body")
        path = None
        hint = _FILE_HINT.search(info)
        if hint:
            path = hint.group("path")
        else:
            first = body.splitlines()[0] if body.splitlines() else ""
            fh = _FILE_HINT.search(first)
            if fh:
                path = fh.group("path")
                body = "\n".join(body.splitlines()[1:])
        if path:
            out[path] = body
    if not out:
        # single unlabeled block -> default target
        blocks = [m.group("body") for m in _FENCE.finditer(text)]
        if blocks:
            out[default_target] = blocks[-1]
    return out


def extract_findings(text: str) -> list[dict] | None:
    """For audit tasks: pull the JSON findings array the model was told to emit."""
    # Prefer a fenced ```json block; else first top-level [ ... ] array.
    for m in _FENCE.finditer(text):
        if "json" in m.group("info").lower():
            try:
                data = json.loads(m.group("body"))
                return data if isinstance(data, list) else data.get("findings")
            except json.JSONDecodeError:
                continue
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None
