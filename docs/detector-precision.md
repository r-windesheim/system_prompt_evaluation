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
