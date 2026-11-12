# SPET overhaul plan (2026-11)

Branch: `overhaul/2025-redesign`. Pre-overhaul state is snapshotted on `wip/pre-overhaul`.
Each step below is one commit or a short series of commits. Push the branch regularly and open one PR at the end.

## Goal

Rebuild SPET (System Prompt Evaluation Tool) from the ground up into a tool that:

1. Gives a **methodologically honest** answer to "which section of my system prompt causes which stylistic quirk?"
2. Looks like a clean, 2025-era product, with motion design that *explains the method*. The core animation is section removed → responses change → quirk effect moves.
3. Is **presentable on windesheim.co**: a static-exportable viewer of recorded runs, so no backend or API key is needed to show it.

## Constraints

- No OpenRouter. No compute until a self-hosted model runs on **Modal**. Until then, everything must be buildable and verifiable without any model calls.
- The engine talks to *any* OpenAI-compatible endpoint (`base_url` + `model`). Modal + vLLM exposes exactly that, so turning it on later is a config change.
- The website repo is only touched at the very end, on its own branch and PR.

## Audit findings (Phase 0, from the code and the recorded runs)

### Method

| # | Finding | Where | Consequence |
|---|---|---|---|
| M1 | The cache-buster `"[sample_{i}_t0.5]"` is appended to the **user message**. | `quirk_analyzer.py:909` | The model answers the tag ("the term '[sample_0_t0.5]' isn't clear…"), which contaminates every response. 13 of 36 recorded runs contain it verbatim in stored responses. |
| M2 | Default queries are context-free ("Should I do this?", "Can you fix it?"). | `config.py:271` | Almost every response is a clarification request, so quirk rates measure the query, not the prompt. |
| M3 | Unpaired `ttest_ind`, even though every config uses the same (query, sample) schedule. | `quirk_analyzer.py:996` | Wastes power. The design is paired. |
| M4 | ~40 quirks × k sections are tested with no multiple-comparison correction, and only the *top* section is kept per quirk. | `:1320–1456` | Selection on the max plus no FDR gives false discoveries by construction. |
| M5 | Thresholds were lowered "to show more quirks" (`spike_threshold` 1.2, `min_impact` 0.5). | `api.py` (WIP) | Results get tuned for density, not truth. |
| M6 | Phrase highlighting paints the category-level removal effect onto every matched phrase. | `generate_showcase_response` | Implies per-phrase causality the method doesn't measure. This is the overclaim flagged in the related-work report. |
| M7 | The semantic comparative score is inverted with `100 - val`, and its own comments contradict each other. | `:1280–1287` | Sign is unclear, so the semantic results can't be trusted. |
| M8 | Regex detectors are loose: `like` → example, `may` → hedge, `always/never` → certainty, `\w+ed` → past tense, `but/yet` → caveat. | `detect_quirks` | Precision is unknown, probably low on several detectors. |
| M9 | Cache keys hash the full request, but prompts aren't stored with responses, and the CSVs keep one example per quirk with section text truncated to 100 chars. | `cached_results/`, `results/` | Recorded data can't be reconstructed into full response sets. It can serve as a labelled **dev fixture**, never as showcase content. |

### Product / UI
- There are two half-finished UIs (Next 14 pages router, plus Streamlit references in `CLAUDE.md` for an `app.py` that no longer exists), and ~1.3k lines of stale summary docs.
- Results require a live FastAPI backend and an API key, so nothing can be shown statically.
- Ad-hoc components (`Badge`, `Card`, `Button`, …) have no token system, and motion is incidental.

## Architecture (target)

```
spet/                 Python engine (pip-installable, no web deps)
  providers.py        OpenAICompatible(base_url, model, api_key) + StubProvider (tests)
  schedule.py         deterministic (config, query, sample_idx, seed) plan; cache salt lives here, never in the prompt
  detectors.py        regex detectors that return SPANS (start, end, label), not just rates
  attribution.py      paired leave-one-out effects, bootstrap CIs, Benjamini–Hochberg FDR; optional Monte Carlo Shapley
  bundle.py           pydantic RunBundle schema + JSON Schema export
  cli.py              `python -m spet run spec.yaml -o bundle.json`, `python -m spet validate bundle.json`
tests/                pytest; stub-model planted-instruction tests
web/                  Next 16 / React 19 / Tailwind v4 / Motion; `output: 'export'`, configurable basePath
  public/runs/*.json  run bundles (the only data the site reads)
docs/                 this plan, method note, detector-precision report
```

### The run bundle (contract between engine and viewer)

