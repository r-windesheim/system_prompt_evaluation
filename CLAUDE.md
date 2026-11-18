# CLAUDE.md

SPET attributes stylistic quirks in model responses to sections of a system prompt, using paired leave-one-out ablation. Read `README.md` for usage and `docs/OVERHAUL_PLAN.md` for the design, the audit and the decision log.

## Commands
- Engine: `source venv/bin/activate && pytest`. Running `python -m spet run <spec.yaml> -o <bundle.json>` writes a bundle, and `python -m spet validate <files>` checks it.
- `python -m spet plan <spec.yaml>`: answer count, upper bounds on discovery calls, and per BH family the first threshold and the smallest reachable p. No model calls; run it before any real run.
- `python -m spet discover <bundle.json> -o <out.json> [--screen <screen.json>]`: discovery on an existing bundle (judge calls only). `python -m spet run <spec> --discover` does both. See `docs/discovery.md`.
- `python -m spet confirm <bundle.json> <confirm.yaml> -o <out.json> [--plan] [--max-answers N] [--max-judge-calls N]`: retest screen candidates (fixed rule) on fresh questions; writes schema 6 with a `confirmation` block. Run it once; see `docs/discovery.md`, "Confirmation".
- `python -m spet readout <bundle.json> -o <out.json> [--audit <audit.yaml>]`: per intended statement, "does the model do it" (rate with the part) and "is the part the reason" (confirmation only), and one reading per part; schema 7, no model calls. See `docs/discovery.md`, "Two questions".
- `python -m spet authored <bundle.json> <statements.yaml> -o <out.json> [--plan] [--max-judge-calls N]`: judge author-written, pre-registered statements on the stored answers (judge calls only); schema 8 `authored` block, read by `spet readout`. See `docs/discovery.md`, "Author-written statements".
- Attention screen: `modal run deploy/modal_attention.py::screen --smoke` (renders every prompt, one short generation) and `modal run deploy/modal_attention.py::screen [--spec ...] [--samples 4]` (the full screen, about an hour of H100 time for the July 2024 example). Both are paid GPU calls: ask first.
- Viewer: `cd web && npm run dev` (port 3100), `npm run build` (static export to `web/out`), `npx tsc --noEmit`.
- Viewer checks: build without `NEXT_PUBLIC_SPET_API`, serve `web/out` (e.g. `python3 -m http.server 3101`), then `node scripts/audit.mjs`, `node scripts/shots.mjs <dir>` and `node scripts/edge-cases.mjs <dir>`. The live flow: `node scripts/live.mjs <dir>` against a build pointed at a `spet serve` backed by `spet mock` (it refuses any other model). These click Split and Test, so never point them at an API that reaches a paid endpoint. They need `npm i -D playwright @axe-core/playwright --no-save` and `npx playwright install chromium`.

## Invariants (don't break these)
- **The run bundle is the only contract** between engine and viewer: `spet/bundle.py`, with its schema exported to `docs/run-bundle.schema.json`. If you change one, regenerate the schema, update `web/lib/types.ts`, and bump `schema_version` for breaking changes.
- **Nothing but the query goes in the user message.** Seeds and cache salts are request parameters (`spet/schedule.py`). `tests/test_schedule.py` guards this.
- **The attribution metric is matches per response,** not a per-word rate. Rates leak length effects across quirks.
- **The planted-instruction test must stay exact:** the significant set equals the planted set. The same holds for discovery (`tests/test_discovery.py`).
- **Discovery tests by question** (sign flips over whole questions) and corrects intended and discovered statements as two separate BH families. Don't loosen alpha, the test or the blocking flags to get findings; add questions instead.
- **The held-out split:** discovered statements are proposed from `discovery_queries` and verified only on `holdout_queries`, minus the part's own targets. The attention screen only reorders the proposer's pairs within the discovery questions; it never enters a test.
- **Run specs:** a query is a string or `{text, targets}` (section labels or ids). `n_per_query` is the count where a question targets the removed part; `n_per_query_untargeted` the count elsewhere. Append new questions at the end: bundles and docs refer to questions by index.
- **The viewer never colours a phrase by section.** Spans are "detector matches". Attribution lives only in effects, with CIs and q-values.
- **The viewer is static.** Bundles are fetched from `/runs/<id>.json` after first paint, and `NEXT_PUBLIC_BASE_PATH` must keep working.
- Motion presets live in `web/lib/motion.ts`. Height and filter animations need an explicit reduced-motion path (`instant`).

## Models
There is no hosted API key in this repo. Real runs target an OpenAI-compatible endpoint, vLLM 0.18.1 on Modal (`deploy/modal_vllm.py`, app `spet-vllm`), configured per spec. See `examples/modal-template.yaml`. The attention pilot and screen are a separate one-shot Modal app (`spet-attention`) that runs transformers, not vLLM, but renders the prompt the way vLLM does.
