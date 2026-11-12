"""Sample detector hits from cached legacy gpt-4o-mini responses for a precision audit.

    python scripts/sample_detector_hits.py --per-detector 18 -o docs/detector-audit/hits.jsonl
"""
import argparse, json, random, re
from pathlib import Path

from spet.detectors import DETECTORS, spans

ap = argparse.ArgumentParser()
ap.add_argument("--cache", default="cached_results/llm_cache/openai/gpt-4o-mini.jsonl")
ap.add_argument("--per-detector", type=int, default=18)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("-o", "--out", default="docs/detector-audit/hits.jsonl")
a = ap.parse_args()

texts = []
for line in Path(a.cache).read_text().splitlines():
    try:
        t = json.loads(json.loads(line)["response"])["choices"][0]["message"]["content"] or ""
    except Exception:
        continue
    if t.strip() and "[sample_" not in t and "sample_" not in t:  # drop responses contaminated by the M1 tag
        texts.append(t)
texts = sorted(set(texts))
rng = random.Random(a.seed)
pool = {d.id: [] for d in DETECTORS}
for ti, t in enumerate(texts):
    for s, e, d in spans(t):
        pool[d].append((ti, s, e))
rows = []
for d in DETECTORS:
    hits = pool[d.id]
    for ti, s, e in rng.sample(hits, min(a.per_detector, len(hits))):
        t = texts[ti]
        lo, hi = max(0, s - 160), min(len(t), e + 160)
        rows.append(dict(id=f"{d.id}-{len(rows)}", detector=d.id, label=d.label, definition=d.description,
                         match=t[s:e], context=t[lo:s] + "⟦" + t[s:e] + "⟧" + t[e:hi]))
rng.shuffle(rows)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
print(f"{len(texts)} clean responses; pool sizes:", {k: len(v) for k, v in pool.items()})
print(f"wrote {len(rows)} hits to {a.out}")