```jsonc
{
  "schema_version": 1,
  "meta": { "id", "title", "created_at", "model", "provider", "temperature", "n_per_query", "seed",
            "queries": [...], "fixture": false, "notes" },
  "sections": [{ "id": 0, "label": "Tone", "text": "<full text>" }],
  "configs": [{ "id": "full", "removed": null }, { "id": "without_0", "removed": 0 }, ...],
  "responses": [{ "config": "full", "query_idx": 0, "sample_idx": 3, "text": "...",
                  "spans": [{ "start": 12, "end": 18, "detector": "hedge" }] }],
  "detectors": [{ "id": "hedge", "label": "Hedging", "group": "Certainty", "unit": "per response",
                  "precision": 0.91 | null }],
  "effects": [{ "detector": "hedge", "section": 2, "full_mean", "ablated_mean", "delta",
                "ci": [lo, hi], "p": 0.003, "q": 0.02, "significant": true }]
}
```

The viewer keeps two layers **visually distinct**:
- **Observation:** "this phrase matched the Hedging detector" (spans).
- **Attribution:** "removing section 2 changed hedging by −0.8 [−1.1, −0.5] matches per response, q = 0.02" (effects).

Phrases are never coloured by section.

## Steps

Each step lists its deliverable and the check that marks it done.

### Phase 1: Repo hygiene
1. **Plan + hygiene.** Add this doc. Untrack `.claude/settings.local.json` and add it to `.gitignore`. Rewrite `CLAUDE.md` for the new layout.
   *Check:* `git status` is clean, and no tracked file contains secrets (`git grep` for key patterns).

### Phase 2: Engine (no compute needed)
2. **Bundle schema.** `spet/bundle.py` with pydantic models, and export `docs/run-bundle.schema.json`.
   *Check:* `pytest tests/test_bundle.py` round-trips a bundle.
3. **Span detectors.** Port the detectors to return spans, and tighten the obviously loose ones (M8): drop `like`, `may`→modal only, past-tense removed from the default set, `but/yet` sentence-initial only.
   *Check:* unit tests with positive and negative examples for each detector.
4. **Schedule + providers.** Deterministic schedule with the cache salt outside the prompt (fixes M1). `OpenAICompatible` provider with a disk cache keyed on (request, salt). `StubProvider` for tests.
   *Check:* a test asserts that no user message sent to the provider contains anything beyond the query text.
5. **Attribution.** Paired per-(query, sample) deltas, a bootstrap 95% CI on the mean delta, a sign-flip permutation p-value, and BH-FDR across all (detector, section) pairs (fixes M3/M4/M5). Report all sections, not just the max. Optional Monte Carlo Shapley over sections, behind a flag.
   *Check:* **planted-instruction stub test.** A stub model emits "sorry" only when section k is in the system prompt and "perhaps" only when section j is. The pipeline must flag (apology, k) and (hedge, j) as significant and nothing else at q < 0.05, across 5 seeds.
6. **CLI.** `run` and `validate` commands, plus a YAML run spec. Better default queries: concrete, context-bearing tasks such as an email rewrite, a debugging question and an explanation (fixes M2).
   *Check:* `python -m spet run examples/stub.yaml` produces a bundle that `validate` accepts.
