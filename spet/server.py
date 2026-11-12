"""Local analysis server: the API behind the web app's "New analysis" flow.

    SPET_BASE_URL=https://<you>--vllm.modal.run/v1 SPET_MODEL=Qwen/Qwen2.5-7B-Instruct \\
        python -m spet serve --runs-dir web/public/runs

The API key, if the endpoint needs one, is read from SPET_API_KEY on the server
and never sent to the browser.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import bundle as B
from . import schedule
from .providers import OpenAICompatible
from .run import RunSpec, execute
from .split import split_heuristic, split_with_model

DEFAULT_QUERIES = [
    "Rewrite this so it sounds professional: 'hey, the report is late again, need it by fri'",
    "My Python script fails with ModuleNotFoundError: No module named 'requests'. What should I do?",
    "Explain the difference between a process and a thread.",
    "I have a job offer with a higher salary but a longer commute. How should I decide?",
    "Summarise the main causes of inflation in two or three sentences.",
]


class EndpointIn(BaseModel):
    base_url: str | None = None
    model: str | None = None


class SplitIn(BaseModel):
    prompt: str
    use_model: bool = True
    endpoint: EndpointIn | None = None


class SectionIn(BaseModel):
    label: str
    text: str


class RunIn(BaseModel):
    title: str = "Untitled prompt"
    sections: list[SectionIn] = Field(min_length=1, max_length=40)
    queries: list[str] = Field(default_factory=lambda: list(DEFAULT_QUERIES), min_length=1, max_length=20)
    n_per_query: int = Field(8, ge=2, le=50)
    temperature: float = Field(0.7, ge=0, le=2)
    seed: int = 0
    endpoint: EndpointIn | None = None


def _extra() -> dict:
    """Extra request fields from the environment, e.g. SPET_REASONING_EFFORT=low for gpt-oss."""
    eff = os.environ.get("SPET_REASONING_EFFORT")
    return {"reasoning_effort": eff} if eff else {}


def create_app(runs_dir: Path) -> FastAPI:
    app = FastAPI(title="spet")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    runs_dir.mkdir(parents=True, exist_ok=True)
    jobs: dict[str, dict] = {}

    def endpoint(e: EndpointIn | None) -> tuple[str, str]:
        base = (e.base_url if e and e.base_url else None) or os.environ.get("SPET_BASE_URL")
        model = (e.model if e and e.model else None) or os.environ.get("SPET_MODEL")
        if not base or not model:
            raise HTTPException(400, "No model endpoint configured. Set SPET_BASE_URL and SPET_MODEL, or enter them in the form.")
        return base, model

    @app.get("/api/health")
    def health():
        return {"ok": True, "base_url": os.environ.get("SPET_BASE_URL"), "model": os.environ.get("SPET_MODEL"),
                "default_queries": DEFAULT_QUERIES}

    @app.post("/api/split")
    async def split(body: SplitIn):
        if not body.prompt.strip():
            raise HTTPException(400, "The prompt is empty.")
        if body.use_model:
            try:
                base, model = endpoint(body.endpoint)
            except HTTPException:
                base = None
            if base:
                prov = OpenAICompatible(base, model, cache_dir=None, max_tokens=4000)
                try:
                    secs, method = await split_with_model(body.prompt, prov)
                finally:
                    await prov.aclose()
                return {"method": method, "sections": [s.__dict__ for s in secs]}
        return {"method": "heuristic", "sections": [s.__dict__ for s in split_heuristic(body.prompt)]}

    @app.post("/api/runs")
    async def start(body: RunIn):
        base, model = endpoint(body.endpoint)
        slug = re.sub(r"[^a-z0-9]+", "-", body.title.lower()).strip("-")[:40] or "run"
        rid = f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        n_cfg = len(body.sections) + 1
        total = n_cfg * len(body.queries) * body.n_per_query
        job = {"id": rid, "state": "running", "done": 0, "total": total, "error": None, "title": body.title,
               "configs": [c for c, _ in schedule.config_ids(len(body.sections))],
               "per_config": {c: 0 for c, _ in schedule.config_ids(len(body.sections))},
               "per_config_total": len(body.queries) * body.n_per_query, "started": time.time()}
        jobs[rid] = job
        spec = RunSpec(id=rid, title=body.title, sections=[s.text for s in body.sections],
                       section_labels=[s.label for s in body.sections], queries=body.queries,
                       n_per_query=body.n_per_query, temperature=body.temperature, seed=body.seed)

        async def work():
            prov = OpenAICompatible(base, model, extra=_extra(), max_tokens=int(os.environ.get("SPET_MAX_TOKENS", "4000")))
            try:
                def on_done(j: schedule.Job, _text: str):
                    job["done"] += 1
                    job["per_config"][j.config] += 1
                b = await execute(spec, prov, on_job=on_done)
                B.dump(b, runs_dir / f"{rid}.json")
                job["state"] = "done"
            except Exception as e:  # noqa: BLE001
                job["state"], job["error"] = "error", f"{type(e).__name__}: {e}"
            finally:
                await prov.aclose()

        job["task"] = asyncio.create_task(work())
        return {"id": rid, "total": total}

    @app.get("/api/runs/{rid}/status")
    def status(rid: str):
        j = jobs.get(rid)
        if not j:
            if (runs_dir / f"{rid}.json").exists():
                return {"id": rid, "state": "done"}
            raise HTTPException(404, "No such run.")
        return {k: v for k, v in j.items() if k != "task"}

    @app.get("/api/runs/{rid}")
    def get_run(rid: str):
        p = runs_dir / f"{rid}.json"
        if not re.fullmatch(r"[\w.-]+", rid) or not p.exists():
            raise HTTPException(404, "No such run.")
        return FileResponse(p, media_type="application/json")

    @app.get("/api/runs")
    def list_runs():
        out = []
        for p in sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                b = B.load(p)
            except Exception:  # noqa: BLE001
                continue
            out.append({"id": b.meta.id, "title": b.meta.title, "model": b.meta.model, "created_at": b.meta.created_at,
                        "fixture": b.meta.fixture, "n_sections": len(b.sections), "n_responses": len(b.responses),
                        "n_significant": sum(e.significant for e in b.effects)})
        running = [{k: v for k, v in j.items() if k in ("id", "title", "state", "done", "total")}
                   for j in jobs.values() if j["state"] == "running"]
        return {"runs": out, "running": running}

    return app
