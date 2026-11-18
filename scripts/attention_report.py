"""Tables for the attention pilot (runs_out/attention-pilot.json, from deploy/modal_attention.py).

    python scripts/attention_report.py [runs_out/attention-pilot.json] [--block answer|reasoning]

Measures, all per generation first, then averaged over the samples of a question:
- raw: mean over the block's tokens of the head-averaged attention mass on a key bucket
  (16 parts, user, reasoning, answer, other, sink; rows sum to 1).
- density: raw / number of tokens in the part, i.e. mass per prompt token.
- rel: density / the mean density of the 16 parts on that generation (1.0 = an average part).
  This is what the tables rank by.
- lift: a part's rel on one question / its median rel over all questions in the file. It removes
  what a part draws on every question (position, length) and keeps what is question-specific.

Only full-attention layers are used (odd layers in gpt-oss-20b). Sliding-window layers see the
last 128 tokens and so can barely reach the system prompt; their mass is printed once as a check.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path):
    r = json.loads(path.read_text())
    full = [i for i, t in enumerate(r["layer_types"]) if t == "full_attention"]
    sliding = [i for i, t in enumerate(r["layer_types"]) if t != "full_attention"]
    q = len(full) // 3
    bands = {"early": full[:q], "middle": full[q:2 * q], "late": full[2 * q:], "mid+late": full[q:]}
    return r, full, sliding, bands


def per_item(it: dict, block: str, layers: list[int], n_parts: int):
    """(raw, density, rel) for one generation, averaged over tokens then layers; None if no block."""
    b = it.get(block)
    if not b:
        return None
    m = np.asarray(b["mass"], dtype=np.float64)[layers]  # (layers, tokens, cols)
    raw = m.mean(axis=1).mean(axis=0)  # (cols,)
    counts = np.asarray(it["bucket_token_counts"]["parts"], dtype=np.float64)
    dens = raw[:n_parts] / counts
    rel = dens / dens.mean()
    return raw, dens, rel


def by_question(r: dict, block: str, layers: list[int]):
    n = len(r["part_labels"])
    acc = defaultdict(list)
    for it in r["items"]:
        x = per_item(it, block, layers, n)
        if x is not None:
            acc[it["query_idx"]].append(x)
    out = {}
    for qi, xs in acc.items():
        out[qi] = {
            "raw": np.mean([x[0] for x in xs], axis=0),
            "dens": np.mean([x[1] for x in xs], axis=0),
            "rel": np.mean([x[2] for x in xs], axis=0),
            "rel_samples": [x[2] for x in xs],
        }
    return out


def rank_of(vec: np.ndarray, k: int) -> int:
    return int((vec > vec[k]).sum()) + 1


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def short(label: str, w: int = 22) -> str:
    return label if len(label) <= w else label[: w - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default=str(ROOT / "runs_out" / "attention-pilot.json"))
    ap.add_argument("--block", default="answer", choices=["answer", "reasoning"])
    ap.add_argument("--lift", type=float, default=1.5, help="Table 2 threshold on lift")
    args = ap.parse_args()

    r, full, sliding, bands = load(Path(args.path))
    labels = r["part_labels"]
    n = len(labels)
    cols = r["columns"]
    items = r["items"]
    qs = sorted({it["query_idx"] for it in items})
    target = {it["query_idx"]: it["target_part"] for it in items}
    question = {it["query_idx"]: it["question"] for it in items}
    counts = items[0]["bucket_token_counts"]["parts"]

    print(f"model {r['model']}@{r['model_revision'][:8]}  weights: {r['settings']['weights']}")
    print(f"{len(items)} generations over {len(qs)} questions; timings {r['timings']}")
    trunc = [(it["query_idx"], it["sample_idx"]) for it in items if not it["finished"] or not it["answer"]]
    print(f"truncated or without a final answer: {trunc or 'none'}")
    print(f"full-attention layers {full}; bands: " + ", ".join(f"{k}={v}" for k, v in bands.items()))
    print("part token counts: " + ", ".join(f"{i}:{c}" for i, c in enumerate(counts)))

    # check: what sliding-window layers put on the system prompt
    for blk in ("reasoning", "answer"):
        s_sys, f_sys = [], []
        for it in items:
            if it.get(blk):
                m = np.asarray(it[blk]["mass"])
                s_sys.append(m[sliding][:, :, :n].sum(-1).mean())
                f_sys.append(m[full][:, :, :n].sum(-1).mean())
        print(f"[{blk}] mass on all 16 parts: sliding layers {np.mean(s_sys):.4f}, full layers {np.mean(f_sys):.4f}")

    # ---- Table 1 -------------------------------------------------------------------------
    L = bands["mid+late"]
    Q = by_question(r, args.block, L)
    print(f"\nTABLE 1  [{args.block} tokens, layers {L}]  top 3 parts by attention per prompt token")
    print("rel = density / mean part density (1.0 = average part).  * = the part the question was written for")
    print(f"{'q':>3} {'target':<22} {'#1':<30} {'#2':<30} {'#3':<30} {'tgt rank':>8} {'s1~s2':>6}")
    for qi in qs:
        rel = Q[qi]["rel"]
        order = np.argsort(-rel)[:3]
        cells = [f"{'*' if k == target[qi] else ' '}{k:>2} {short(labels[k], 18)} {rel[k]:4.2f}" for k in order]
        rs = Q[qi]["rel_samples"]
        rho = spearman(rs[0], rs[1]) if len(rs) > 1 else float("nan")
        print(f"{qi:>3} {short(labels[target[qi]]):<22} " + " ".join(f"{c:<30}" for c in cells)
              + f" {rank_of(rel, target[qi]):>8} {rho:6.2f}")
    print("s1~s2 = Spearman correlation of the 16 part densities between the two samples")

    # ---- Table 2 -------------------------------------------------------------------------
    rel_mat = np.array([Q[qi]["rel"] for qi in qs])  # (questions, parts)
    med = np.median(rel_mat, axis=0)
    print(f"\nTABLE 2  [{args.block}, layers {L}]  parts drawing attention on questions NOT written for them")
    print("(a) mean rel over non-target questions, per part (high = draws attention regardless of question)")
    rows = []
    for k in range(n):
        non = [i for i, qi in enumerate(qs) if target[qi] != k]
        own = [i for i, qi in enumerate(qs) if target[qi] == k]
        rows.append((rel_mat[non, k].mean(), k, rel_mat[own, k].mean() if own else float("nan")))
    for v, k, own in sorted(rows, reverse=True):
        own_s = f"{own:5.2f}" if own == own else "  n/a"
        print(f"  {k:>2} {short(labels[k], 28):<28} non-target {v:5.2f}   own questions {own_s}   tokens {counts[k]}")
    print(f"(b) question-specific spikes: lift = rel / the part's median rel over all {len(qs)} questions, >= {args.lift}")
    spikes = []
    for i, qi in enumerate(qs):
        for k in range(n):
            if k != target[qi] and med[k] > 0 and rel_mat[i, k] / med[k] >= args.lift:
                spikes.append((rel_mat[i, k] / med[k], qi, k, rel_mat[i, k]))
    for lift, qi, k, v in sorted(spikes, reverse=True):
        print(f"  q{qi:<3} (for {short(labels[target[qi]], 18):<18}) -> part {k:>2} {short(labels[k], 24):<24} "
              f"lift {lift:4.2f}  rel {v:4.2f}")
    if not spikes:
        print("  none")
    own_lift = [rel_mat[i, target[qi]] / med[target[qi]] for i, qi in enumerate(qs)]
    print("  for comparison, lift of the target part on its own questions: "
          + ", ".join(f"q{qi} {x:.2f}" for qi, x in zip(qs, own_lift)))

    # ---- by band and block ---------------------------------------------------------------
    print("\nBY LAYER BAND AND BLOCK  (target part on its own questions; masses are raw, mean over questions)")
    print(f"{'block':<10} {'band':<9} {'mean rank':>9} {'top3':>5} {'tgt rel':>8} {'parts':>6} {'user':>6} "
          f"{'reason':>6} {'answer':>6} {'other':>6} {'sink':>6}")
    for blk in ("reasoning", "answer"):
        for bname in ("early", "middle", "late"):
            QB = by_question(r, blk, bands[bname])
            ranks = [rank_of(QB[qi]["rel"], target[qi]) for qi in qs if qi in QB]
            trel = [QB[qi]["rel"][target[qi]] for qi in qs if qi in QB]
            raw = np.mean([QB[qi]["raw"] for qi in qs if qi in QB], axis=0)
            print(f"{blk:<10} {bname:<9} {np.mean(ranks):9.1f} {np.mean([x <= 3 for x in ranks]):5.0%} "
                  f"{np.mean(trel):8.2f} {raw[:n].sum():6.3f} " + " ".join(f"{raw[cols.index(c)]:6.3f}"
                  for c in ("user", "reasoning", "answer", "other", "sink")))
    print("  per-question target rank by band (answer | reasoning):")
    for qi in qs:
        parts = []
        for blk in ("answer", "reasoning"):
            rk = []
            for bname in ("early", "middle", "late"):
                QB = by_question(r, blk, bands[bname])
                rk.append(rank_of(QB[qi]["rel"], target[qi]) if qi in QB else 0)
            parts.append("/".join(f"{x:>2}" for x in rk))
        print(f"   q{qi:<3} {short(labels[target[qi]], 22):<22} {parts[0]}  |  {parts[1]}")

    # ---- Links and videos on questions 3-5 ----------------------------------------------
    k = next((i for i, lab in enumerate(labels) if lab.lower().startswith("links")), 1)
    print(f"\nPART {k} ({labels[k]}) ON ITS OWN QUESTIONS vs THE REST")
    for blk in ("answer", "reasoning"):
        for bname in ("early", "middle", "late"):
            QB = by_question(r, blk, bands[bname])
            own = [qi for qi in qs if target[qi] == k and qi in QB]
            rest = [qi for qi in qs if target[qi] != k and qi in QB]
            s = "  ".join(f"q{qi}: rank {rank_of(QB[qi]['rel'], k):>2} rel {QB[qi]['rel'][k]:4.2f}" for qi in own)
            if not rest:
                print(f"  {blk:<9} {bname:<7} {s}")
                continue
            print(f"  {blk:<9} {bname:<7} {s}   | other questions: rel {np.mean([QB[qi]['rel'][k] for qi in rest]):4.2f}, "
                  f"best rank {min(rank_of(QB[qi]['rel'], k) for qi in rest)}")
    print("\nquestions:")
    for qi in qs:
        print(f"  q{qi:<3} part {target[qi]:>2}  {question[qi][:90]}")


if __name__ == "__main__":
    main()
