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

Caveat: cells within the same query are not independent. The cell-level test is
valid for "removing k changes answers to *these* queries" (under that null every
cell is exchangeable on its own), but one question can carry it. With few queries
the CI is optimistic about generalising to *other* queries. It describes these
queries. ``paired_stats(..., cluster=True)`` (used by discovery) instead flips
signs per question, bootstraps questions and sizes the MDE by question, so a
result must hold across questions, not within one.
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
    tested: bool = True                       # False when both arms are all-zero: excluded from the correction
    ci_query: tuple[float, float] | None = None  # bootstrap over questions (clusters), not cells
    per_query: tuple[float, ...] = ()         # mean paired difference for each question in per_query_idx
    mde: float | None = None                  # smallest change detectable 80% of the time at alpha=MDE_ALPHA
    per_query_idx: tuple[int, ...] = ()       # the question index of each per_query entry (questions with no pair are absent)


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


N_PERM = 10000  # Monte Carlo draws above 16 units; the smallest p it can return is 1 / (N_PERM + 1)


def sign_flip_p(diffs: np.ndarray, rng: np.random.Generator, n_perm: int = N_PERM) -> float:
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


MDE_ALPHA = 0.005  # roughly the per-test threshold BH needs with ~100 tests and a handful of real effects
_Z = {0.005: 2.807, 0.05: 1.960}
_Z80 = 0.8416


def cluster_bootstrap_ci(diffs: np.ndarray, groups: np.ndarray, rng: np.random.Generator,
                         n_boot: int = 4000, level: float = 0.95) -> tuple[float, float]:
    """Percentile bootstrap that resamples whole groups (questions), keeping their cells together."""
    ids = np.unique(groups)
    if len(ids) < 2:
        return bootstrap_ci(diffs, rng, n_boot, level)
    by = [diffs[groups == g] for g in ids]
    sums = np.array([b.sum() for b in by])
    lens = np.array([len(b) for b in by])
    pick = rng.integers(0, len(ids), size=(n_boot, len(ids)))
    means = sums[pick].sum(axis=1) / lens[pick].sum(axis=1)
    a = (1 - level) / 2
    return (float(np.quantile(means, a)), float(np.quantile(means, 1 - a)))


def cluster_sign_flip_p(diffs: np.ndarray, groups: np.ndarray, rng: np.random.Generator,
                        n_perm: int = N_PERM) -> float:
    """Two-sided sign-flip test that flips whole questions: the cells of a question keep their signs together.

    Statistic: |sum of signed per-question sums|, i.e. the pooled mean difference. Valid when cells within a
    question are correlated. With G questions the smallest possible p is 2 / 2**G. Exact for G <= 16.
    """
    if len(diffs) == 0 or np.all(diffs == 0):
        return 1.0
    sums = np.array([diffs[groups == g].sum() for g in np.unique(groups)])
    return sign_flip_p(sums, rng, n_perm)


def cluster_p_floor(n_questions: int) -> float:
    """Smallest p the cluster sign-flip test can return with this many questions, when the test is exact (G <= 16).

    Above 16 questions the test is Monte Carlo and cannot go below 1 / (N_PERM + 1); this function does not model
    that (the ``too_few_questions`` flag uses it as is, which is harmless while alpha / m > 1 / (N_PERM + 1)).
    """
    return 1.0 if n_questions < 1 else min(1.0, 2.0 / 2 ** n_questions)


def min_detectable(diffs: np.ndarray, alpha: float = MDE_ALPHA) -> float | None:
    if len(diffs) < 2:
        return None
    sd = float(np.std(diffs, ddof=1))
    return (_Z[alpha] + _Z80) * sd / np.sqrt(len(diffs)) if sd > 0 else 0.0


def cluster_min_detectable(diffs: np.ndarray, groups: np.ndarray, alpha: float = MDE_ALPHA) -> float | None:
    """MDE from the spread of per-question mean differences. None if the cluster test can never reach alpha."""
    ids = np.unique(groups)
    if len(ids) < 2 or cluster_p_floor(len(ids)) > alpha:
        return None
    return min_detectable(np.array([diffs[groups == g].mean() for g in ids]), alpha)


def paired_stats(f: np.ndarray, a: np.ndarray, groups: np.ndarray, rng: np.random.Generator,
                 *, cluster: bool = False) -> dict:
    """Everything but q/significance for one paired comparison (with-part ``f`` vs without ``a``, per cell).

    Shared by the habit effects and the discovery statements. ``cluster=True`` makes p, ci and mde treat the
    question as the unit (sign flips and bootstrap over whole questions), so cells from the same question
    are not counted as independent evidence.
    """
    diffs = f - a
    n = len(diffs)
    tested = bool(n) and not (np.all(f == 0) and np.all(a == 0))
    ids = np.unique(groups) if n else np.array([], dtype=int)
    per_q = tuple(float(diffs[groups == g].mean()) for g in ids)
    if cluster:
        ci_query = cluster_bootstrap_ci(diffs, groups, rng) if tested else None
        p = cluster_sign_flip_p(diffs, groups, rng) if tested else 1.0
        ci = ci_query if ci_query is not None else bootstrap_ci(diffs, rng)
        mde = cluster_min_detectable(diffs, groups) if tested else None
    else:  # same RNG order as before, so habit results are unchanged
        ci = bootstrap_ci(diffs, rng)
        p = sign_flip_p(diffs, rng) if tested else 1.0
        ci_query = cluster_bootstrap_ci(diffs, groups, rng) if tested else None
        mde = min_detectable(diffs) if tested else None
    return dict(full_mean=float(f.mean()) if n else 0.0, ablated_mean=float(a.mean()) if n else 0.0,
                delta=float(diffs.mean()) if n else 0.0,
                ci=ci, p=p, n_pairs=n, tested=tested, ci_query=ci_query,
                per_query=per_q, per_query_idx=tuple(int(g) for g in ids), mde=mde)


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
            raw.append(dict(detector=d, section=k, **paired_stats(f, a, np.array([c[0] for c in cells]), rng)))
    # Benjamini–Hochberg over the tests that could fire (all-zero tests are reported, not counted)
    idx = [i for i, r in enumerate(raw) if r["tested"]]
    qs = benjamini_hochberg([raw[i]["p"] for i in idx])
    qmap = dict(zip(idx, qs))
    return [EffectResult(**r, q=qmap.get(i, 1.0), significant=qmap.get(i, 1.0) < alpha) for i, r in enumerate(raw)]


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
