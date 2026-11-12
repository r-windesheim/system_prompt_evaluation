"""Execute a run spec against a provider and produce a RunBundle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import attribution, detectors, schedule
from .bundle import Config, Detector, Effect, Meta, Response, RunBundle, Section, Span
from .providers import Provider


@dataclass
class RunSpec:
    id: str
    title: str
    sections: list[str]
    queries: list[str]
    section_labels: list[str] | None = None
    n_per_query: int = 8
    temperature: float = 0.7
    seed: int = 0
    alpha: float = 0.05
    notes: str = ""
    fixture: bool = False
    detector_precision: dict[str, tuple[float, int]] = field(default_factory=dict)


async def execute(spec: RunSpec, provider: Provider, *, progress=None) -> RunBundle:
    jobs = schedule.build(spec.sections, spec.queries, spec.n_per_query, spec.seed)
    done = 0

    async def one(job: schedule.Job) -> str:
        nonlocal done
        text = await provider.complete(job.system, job.user, temperature=spec.temperature, seed=job.seed)
        done += 1
        if progress:
            progress(done, len(jobs))
        return text

    texts = await asyncio.gather(*(one(j) for j in jobs))
    return assemble(spec, provider.name, provider.model, jobs, list(texts))


def assemble(spec: RunSpec, provider_name: str, model: str, jobs: list[schedule.Job],
             texts: list[str]) -> RunBundle:
    det_ids = [d.id for d in detectors.DETECTORS]
    responses: list[Response] = []
    cell_rates: dict[str, dict[tuple[int, int], dict[str, float]]] = {}
    for job, text in zip(jobs, texts):
        sp = detectors.spans(text)
        responses.append(Response(config=job.config, query_idx=job.query_idx, sample_idx=job.sample_idx,
                                  text=text, spans=[Span(start=s, end=e, detector=d) for s, e, d in sp]))
        cell_rates.setdefault(job.config, {})[(job.query_idx, job.sample_idx)] = detectors.counts(text)

    effects = attribution.section_effects(cell_rates, range(len(spec.sections)), det_ids,
                                          alpha=spec.alpha, seed=spec.seed)
    labels = spec.section_labels or [f"Section {i + 1}" for i in range(len(spec.sections))]
    return RunBundle(
        meta=Meta(id=spec.id, title=spec.title, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  model=model, provider=provider_name, temperature=spec.temperature,
                  n_per_query=spec.n_per_query, seed=spec.seed, queries=spec.queries,
                  fixture=spec.fixture, notes=spec.notes),
        sections=[Section(id=i, label=labels[i], text=t) for i, t in enumerate(spec.sections)],
        configs=[Config(id=c, removed=r) for c, r in schedule.config_ids(len(spec.sections))],
        responses=responses,
        detectors=[Detector(id=d.id, label=d.label, group=d.group, description=d.description,
                            precision=spec.detector_precision.get(d.id, (None, None))[0],
                            precision_n=spec.detector_precision.get(d.id, (None, None))[1])
                   for d in detectors.DETECTORS],
        effects=[Effect(**e.__dict__) for e in effects],
    )
