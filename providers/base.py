"""OpenAI-compatible provider abstraction.

All three arms (OpenRouter, local llama.cpp/Ollama, Routstr) expose the same
`/chat/completions` shape, so one client covers them. The only per-arm concerns
are: base URL, auth header, and how cost is reported back.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

_HTTP_TIMEOUT = float(os.environ.get("NOSTR_BENCH_HTTP_TIMEOUT", "300"))
_MAX_ATTEMPTS = int(os.environ.get("NOSTR_BENCH_MAX_ATTEMPTS", "4"))


@dataclass
class ChatResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Optional[float] = None      # provider-reported when available
    wall_clock_s: float = 0.0
    raw: dict = field(default_factory=dict)
    finish_reason: str = ""


class Provider:
    """Thin OpenAI-compatible chat client."""

    def __init__(self, base_url: str, api_key: str, *, arm: str, headers: Optional[dict] = None,
                 price: Optional[dict] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.arm = arm                     # "cloud" | "local" | "routstr"
        self.price = price or {}           # {"in": $/M, "out": $/M} fallback for cost
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        if headers:
            self._headers.update(headers)
        # OpenRouter wants cost accounting turned on:
        self._extra_body = {}
        if arm == "cloud" and "openrouter" in self.base_url:
            self._extra_body["usage"] = {"include": True}

    @retry(stop=stop_after_attempt(_MAX_ATTEMPTS), wait=wait_exponential(min=2, max=30), reraise=True)
    def chat(self, model: str, messages: list[dict], *, tools: Optional[list] = None,
             temperature: float = 0.2, top_p: float = 1.0, max_tokens: int = 4096,
             seed: Optional[int] = None, timeout: float = _HTTP_TIMEOUT,
             reasoning: Optional[dict] = None) -> ChatResult:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            **self._extra_body,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if seed is not None:
            body["seed"] = seed
        # Bound reasoning so thinking models leave room for a final answer within max_tokens.
        if reasoning is not None:
            body["reasoning"] = reasoning

        t0 = time.time()
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions",
                               headers=self._headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        dt = time.time() - t0

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        usage = data.get("usage", {}) or {}
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)

        cost = usage.get("cost")           # OpenRouter reports this in USD
        if cost is None and self.price:
            cost = (pt / 1e6) * self.price.get("in", 0) + (ct / 1e6) * self.price.get("out", 0)

        return ChatResult(
            text=msg.get("content") or "",
            tool_calls=msg.get("tool_calls") or [],
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=cost,
            wall_clock_s=dt,
            raw=data,
            finish_reason=choice.get("finish_reason", ""),
        )


def get_provider(arm: str, price: Optional[dict] = None) -> Provider:
    """Construct a provider for an arm from environment variables."""
    if arm == "cloud":
        return Provider(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.environ["OPENROUTER_API_KEY"],
            arm="cloud",
            headers={"HTTP-Referer": "https://github.com/local/nostr-bench",
                     "X-Title": "nostr-bench"},
            price=price,
        )
    if arm == "local":
        return Provider(
            base_url=os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("LOCAL_API_KEY", "sk-local"),
            arm="local",
            price=None,   # local cost is wall-clock * rig $/hr, computed in the report layer
        )
    if arm == "routstr":
        # Cashu ecash token is the bearer key; cost is debited per token in sats.
        return Provider(
            base_url=os.environ["ROUTSTR_BASE_URL"],
            api_key=os.environ["ROUTSTR_CASHU_TOKEN"],
            arm="routstr",
            price=price,
        )
    raise ValueError(f"unknown arm: {arm}")
