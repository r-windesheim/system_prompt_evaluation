"""Sample current-detector hits from run bundles for a per-model precision audit.

    python scripts/sample_bundle_hits.py web/public/runs/a.json web/public/runs/b.json \
        --per-detector 20 -o docs/detector-audit/gpt-oss-20b/hits.jsonl
"""
import argparse, json, random
from pathlib import Path

from spet.detectors import DETECTORS, spans

ap = argparse.ArgumentParser()
ap.add_argument("bundles", nargs="+")
ap.add_argument("--per-detector", type=int, default=20)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()

texts = sorted({r["text"] for b in a.bundles for r in json.loads(Path(b).read_text())["responses"] if r["text"].strip()})
pool = {d.id: [] for d in DETECTORS}
for ti, t in enumerate(texts):
    for s, e, d in spans(t):
        pool[d].append((ti, s, e))
rng = random.Random(a.seed)
rows = []
for d in DETECTORS:
    for ti, s, e in rng.sample(pool[d.id], min(a.per_detector, len(pool[d.id]))):
        t = texts[ti]
        lo, hi = max(0, s - 200), min(len(t), e + 200)
        rows.append(dict(id=f"{d.id}-{len(rows)}", detector=d.id, label=d.label, definition=d.description,
                         match=t[s:e], context=t[lo:s] + "⟦" + t[s:e] + "⟧" + t[e:hi]))
rng.shuffle(rows)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
print(f"{len(texts)} distinct responses; pool:", {k: len(v) for k, v in pool.items() if v})
print(f"wrote {len(rows)} hits to {a.out}")
