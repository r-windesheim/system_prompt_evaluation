"""Run bundle: the single JSON contract between the engine and the viewer.

A bundle holds everything needed to render a run statically: the full section
texts, every raw response for every configuration, detector spans, and the
per-(detector, section) effects with uncertainty.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(_Strict):
    id: str
    title: str
    created_at: str
    model: str
    provider: str
    temperature: float
    n_per_query: int = Field(ge=1)
    seed: int
    queries: list[str]
    fixture: bool = False
    notes: str = ""


class Section(_Strict):
    id: int
    label: str
    text: str


class Config(_Strict):
    id: str
    removed: int | None = None


class Span(_Strict):
    start: int = Field(ge=0)
    end: int
    detector: str


class Response(_Strict):
    config: str
    query_idx: int = Field(ge=0)
    sample_idx: int = Field(ge=0)
    text: str
    spans: list[Span] = []


class Detector(_Strict):
    id: str
    label: str
    group: str
    description: str = ""
    unit: Literal["per 100 words"] = "per 100 words"
    precision: float | None = None
    precision_n: int | None = None


class Effect(_Strict):
    detector: str
    section: int
    full_mean: float
    ablated_mean: float
    delta: float  # full_mean - ablated_mean: >0 means the section increases the quirk
    ci: tuple[float, float]
    p: float = Field(ge=0, le=1)
    q: float = Field(ge=0, le=1)
    significant: bool
    n_pairs: int


class RunBundle(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    meta: Meta
    sections: list[Section]
    configs: list[Config]
    responses: list[Response]
    detectors: list[Detector]
    effects: list[Effect]
    shapley: dict[str, dict[str, float]] | None = None  # detector -> section id -> value

    @model_validator(mode="after")
    def _check_refs(self) -> "RunBundle":
        section_ids = {s.id for s in self.sections}
        config_ids = {c.id for c in self.configs}
        detector_ids = {d.id for d in self.detectors}
        if "full" not in config_ids:
            raise ValueError("configs must include 'full'")
        for c in self.configs:
            if c.removed is not None and c.removed not in section_ids:
                raise ValueError(f"config {c.id} removes unknown section {c.removed}")
        for r in self.responses:
            if r.config not in config_ids:
                raise ValueError(f"response references unknown config {r.config}")
            if r.query_idx >= len(self.meta.queries):
                raise ValueError(f"response query_idx {r.query_idx} out of range")
            for sp in r.spans:
                if sp.detector not in detector_ids:
                    raise ValueError(f"span references unknown detector {sp.detector}")
                if not (0 <= sp.start < sp.end <= len(r.text)):
                    raise ValueError(f"span {sp.start}:{sp.end} out of bounds")
        for e in self.effects:
            if e.detector not in detector_ids or e.section not in section_ids:
                raise ValueError(f"effect references unknown detector/section {e.detector}/{e.section}")
        return self


def load(path: str | Path) -> RunBundle:
    return RunBundle.model_validate_json(Path(path).read_text())


def dump(bundle: RunBundle, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(bundle.model_dump_json(indent=1) + "\n")


def json_schema() -> str:
    return json.dumps(RunBundle.model_json_schema(), indent=2) + "\n"
