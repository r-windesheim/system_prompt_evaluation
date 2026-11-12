# CLAUDE.md

SPET attributes stylistic quirks in model responses to sections of a system prompt, using paired leave-one-out ablation. Read `README.md` for usage and `docs/OVERHAUL_PLAN.md` for the design, the audit and the decision log.

## Commands
- Engine: `source venv/bin/activate && pytest`. Running `python -m spet run <spec.yaml> -o <bundle.json>` writes a bundle, and `python -m spet validate <files>` checks it.
- Viewer: `cd web && npm run dev` (port 3100), `npm run build` (static export to `web/out`), `npx tsc --noEmit`.
- Viewer checks: serve `web/out` (e.g. `python3 -m http.server 3101`), then `node scripts/audit.mjs` and `node scripts/shots.mjs <dir>`. These need `npm i -D playwright @axe-core/playwright --no-save` and `npx playwright install chromium`.

## Invariants (don't break these)
- **The run bundle is the only contract** between engine and viewer: `spet/bundle.py`, with its schema exported to `docs/run-bundle.schema.json`. If you change one, regenerate the schema, update `web/lib/types.ts`, and bump `schema_version` for breaking changes.
- **Nothing but the query goes in the user message.** Seeds and cache salts are request parameters (`spet/schedule.py`). `tests/test_schedule.py` guards this.
- **The attribution metric is matches per response,** not a per-word rate. Rates leak length effects across quirks.
- **The planted-instruction test must stay exact:** the significant set equals the planted set.
- **The viewer never colours a phrase by section.** Spans are "detector matches". Attribution lives only in effects, with CIs and q-values.
- **The viewer is static.** Bundles are fetched from `/runs/<id>.json` after first paint, and `NEXT_PUBLIC_BASE_PATH` must keep working.
- Motion presets live in `web/lib/motion.ts`. Height and filter animations need an explicit reduced-motion path (`instant`).

## Models
There is no hosted API key in this repo. Real runs target an OpenAI-compatible endpoint (planned: vLLM on Modal), configured per spec. See `examples/modal-template.yaml`.