7. **Dev fixture.** Convert the latest clean recorded run (one whose responses don't contain the tag) into a bundle with `meta.fixture = true`. Plus a richer synthetic demo bundle from the stub model, so the viewer has every state to render.
   *Check:* both validate. The fixture contains no `[sample_` text.

### Phase 3: Detector validation (no compute needed)
8. **Precision audit.** Sample ~300 detector hits from the 2,886 cached gpt-4o-mini responses (`cached_results/llm_cache`). Hand-label each hit as a true or false instance of the quirk. Report per-detector precision with Wilson CIs in `docs/detector-precision.md`. Detectors below 0.7 are dropped or rewritten. Precision is shipped in the bundle and shown in the UI.
   *Check:* the report is committed, and detector changes are backed by the numbers.

### Phase 4: Visual overhaul (`web/`)
9. **Scaffold.** Next 16 / React 19 / Tailwind v4 / Motion, static export, `NEXT_PUBLIC_BASE_PATH`. Design tokens: one type family (Geist Sans/Mono), 4-pt spacing, a neutral palette plus one accent, and a categorical scale only for detector groups. Light and dark. Dev port 3100.
   *Check:* `npm run build` exports with zero type errors.
10. **Run index.** A list of bundles with model, date, sections and the top significant effects. Fixture runs are clearly badged.
11. **Run view: the prompt.** Sections as a vertical stack. Hovering or selecting a section highlights its significant effects.
12. **Run view: the ablation.** The signature interaction. Toggling a section off animates it out (layout animation), and the response pane cross-fades from the `full` sample to the matching `without_k` sample (same query and sample index, so it's a true paired comparison). Effect bars spring to their new values. A word-level diff is shown inline.
13. **Effects matrix.** Detectors × sections with CI bars or dot-and-whisker per cell. Non-significant cells are muted. Clicking a cell opens the paired examples.
14. **Responses explorer.** Filter by config, query or detector. Spans are underlined in their detector-group colour, explicitly labelled "detector match", never "caused by".
15. **Method page.** A short, plain explanation of LOO, pairing, CIs, FDR and detector precision, plus the related-work positioning (integration claim, not novelty of the method). Links to the GitHub repo.
16. **Motion pass.** Shared-element transitions between index and run, staggered reveals, spring presets in one `motion.ts`. Every animation has a `prefers-reduced-motion` path (opacity only).
   *Check (Phase 4):* axe shows 0 serious violations. Lighthouse accessibility ≥ 95 on the export. Chrome profiling shows no long frames during the ablation toggle. Before/after screenshots are committed to `docs/screenshots/` (taken with the bundled-chromium node script, not Playwright MCP).

### Phase 5: Cleanup
17. **Remove the legacy stack.** Delete the old `frontend/`, `api.py`, `evaluation.py`, `run_evaluation.py`, `deprecated/`, `archived_features/` and stale docs. They stay in history and on `wip/pre-overhaul`. A thin optional FastAPI `serve` for live runs comes back only when Modal exists.
18. **README.** What it is, a screenshot/GIF, how to run the viewer, how to produce a bundle, the method caveats.
   *Check:* a fresh clone can run `pip install -e . && pytest`, then `cd web && npm ci && npm run build`.

### Phase 6: Waits on Modal (do not start without Richard)
19. A Modal vLLM endpoint (e.g. a Qwen-class open-weights model). Then a first clean run → a real showcase bundle.
20. Real-model validation: planted-instruction recovery on a real model, seed stability, and an optional comparison with ContextCite/TokenSHAP. Token-level logprob attribution becomes possible here.
21. Website integration: a separate branch + PR in the Personal-Website repo (PRJ-001 link or an embedded static export under a basePath). Exclude the unrelated `QUICK_START.md` change.

## Definition of done (for the no-compute phases)
- `pytest` is green, including the planted-instruction stub test across seeds.
- All bundles validate against the schema.
- `web` static export builds clean.
- axe 0 serious violations and Lighthouse accessibility ≥ 95.
- Reduced-motion path verified.
- Before/after screenshots are committed.
- One PR from `overhaul/2025-redesign` → `main`.

## Log
- **Step 5 finding (2026-11-12).** With the legacy per-100-words rates, the planted stub test produced *spurious significant* effects. The apology section lengthened answers, which diluted the hedge rate (q = 0.003 for a section with no hedging instruction). The attribution metric is now **matches per response**. The planted test now requires the significant set to equal the planted set exactly, across 5 seeds.
- **Step 7 decision.** No legacy-fixture bundle. The recorded CSVs hold about one with/without example per quirk, so they can't support paired effects, and a bundle built from them would show attributions the data can't back. The viewer is built against the synthetic planted-instruction demo (`examples/stub-demo.yaml` → `web/public/runs/stub-demo.json`), which is clearly badged as synthetic. Real showcase content comes from the first Modal run (Phase 6).
- **Phase 4 checks (2026-11-12)**, against the static export served by `python -m http.server` (no compression):
  - axe (WCAG 2.1 AA): 0 violations on /, /runs/stub-demo/ and /method/, in light and dark.
  - Lighthouse accessibility 100, best practices 100 and SEO 100 on all pages. Performance: run page 90, method 87, home 77. The home figure is limited by the uncompressed 257 KB bundle fetch, which gzips to 22 KB on Cloudflare.
  - Frames while toggling sections at 4× CPU throttle: p95 16.7 ms, 0 frames over 50 ms.
  - Reduced motion: no section rows move after a toggle, and diff words don't blur. Motion's `reducedMotion` doesn't cover height or filter animations, so those use explicit instant transitions.
  - Found and fixed: inlining the bundle into HTML made the pages 304 KB, so bundles are now fetched after first paint (HTML is 16 KB).
  - Reproduce: `node web/scripts/audit.mjs` (axe, frames, reduced motion). Lighthouse was run through its Node API, because the CLI refuses x64 Node on Apple Silicon.
- **Pre-PR review (2026-11-12).**
  - **Overclaims fixed:** "independent annotator" now says it was an LLM (Claude) annotator, not human-validated. The sign-flip test is described as exact only up to 16 pairs. Shapley is described as estimator-only (subset runs aren't wired up).
  - **Hedge precision:** the 26/26 figure came from re-scoring on the same hits used to write the revision, so it was in-sample. Revised detectors now ship as unmeasured.
  - **Demo:** now uses debugging questions that the stub's filler actually answers.
