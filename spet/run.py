"""Execute a run spec against a provider and produce a RunBundle."""

from __future__ import annotations

import asyncio
import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import attribution, detectors, schedule
from .bundle import Analysis, Config, Detector, Effect, Meta, Response, RunBundle, Section, Span
from .providers import Provider

# Precision per model, measured in scripts/precision_report.py (see docs/detector-precision.md).
# Format: {model: {detector: {"precision": p, "n": n}}}. A flat legacy file = gpt-4o-mini.
try:
    _raw = json.loads((Path(__file__).parent / "precision.json").read_text())
    _PRECISION = _raw if all(isinstance(v, dict) and "precision" not in v for v in _raw.values()) else {"openai/gpt-4o-mini": _raw}
except FileNotFoundError:
    _PRECISION = {}


def precision_for(model: str) -> tuple[str | None, dict[str, dict]]:
    """Precision measured on this model's answers, if any. Never borrowed from another model."""
    for key, table in _PRECISION.items():
        if key == model or key.split("/")[-1] == model.split("/")[-1]:
            return key, table
    return None, {}


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
    settings: dict = field(default_factory=dict)


async def execute(spec: RunSpec, provider: Provider, *, progress=None, on_job=None) -> RunBundle:
    jobs = schedule.build(spec.sections, spec.queries, spec.n_per_query, spec.seed)
    done = 0

    async def one(job: schedule.Job) -> str:
        nonlocal done
        text = await provider.complete(job.system, job.user, temperature=spec.temperature, seed=job.seed)
        done += 1
        if progress:
            progress(done, len(jobs))
        if on_job:
            on_job(job, text)
        return text

    texts = await asyncio.gather(*(one(j) for j in jobs))
    settings = {**getattr(provider, "settings", {}), **spec.settings}
    spec.settings = settings
    return assemble(spec, provider.name, provider.model, jobs, list(texts),
                    finish=[getattr(t, "finish_reason", None) for t in texts])


_WORD_LIMIT = re.compile(r"(?:under|fewer than|less than|at most|no more than|max(?:imum)?(?: of)?|within)\s+(\d{2,5})\s+words", re.I)
_IDENTITY = re.compile(r"^\s*(?:you are|you're|act as|your role)\b", re.I)


