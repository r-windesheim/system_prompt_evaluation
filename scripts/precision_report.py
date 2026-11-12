"""Turn hand labels into per-detector precision (Wilson 95% CI).

Revised detectors are re-scored on the labelled hits their *current* pattern still
matches. Hits outside the labelled sample are not covered, so treat revised numbers
as estimates.

    python scripts/precision_report.py   # writes spet/precision.json and docs/detector-precision.md
"""
import json, math, re
from collections import defaultdict
from pathlib import Path

from spet.detectors import BY_ID, DETECTORS, spans

ROOT = Path(__file__).resolve().parents[1]
hits = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "docs/detector-audit/hits.jsonl").read_text().splitlines()}
labels = [json.loads(l) for l in (ROOT / "docs/detector-audit/labels.jsonl").read_text().splitlines()]


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


orig = defaultdict(lambda: [0, 0])
cur = defaultdict(lambda: [0, 0])
for lab in labels:
    h = hits[lab["id"]]
    tp = lab["verdict"] == "tp"
    orig[h["detector"]][0] += tp
    orig[h["detector"]][1] += 1
    # does the current detector still match this exact text in its context?
    ctx = h["context"]
    s = ctx.index("⟦"); e = ctx.index("⟧")
    text = ctx[:s] + ctx[s + 1:e] + ctx[e + 1:]
    still = any(a < e - 1 and b > s for a, b, _ in spans(text, (BY_ID[h["detector"]],)))
    if still:
        cur[h["detector"]][0] += tp
        cur[h["detector"]][1] += 1

out, rows = {}, []
for d in DETECTORS:
    k0, n0 = orig.get(d.id, (0, 0))
    k, n = cur.get(d.id, (0, 0))
    lo, hi = wilson(k, n)
    if n >= 10:
        out[d.id] = {"precision": round(k / n, 3), "n": n}
    pr = f"{k}/{n} = {k/n:.2f} [{lo:.2f}, {hi:.2f}]" if n else "n/a"
    note = "" if (k0, n0) == (k, n) else f"revised (was {k0}/{n0})"
    if n0 == 0:
        note = "no hits in the legacy responses"
    elif n < 10:
        note = (note + "; " if note else "") + "too few labelled hits to report"
    rows.append(f"| {d.label} | {d.group} | {pr} | {note} |")

(ROOT / "spet/precision.json").write_text(json.dumps(out, indent=1) + "\n")
md = f"""# Detector precision audit

**Data:** {len(labels)} detector hits, up to 30 per detector, sampled at random (seed 0) from 1,140
distinct gpt-4o-mini responses in the legacy cache (`cached_results/llm_cache`). Responses
contaminated by the `[sample_i]` tag were excluded. Sampler: `scripts/sample_detector_hits.py`.

**Labels:** an independent annotator (a separate Claude subagent that was told not to read the
detector code) judged each hit against the detector's plain-language definition only.
Labels are in `docs/detector-audit/labels.jsonl`.

**Precision** = true hits / labelled hits still matched by the current pattern, with a Wilson
95% interval. Detectors were revised after the audit where precision was poor. Revised rows are
re-scored on the surviving labelled hits.

| Detector | Group | Precision (current pattern) | Note |
|---|---|---|---|
""" + "\n".join(rows) + """

## What this does and doesn't show
- The legacy responses are mostly short clarification requests (the old queries had no
  context), so detectors that fit that genre (question, clarify, offer) look near-perfect.
  Precision on varied, substantive answers is unmeasured until the first real run.
- Several detectors (apology, heading, disclaimer, AI self-reference, emoji) had **no** hits,
  so their precision is unknown. The viewer shows "unmeasured" for them.
- This audit measures precision only, not recall.

## Changes made because of it
- **Booster:** bare "clearly" was 0/7 (always a manner adverb, as in "clearly understand"). Now it only
  matches stance uses ("it is clearly", sentence-initial "Clearly,").
- **Flattery:** "good idea" was 0/4 ("whether it's a good idea or not"). Removed.
- **Meta:** "here's a/the/how" was 0/1 (it introduces a real answer). Removed.
- **Hedge:** 4/30 false positives were "what might be wrong"-style embedded questions. These are now excluded.
"""
(ROOT / "docs/detector-precision.md").write_text(md)
print("\n".join(rows))
