"""Model providers.

``OpenAICompatible`` talks to any ``/chat/completions`` endpoint: a Modal vLLM
deployment, a local llama.cpp/vLLM server, or a hosted API. ``StubProvider``
is a deterministic fake used by the tests and for demo bundles.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Protocol


class Completion(str):
    """Answer text that also carries the endpoint's finish_reason ("stop", "length", ...)."""

    finish_reason: str | None = None

    def __new__(cls, text: str, finish_reason: str | None = None):
        obj = super().__new__(cls, text)
        obj.finish_reason = finish_reason
        return obj


class Provider(Protocol):
    name: str
    model: str

    async def complete(self, system: str, user: str, *, temperature: float, seed: int) -> str: ...


class StubProvider:
    """Calls ``fn(system, user, seed) -> str``. Records every request for inspection."""

    name = "stub"

    def __init__(self, fn: Callable[[str, str, int], str], model: str = "stub"):
        self.fn = fn
        self.model = model
        self.requests: list[dict] = []

    async def complete(self, system: str, user: str, *, temperature: float, seed: int) -> str:
        self.requests.append({"system": system, "user": user, "temperature": temperature, "seed": seed})
        return self.fn(system, user, seed)


class OpenAICompatible:
    name = "openai-compatible"

    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 cache_dir: str | Path | None = ".spet_cache", max_concurrency: int = 16,
                 max_tokens: int = 1500, timeout: float = 300.0, extra: dict | None = None):
        import httpx

        self.base_url = base_url.rstrip("/")
        self.model = model
        key = api_key or os.environ.get("SPET_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)
        self._sem = asyncio.Semaphore(max_concurrency)
        self.max_tokens = max_tokens
        # provider-specific request fields, e.g. {"reasoning_effort": "low"} for gpt-oss on vLLM
        self.extra = extra or {}
        # revision/version go into the cache key so a redeploy never mixes old and new answers
        self.revision = os.environ.get("SPET_MODEL_REVISION", "")
        self.settings = {
            "max_tokens": max_tokens, "endpoint_host": _host(base_url),
            "model_revision": self.revision or None, "vllm_version": os.environ.get("SPET_VLLM_VERSION") or None,
            **{k: v for k, v in self.extra.items() if isinstance(v, (str, int, float))},
        }
        self._cache_path = Path(cache_dir) / f"{_slug(base_url)}__{_slug(model)}.jsonl" if cache_dir else None
        self._cache: dict[str, tuple[str, str | None]] = {}
        if self._cache_path and self._cache_path.exists():
            for line in self._cache_path.read_text().splitlines():
                row = json.loads(line)
                self._cache[row["key"]] = (row["text"], row.get("finish_reason"))

    def _payload(self, system: str, user: str, temperature: float, seed: int) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "seed": seed,
            "max_tokens": self.max_tokens,
            **self.extra,
        }

    async def complete(self, system: str, user: str, *, temperature: float, seed: int) -> str:
        payload = self._payload(system, user, temperature, seed)
        key = hashlib.sha256(json.dumps({**payload, "_rev": self.revision}, sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            return Completion(*self._cache[key])
        async with self._sem:
            for attempt in range(4):
                try:
                    r = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
                    if r.status_code in (429, 500, 502, 503, 504):
                        raise RuntimeError(f"HTTP {r.status_code}")
                    r.raise_for_status()
                    choice = r.json()["choices"][0]
                    text = choice["message"].get("content") or ""
                    finish = choice.get("finish_reason")
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** attempt)
        self._cache[key] = (text, finish)
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_path.open("a") as f:
                f.write(json.dumps({"key": key, "text": text, "finish_reason": finish}) + "\n")
        return Completion(text, finish)

    async def aclose(self) -> None:
        await self._client.aclose()


def _host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or url


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)[:80]
