"""Attention screen: which prompt parts does the model look at while it answers each question?

The GPU side (``deploy/modal_attention.py``) renders every question the way vLLM sends it, samples a few
answers with the full prompt and records, per generation, the attention mass that the reasoning tokens and the
answer tokens put on each part, layer by layer. This module turns those records into a screen file and reads it
back. It needs no GPU and no torch, so it is tested with synthetic records.

Measures (the pilot's, scripts/attention_report.py), on the middle and late full-attention layers:

- density: attention mass on a part / the part's token count (mass per prompt token);
- rel: density / the mean density of all parts in that generation (1.0 = an average part);
- lift: a part's rel on one question (mean over its samples) / the part's median rel over all questions.
  Raw attention is dominated by position, so only lift is used: it removes what a part draws on every question.

The screen only reorders what discovery shows its proposer (``spet discover --screen``). It never enters a test.
"""

from __future__ import annotations

import hashlib
import json
from itertools import combinations
from pathlib import Path

import numpy as np

FORMAT = "spet-attention-screen/1"
BLOCKS = ("reasoning", "answer")


def fingerprint(sections: list[str], queries: list[str]) -> str:
    """Hash of the part texts and question texts, in order. A screen is only valid for the run it was made for."""
    blob = json.dumps({"sections": [s.strip() for s in sections], "queries": list(queries)}, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def bands(layer_types: list[str]) -> dict[str, list[int]]:
    """Full-attention layers split in thirds. Sliding-window layers cannot reach the prompt from late tokens."""
    full = [i for i, t in enumerate(layer_types) if t == "full_attention"]
    q = len(full) // 3
    return {"early": full[:q], "middle": full[q:2 * q], "late": full[2 * q:], "mid+late": full[q:]}


def _rel(block: dict, layers: list[int], all_layers: list[int], counts: list[int]) -> np.ndarray | None:
    """Per-part rel for one generation's block; None if the block is missing."""
    if not block or not block.get("n_tokens"):
        return None
    pos = [all_layers.index(li) for li in layers]
    m = np.asarray(block["mass"], dtype=np.float64)[pos]  # (layers, columns), already a mean over the block's tokens
    raw = m.mean(axis=0)[:len(counts)]
    dens = raw / np.asarray(counts, dtype=np.float64)
    return dens / dens.mean() if dens.mean() > 0 else None


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    c = np.corrcoef(ra, rb)[0, 1]
    return float(c) if np.isfinite(c) else 0.0


def build(raw: dict, targets: list[list[int]] | None = None, band: str = "mid+late") -> dict:
    """Screen file from the GPU records. ``raw`` is what deploy/modal_attention.py's screen returns (all chunks merged).

    Each record in raw["generations"]: query_idx, sample_idx, finished, part_token_counts, and for each block in
    BLOCKS either None or {"n_tokens", "mass": [layer][column]} where layers are raw["layers_recorded"] and the
    columns are the parts, then user, reasoning, answer, other, sink.
    """
    n_parts = len(raw["part_labels"])
    n_q = raw["n_questions"]
    rec_layers = raw["layers_recorded"]
    layers = bands(raw["layer_types"])[band]
    rel: dict[str, dict[int, list[np.ndarray]]] = {b: {} for b in BLOCKS}
    for g in raw["generations"]:
        for b in BLOCKS:
            r = _rel(g.get(b), layers, rec_layers, g["part_token_counts"])
            if r is not None:
                rel[b].setdefault(g["query_idx"], []).append(r)

    out_pairs = []
    agreement: dict[str, dict[int, float | None]] = {b: {} for b in BLOCKS}
    lift: dict[str, dict[int, np.ndarray]] = {b: {} for b in BLOCKS}
    sample_lift: dict[str, dict[int, list[np.ndarray]]] = {b: {} for b in BLOCKS}
    for b in BLOCKS:
        means = {q: np.mean(v, axis=0) for q, v in rel[b].items()}
        if not means:
            continue
        med = np.median(np.array(list(means.values())), axis=0)  # per part, over every question with a value
        med = np.where(med > 0, med, np.nan)
        for q, v in rel[b].items():
            lift[b][q] = means[q] / med
            sample_lift[b][q] = [x / med for x in v]
            agreement[b][q] = (float(np.mean([_spearman(x, y) for x, y in combinations(v, 2)]))
                               if len(v) > 1 else None)
    for k in range(n_parts):
        for q in range(n_q):
            row: dict = {"section": k, "query_idx": q, "target": bool(targets and k in targets[q])}
            for b in BLOCKS:
                if q not in lift[b] or not np.isfinite(lift[b][q][k]):
                    row[b] = None
                    continue
                xs = [float(x[k]) for x in sample_lift[b][q]]
                mean = float(lift[b][q][k])
                row[b] = {
                    "lift": round(mean, 4),
                    "samples": [round(x, 4) for x in xs],
                    "sd": round(float(np.std(xs, ddof=1)), 4) if len(xs) > 1 else None,
                    # share of samples on the same side of 1 as the mean: 1.0 = every sample agrees
                    "same_side": round(float(np.mean([(x > 1) == (mean > 1) for x in xs])), 4),
                }
            out_pairs.append(row)
    n_gen = {}
    for g in raw["generations"]:
        n_gen[g["query_idx"]] = n_gen.get(g["query_idx"], 0) + 1
    questions = [{
        "query_idx": q, "targets": targets[q] if targets else None, "n_generations": n_gen.get(q, 0),
        **{f"n_{b}": len(rel[b].get(q, [])) for b in BLOCKS},
        # mean pairwise Spearman correlation of the part rel vectors between samples (None with < 2 samples)
        **{f"agreement_{b}": None if agreement[b].get(q) is None else round(agreement[b][q], 4) for b in BLOCKS},
    } for q in range(n_q)]
    return {
        "format": FORMAT, "fingerprint": raw["fingerprint"], "spec_id": raw.get("spec_id"),
        "model": raw.get("model"), "model_revision": raw.get("model_revision"),
        "part_labels": raw["part_labels"], "n_questions": n_q, "n_samples": raw.get("n_samples"),
        "band": band, "layers": layers, "layer_types": raw["layer_types"], "settings": raw.get("settings", {}),
        "layout": raw.get("layout"), "timings": raw.get("timings"),
        "questions": questions, "pairs": out_pairs, "generations": raw["generations"],
    }


def load(path: str | Path) -> tuple[dict, str]:
    """(screen, sha256 of the file)."""
    data = Path(path).read_bytes()
    s = json.loads(data)
    if s.get("format") != FORMAT:
        raise ValueError(f"{path}: not an attention screen (format {s.get('format')!r}, expected {FORMAT!r})")
    return s, hashlib.sha256(data).hexdigest()


def lifts(screen: dict, block: str = "reasoning") -> dict[tuple[int, int], float]:
    """(section, query_idx) -> lift on ``block`` tokens, for every pair the screen has a value for."""
    if block not in BLOCKS:
        raise ValueError(f"block must be one of {BLOCKS}")
    return {(p["section"], p["query_idx"]): p[block]["lift"] for p in screen["pairs"] if p.get(block)}


def check(screen: dict, sections: list[str], queries: list[str]) -> None:
    """Refuse a screen made for other parts or questions."""
    want = fingerprint(sections, queries)
    if screen.get("fingerprint") != want:
        raise ValueError("the screen was made for different parts or questions than this run "
                         f"(screen {screen.get('fingerprint')}, run {want})")


GPT_OSS_LAYER_TYPES = ["sliding_attention", "full_attention"] * 12  # openai/gpt-oss-20b


def stub_raw(sections: list[str], queries: list[str], n_samples: int = 4, seed: int = 0,
             boost: dict[tuple[int, int], float] | None = None) -> dict:
    """Synthetic GPU records for tests and dry runs: no model. A part draws more attention per token on a question
    that shares words with it (and by ``boost[(part, question)]``), plus seeded noise per sample."""
    rng = np.random.default_rng(seed)
    words = [set(w for w in s.lower().split() if len(w) > 3) for s in sections]
    counts = [max(1, len(s.split())) for s in sections]
    full = [i for i, t in enumerate(GPT_OSS_LAYER_TYPES) if t == "full_attention"]
    gens = []
    for q, text in enumerate(queries):
        qw = set(w for w in text.lower().split() if len(w) > 3)
        base = np.array([1.0 + 2.0 * len(qw & w) + (boost or {}).get((k, q), 0.0) for k, w in enumerate(words)])
        for s in range(n_samples):
            rec = {"query_idx": q, "sample_idx": s, "finished": True, "part_token_counts": counts,
                   "channels": ["analysis", "final"]}
            for b in BLOCKS:
                dens = base * np.exp(rng.normal(0, 0.1, len(base)))
                mass = dens * np.array(counts) * 1e-4
                row = list(mass) + [0.05, 0.1, 0.1, 0.2]
                row.append(1.0 - sum(row))  # sink
                rec[b] = {"n_tokens": 20, "mass": [[round(float(v), 7) for v in row] for _ in full]}
            gens.append(rec)
    return {"fingerprint": fingerprint(sections, queries), "model": "stub-attention", "n_questions": len(queries),
            "n_samples": n_samples, "part_labels": [f"Part {k + 1}" for k in range(len(sections))],
            "layer_types": GPT_OSS_LAYER_TYPES, "layers_recorded": full, "generations": gens}
