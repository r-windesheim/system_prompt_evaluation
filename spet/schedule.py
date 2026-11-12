"""Deterministic sampling schedule.

Every configuration (``full`` and each ``without_k``) gets the *same* grid of
(query_idx, sample_idx) cells, and each cell has one sampling seed shared by
all configurations. The shared seed makes runs reproducible. It does NOT make
paired answers near-twins: once the prompt differs, sampling diverges (on
gpt-oss, same-seed pairs are barely more alike than different-seed pairs;
methodology review, problem 4). Pairing by cell is still valid for the test.

The seed travels as a request parameter and part of the cache key. It is
never written into the prompt. The legacy tool appended ``[sample_i_t0.5]`` to
the user message, and the model answered the tag (audit finding M1).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    config: str
    removed: int | None
    query_idx: int
    sample_idx: int
    system: str
    user: str
    seed: int


def join_sections(sections: list[str]) -> str:
    return "\n\n".join(s.strip() for s in sections)


def cell_seed(run_seed: int, query_idx: int, sample_idx: int) -> int:
    h = hashlib.sha256(f"{run_seed}:{query_idx}:{sample_idx}".encode()).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def config_ids(n_sections: int, skip: set[int] = frozenset()) -> list[tuple[str, int | None]]:
    return [("full", None)] + [(f"without_{k}", k) for k in range(n_sections) if k not in skip]


def build(sections: list[str], queries: list[str], n_per_query: int, run_seed: int,
          skip: set[int] = frozenset()) -> list[Job]:
    if not sections:
        raise ValueError("need at least one section")
    jobs: list[Job] = []
    for cfg, removed in config_ids(len(sections), skip):
        kept = [s for i, s in enumerate(sections) if i != removed]
        system = join_sections(kept)
        for qi, q in enumerate(queries):
            for si in range(n_per_query):
                jobs.append(Job(cfg, removed, qi, si, system, q, cell_seed(run_seed, qi, si)))
    return jobs