def assemble(spec: RunSpec, provider_name: str, model: str, jobs: list[schedule.Job],
             texts: list[str], finish: list[str | None] | None = None) -> RunBundle:
    finish = finish or [None] * len(texts)
    habit_ids = [d.id for d in detectors.DETECTORS]
    metric_ids = [m.id for m in detectors.METRICS]
    responses: list[Response] = []
    cells: dict[str, dict[tuple[int, int], dict[str, float]]] = {}
    span_cache: dict[tuple[str, int, int], list] = {}
    dropped = 0
    for job, text, fr in zip(jobs, texts, finish):
        text = str(text)
        sp = detectors.spans(text)
        responses.append(Response(config=job.config, query_idx=job.query_idx, sample_idx=job.sample_idx,
                                  text=text, spans=[Span(start=s, end=e, detector=d) for s, e, d in sp],
                                  finish_reason=fr))
        if fr == "length" or not text.strip():  # truncated or empty: not a clean zero (review problem 18)
            dropped += 1
            continue
        counts = {d: 0.0 for d in habit_ids}
        for _, _, d in sp:
            counts[d] += 1
        cells.setdefault(job.config, {})[(job.query_idx, job.sample_idx)] = {**counts, **detectors.metrics(text, sp)}
        span_cache[(job.config, job.query_idx, job.sample_idx)] = (text, sp)

    k_range = range(len(spec.sections))
    # two separate families: habits are the findings; shape metrics are context and shouldn't dilute them
    habit_fx = attribution.section_effects(cells, k_range, habit_ids, alpha=spec.alpha, seed=spec.seed)
    metric_fx = attribution.section_effects(cells, k_range, metric_ids, alpha=spec.alpha, seed=spec.seed + 1)

    length_shift = {e.section for e in metric_fx if e.detector == "words" and e.significant}
    identity = {i for i, t in enumerate(spec.sections) if _IDENTITY.match(t)}
    binary = {m.id for m in detectors.METRICS if m.binary}

    def flags(e) -> list[str]:
        out = []
        if not e.tested or max(e.full_mean, e.ablated_mean) < 0.1 or (
                e.detector in binary and min(e.full_mean, e.ablated_mean) >= 0.9):
            out.append("not_testable")
        if e.detector in habit_ids and e.detector not in ("list_item", "heading"):
            inside = total = 0
            for (cfg, q, s), (text, sp) in span_cache.items():
                if cfg in ("full", f"without_{e.section}"):
                    a, b = detectors.list_line_share(text, sp, e.detector)
                    inside, total = inside + a, total + b
            if total >= 5 and inside / total > 0.7:
                out.append("in_lists")
        if e.section in length_shift and e.detector != "words":
            out.append("length_shift")
        if e.section in identity:
            out.append("context_shift")
        return out

    # per-section notes: a word limit is only tested if answers WITHOUT it go over the limit
    notes: dict[int, list[str]] = {i: [] for i in k_range}
    for i, t in enumerate(spec.sections):
        m = _WORD_LIMIT.search(t)
        if not m:
            continue
        limit = int(m.group(1))
        without = [detectors.word_count(tx) for (cfg, _, _), (tx, _) in span_cache.items() if cfg == f"without_{i}"]
        if without and max(without) <= limit:
            notes[i].append(f"never tested: even without this part, no answer went over {limit} words "
                            f"(longest: {max(without)}), so the limit had nothing to hold back")
        if i in identity:
            notes[i].append("context shift: this part sets who the assistant is, so removing it changes what answers are about, not just their style")

    warnings = []
    qwords = [len(q.split()) for q in spec.queries]
    if qwords and statistics.median(qwords) < 8:
        warnings.append("The questions are very short and vague, so answers are mostly clarification requests. "
                        "Instructions about length, formatting or claims may never come into play.")
    if dropped:
        warnings.append(f"{dropped} answers were cut off or empty and were left out of the comparison.")
    if len(spec.queries) < 10:
        warnings.append(f"Effects describe these {len(spec.queries)} questions; with few questions they may not generalise.")

    prec_model, prec = precision_for(model)
    labels = spec.section_labels or [f"Section {i + 1}" for i in k_range]
    settings = {**spec.settings, "detector_version": detectors.detector_version()}
    return RunBundle(
        meta=Meta(id=spec.id, title=spec.title, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  model=model, provider=provider_name, temperature=spec.temperature,
                  n_per_query=spec.n_per_query, seed=spec.seed, queries=spec.queries,
                  fixture=spec.fixture, notes=spec.notes, settings=settings),
        sections=[Section(id=i, label=labels[i], text=t, notes=notes[i]) for i, t in enumerate(spec.sections)],
        configs=[Config(id=c, removed=r) for c, r in schedule.config_ids(len(spec.sections))],
        responses=responses,
        detectors=[Detector(id=d.id, label=d.label, group=d.group, description=d.description,
                            precision=prec.get(d.id, {}).get("precision"), precision_n=prec.get(d.id, {}).get("n"),
                            precision_model=prec_model if d.id in prec else None)
                   for d in detectors.DETECTORS]
                  + [Detector(id=m.id, label=m.label, group=m.group, description=m.description, kind="metric", unit=m.unit)
                     for m in detectors.METRICS],
        effects=[Effect(**{**e.__dict__, "per_query": list(e.per_query)}, flags=flags(e)) for e in habit_fx + metric_fx],
        analysis=Analysis(n_tests=sum(e.tested for e in habit_fx), alpha=spec.alpha,
                          mde_alpha=attribution.MDE_ALPHA, warnings=warnings),
    )


def rescore(b: RunBundle) -> RunBundle:
    """Recompute spans, metrics, effects and flags from a bundle's stored answers (no model calls)."""
    by_cfg = {c.id: c.removed for c in b.configs}
    jobs = [schedule.Job(r.config, by_cfg[r.config], r.query_idx, r.sample_idx, "", "", 0) for r in b.responses]
    spec = RunSpec(id=b.meta.id, title=b.meta.title, sections=[s.text for s in b.sections],
                   section_labels=[s.label for s in b.sections], queries=b.meta.queries,
                   n_per_query=b.meta.n_per_query, temperature=b.meta.temperature, seed=b.meta.seed,
                   notes=b.meta.notes, fixture=b.meta.fixture, settings=dict(b.meta.settings))
    out = assemble(spec, b.meta.provider, b.meta.model, jobs, [r.text for r in b.responses],
                   finish=[r.finish_reason for r in b.responses])
    out.meta.created_at = b.meta.created_at
    return out
