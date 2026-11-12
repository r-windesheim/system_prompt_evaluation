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
                 max_tokens: int = 600, timeout: float = 120.0):
        import httpx

        self.base_url = base_url.rstrip("/")
        self.model = model
        key = api_key or os.environ.get("SPET_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)
        self._sem = asyncio.Semaphore(max_concurrency)
        self.max_tokens = max_tokens
        self._cache_path = Path(cache_dir) / f"{_slug(base_url)}__{_slug(model)}.jsonl" if cache_dir else None
        self._cache: dict[str, str] = {}
        if self._cache_path and self._cache_path.exists():
            for line in self._cache_path.read_text().splitlines():
                row = json.loads(line)
                self._cache[row["key"]] = row["text"]

    def _payload(self, system: str, user: str, temperature: float, seed: int) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "seed": seed,
            "max_tokens": self.max_tokens,
        }

    async def complete(self, system: str, user: str, *, temperature: float, seed: int) -> str:
        payload = self._payload(system, user, temperature, seed)
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        async with self._sem:
            for attempt in range(4):
                try:
                    r = await self._client.post(f"{self.base_url}/chat/completions", json=payload)
                    if r.status_code in (429, 500, 502, 503, 504):
                        raise RuntimeError(f"HTTP {r.status_code}")
                    r.raise_for_status()
                    text = r.json()["choices"][0]["message"]["content"] or ""
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** attempt)
        self._cache[key] = text
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_path.open("a") as f:
                f.write(json.dumps({"key": key, "text": text}) + "\n")
        return text

    async def aclose(self) -> None:
        await self._client.aclose()


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s)[:80]
