# Detector precision audit

**Data:** 262 detector hits, up to 30 per detector, sampled at random (seed 0) from 1,140
distinct gpt-4o-mini responses in the legacy cache (`cached_results/llm_cache`). Responses
contaminated by the `[sample_i]` tag were excluded. Sampler: `scripts/sample_detector_hits.py`.

**Labels:** an independent LLM annotator (a separate Claude agent that was told not to read the
detector code) judged each hit against the detector's plain-language definition only. The labels
are **not human-validated**.
Labels are in `docs/detector-audit/labels.jsonl`.

**Precision** = true hits / labelled hits still matched by the current pattern, with a Wilson
95% interval. Detectors were revised after the audit where precision was poor. Revised rows are
re-scored on the surviving labelled hits. That is an in-sample number (the revision was written
while looking at those hits), so revised detectors ship as "precision unmeasured" until a fresh sample is labelled.

| Detector | Group | Precision (current pattern) | Note |
|---|---|---|---|
| Apology | Deference | n/a | no hits in the legacy responses |
| Flattery | Deference | n/a | revised (was 0/4); in-sample re-score only, needs a fresh sample, shipped as unmeasured; too few labelled hits to report |
| Hedging | Certainty | 26/26 = 1.00 [0.87, 1.00] | revised (was 26/30); in-sample re-score only, needs a fresh sample, shipped as unmeasured |
| Certainty boost | Certainty | n/a | revised (was 0/7); in-sample re-score only, needs a fresh sample, shipped as unmeasured; too few labelled hits to report |
| List item | Structure | 30/30 = 1.00 [0.89, 1.00] |  |
| Heading | Structure | n/a | no hits in the legacy responses |
| Bold emphasis | Structure | 30/30 = 1.00 [0.89, 1.00] |  |
| Parenthetical | Structure | 15/15 = 1.00 [0.80, 1.00] |  |
| Question back | Interaction | 30/30 = 1.00 [0.89, 1.00] |  |
| Clarification request | Interaction | 30/30 = 1.00 [0.89, 1.00] |  |
| Offer of more help | Interaction | 30/30 = 1.00 [0.89, 1.00] |  |
| Caveat | Framing | 25/25 = 1.00 [0.87, 1.00] |  |
| Disclaimer | Framing | n/a | no hits in the legacy responses |
| Metacommentary | Framing | n/a | revised (was 0/1); in-sample re-score only, needs a fresh sample, shipped as unmeasured; too few labelled hits to report |
| AI self-reference | Framing | n/a | no hits in the legacy responses |
| Exclamation | Tone | 30/30 = 1.00 [0.89, 1.00] |  |
| Emoji | Tone | n/a | no hits in the legacy responses |

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


## gpt-oss-20b audit (2026-11-12)

**Data:** 247 hits from the current detectors. That's up to 20 per detector, sampled (seed 0) from 352 distinct gpt-oss-20b answers in two real runs. Sampler: `scripts/sample_bundle_hits.py`. Labels are in `docs/detector-audit/gpt-oss-20b/labels.jsonl`, from a separate Claude agent that didn't see the detector code. A person hasn't checked them.

| Detector | Precision [Wilson 95%] | Note |
|---|---|---|
| heading | 16/20 = 0.80 [0.58, 0.92] | revised after this audit: shipped as unmeasured |
| list_item | 20/20 = 1.00 [0.84, 1.00] |  |
| hedge | 11/20 = 0.55 [0.34, 0.74] | revised after this audit: shipped as unmeasured |
| emoji | 20/20 = 1.00 [0.84, 1.00] |  |
| parenthetical | 19/20 = 0.95 [0.76, 0.99] |  |
| sympathy | 20/20 = 1.00 [0.84, 1.00] |  |
| clarify | 17/20 = 0.85 [0.64, 0.95] |  |
| question | 20/20 = 1.00 [0.84, 1.00] |  |
| apology | 19/20 = 0.95 [0.76, 0.99] |  |
| unclear | 20/20 = 1.00 [0.84, 1.00] |  |
| bold | 4/20 = 0.20 [0.08, 0.42] | revised after this audit: shipped as unmeasured |
| exclamation | 20/20 = 1.00 [0.84, 1.00] |  |
| offer | 3/5 = 0.60 [0.23, 0.88] | too few hits |
| meta | 1/1 = 1.00 [0.21, 1.00] | too few hits |
| booster | 1/1 = 1.00 [0.21, 1.00] | too few hits |

**Fixed because of this audit:**
- **bold** (4/20): table-row labels and bold lines standing alone are no longer counted.
- **hedge** (11/20): "might" inside the model's own questions no longer counts.
- **heading:** `#` comments in code blocks no longer count. All detectors now ignore code blocks.

These three ship as "unmeasured" until a fresh sample is labelled.

Precision is now stored **per model** in `spet/precision.json`. A run only shows precision measured on its own model's answers, never one borrowed from another model (methodology review, problem 11).
