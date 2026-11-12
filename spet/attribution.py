"""Section attribution with honest uncertainty.

For each (detector d, section k) we compare the ``full`` configuration with
``without_k`` cell by cell. Both saw the same (query, sample, seed) cell, so
the comparison is paired:

    diff_c = rate_d(full, c) - rate_d(without_k, c)
    delta  = mean_c diff_c          (>0: section k increases quirk d)

- 95% CI: percentile bootstrap over cells.
- p-value: two-sided sign-flip permutation test on the paired diffs.
- q-value: Benjamini–Hochberg across *all* (d, k) pairs tested in the run.
- significant: q < alpha. No spike-ratio or min-impact thresholds.

Every section is reported, not only the arg-max (audit M3–M5).

Caveat: cells within the same query are not independent. With few queries the
CI is optimistic about generalising to *other* queries. It describes these
queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from math import factorial
from typing import Callable, Mapping, Sequence

import numpy as np

Cell = tuple[int, int]  # (query_idx, sample_idx)
Rates = Mapping[str, float]


@dataclass(frozen=True)
class EffectResult:
    detector: str
    section: int
    full_mean: float
    ablated_mean: float
    delta: float
    ci: tuple[float, float]
    p: float
    q: float
    significant: bool
    n_pairs: int


def bootstrap_ci(diffs: np.ndarray, rng: np.random.Generator, n_boot: int = 4000,
                 level: float = 0.95) -> tuple[float, float]:
    if len(diffs) == 0:
        return (0.0, 0.0)
    if np.all(diffs == diffs[0]):
        return (float(diffs[0]), float(diffs[0]))
    idx = rng.integers(0, len(diffs), size=(n_boot, len(diffs)))
    means = diffs[idx].mean(axis=1)
    a = (1 - level) / 2
    return (float(np.quantile(means, a)), float(np.quantile(means, 1 - a)))


def sign_flip_p(diffs: np.ndarray, rng: np.random.Generator, n_perm: int = 10000) -> float:
    """Two-sided paired permutation p-value. Exact for n <= 16."""
    n = len(diffs)
    if n == 0 or np.all(diffs == 0):
        return 1.0
    obs = abs(diffs.mean())
    if n <= 16:
        signs = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1) * 2 - 1
        stats = np.abs((signs * diffs).mean(axis=1))
        return float(np.mean(stats >= obs - 1e-12))
    signs = rng.choice([-1.0, 1.0], size=(n_perm, n))
    stats = np.abs((signs * diffs).mean(axis=1))
    return float((np.sum(stats >= obs - 1e-12) + 1) / (n_perm + 1))


def benjamini_hochberg(p: Sequence[float]) -> list[float]:
    p_arr = np.asarray(p, dtype=float)
    m = len(p_arr)
    if m == 0:
        return []
    order = np.argsort(p_arr)
    ranked = p_arr[order] * m / np.arange(1, m + 1)
    q_sorted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.clip(q_sorted, 0, 1)
    return q.tolist()


def section_effects(
    cell_rates: Mapping[str, Mapping[Cell, Rates]],
    sections: Sequence[int],
    detectors: Sequence[str],
    *,
    alpha: float = 0.05,
    seed: int = 0,
) -> list[EffectResult]:
    """``cell_rates[config][cell][detector]``; configs are ``full`` and ``without_k``."""
    rng = np.random.default_rng(seed)
    full = cell_rates["full"]
    raw: list[dict] = []
    for k in sections:
        abl = cell_rates.get(f"without_{k}")
        if not abl:
            continue
        cells = sorted(set(full) & set(abl))
        for d in detectors:
            f = np.array([full[c].get(d, 0.0) for c in cells])
            a = np.array([abl[c].get(d, 0.0) for c in cells])
            diffs = f - a
            raw.append(dict(detector=d, section=k, full_mean=float(f.mean()) if len(f) else 0.0,
                            ablated_mean=float(a.mean()) if len(a) else 0.0,
                            delta=float(diffs.mean()) if len(diffs) else 0.0,
                            ci=bootstrap_ci(diffs, rng), p=sign_flip_p(diffs, rng), n_pairs=len(cells)))
    qs = benjamini_hochberg([r["p"] for r in raw])
    return [EffectResult(**r, q=q, significant=q < alpha) for r, q in zip(raw, qs)]


def shapley_values(n_players: int, value: Callable[[frozenset[int]], float], *,
                   n_perm: int | None = None, rng: np.random.Generator | None = None) -> list[float]:
    """Shapley values of a set function. Exact for small n, else Monte Carlo over permutations.

    ``value`` is called on subsets of *kept* sections. Each call needs model responses
    for that subset, so the runner should memoise it.
    """
    if n_perm is None and n_players <= 7:
        perms = list(permutations(range(n_players)))
    else:
        rng = rng or np.random.default_rng(0)
        perms = [tuple(rng.permutation(n_players)) for _ in range(n_perm or 200)]
    phi = np.zeros(n_players)
    for perm in perms:
        kept: set[int] = set()
        prev = value(frozenset(kept))
        for p in perm:
            kept.add(p)
            cur = value(frozenset(kept))
            phi[p] += cur - prev
            prev = cur
    phi /= len(perms)
    assert n_perm is not None or len(perms) == factorial(n_players)
    return phi.tolist()
