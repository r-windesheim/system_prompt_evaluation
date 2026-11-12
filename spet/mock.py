"""A fake OpenAI-compatible endpoint backed by the planted-behaviour stub.

For developing and testing the tool without a real model:

    python -m spet mock --port 8001      # then SPET_BASE_URL=http://localhost:8001/v1 SPET_MODEL=stub

Answers come from spet/stub.py and only make sense for its trigger phrases.
Prompt splitting through this endpoint always falls back to the heuristic.
"""

from __future__ import annotations

import asyncio
import random

from fastapi import FastAPI
from pydantic import BaseModel

from .stub import respond


class Msg(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    model: str = "stub"
    messages: list[Msg]
    temperature: float = 0.7
    seed: int | None = None
    max_tokens: int | None = None


def create_mock(latency: float = 0.05) -> FastAPI:
    app = FastAPI(title="spet mock endpoint")

    @app.post("/v1/chat/completions")
    async def chat(body: ChatIn):
        system = next((m.content for m in body.messages if m.role == "system"), "")
        user = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
        await asyncio.sleep(latency * (0.5 + random.random()))
        text = respond(system, user, body.seed or 0)
        return {"id": "mock", "object": "chat.completion", "model": body.model,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}]}

    @app.get("/v1/models")
    def models():
        return {"data": [{"id": "stub", "object": "model"}]}

    return app
