# SPET integration handoff

Handoff context for whoever (or whichever Claude session) picks up the task of wiring `system_prompt_evaluation/` into **windesheim.co** so it's reachable from `/projects/`.

## Where we are

- Richard copied his SPET repo into this repo at `system_prompt_evaluation/` (the original repo still exists elsewhere on disk).
- The inner `.git` has been removed — SPET is now plain files inside the personal-website repo, no nested-git mess.
- Root `.gitignore` updated to exclude SPET's runtime artifacts (`venv/`, `__pycache__`, `cached_results/llm_cache/`, `logs/`, `evaluation_history/`, `results/`). The `.env` file is already covered by the root `.env*` rule.
- Nothing has been committed yet; the SPET folder is currently untracked.
- On the site, `/projects/` lists SPET as `PRJ-001` but does **not** link to a demo. Goal of this work: make it clickable.

## What SPET actually is (the constraint)

**Not a static frontend.** It's a full-stack app:

- **Frontend:** Next.js 14 (Pages Router) + TypeScript + Tailwind, in `system_prompt_evaluation/frontend/`.
- **Backend:** FastAPI (Python 3.9+), in `system_prompt_evaluation/api.py`. Handles orchestration of async LLM calls.
- **LLM:** OpenRouter (GPT-4o and GPT-5-nano), called through the Latteries framework in `utils/latteries/caller.py`.
- **API key:** `system_prompt_evaluation/.env` holds `OPENROUTER_API_KEY`. **Do not commit.**
- **Storage:** SQLite-free — uses CSV files in `cached_results/`, CSV backups in `evaluation_history/`, logs in `logs/`.

Because the backend runs Python and calls OpenRouter with a secret key, **you cannot sub-path host this on Cloudflare Pages the way `admin/` is hosted.** Cloudflare Pages serves only static files; the FastAPI server has nowhere to run, and putting the OpenRouter key in client-side JS is not acceptable.

## Integration options, ranked

### 1. Source-in-repo, GitHub-linked, no live demo *(recommended v1)*
The SPET code lives in this repo as source-of-truth for the public. The `/projects/` entry for SPET adds a `source →` link to the GitHub directory. No live demo. If Richard wants a live demo eventually, that ships separately.

**Pros:** Zero infra work. The code itself is the portfolio artifact. Matches how many strong research-engineer sites work (e.g., linking to GitHub repos).
**Cons:** No interactive demo. Recruiter has to read code to judge depth.
**Cost:** $0.
**Effort:** ~5 min (add entry-link, commit).

### 2. Separate subdomain deployment with a small budget *(recommended v2 if Richard wants a live demo)*
Host SPET on Fly.io / Railway / Render (any provider that runs both Python backends and Next.js frontends). Map `spet.windesheim.co` to it via Cloudflare DNS CNAME. Link from `/projects/` entry.

**Pros:** Fully functional live demo. Independent deploy cycle. Doesn't add infra coupling to the personal site.
**Cons:** Running cost for the backend (small — Fly.io free tier or ~$5/mo). Visitors burn OpenRouter credit when they run analyses.
**Mitigations for the cost concern:**
- Rate-limit by IP.
- Lock the free demo to a single preset test prompt, cached results only.
- Require visitors to paste their own OpenRouter key (demo form pattern).
- Add a "request-access" gate if anonymous usage is undesirable.
**Effort:** ~2–4 hours, plus DNS. Also needs a Dockerfile or provider-specific config.

### 3. Static frontend-only demo with cached results *(middle ground)*
Build the Next.js frontend pointing to a static JSON file of example results (or to a Cloudflare Workers API that only serves cached responses). Ship to `out/spet/` as part of the site's build. Visitors see a walkthrough of a pre-run analysis but cannot submit their own prompts.

**Pros:** Hosted on Cloudflare alongside the rest of the site. No running backend. Zero API cost per visit.
**Cons:** Not really a demo — it's a showcase. Lower signal than #2.
**Effort:** ~3–5 hours (stub the API layer in the frontend, pick an illustrative pre-run, adapt the build step).

### 4. Port the backend to Cloudflare Workers (TypeScript rewrite)
Rewrite `api.py` and the LLM-calling logic in TypeScript, deploy as a Worker bound to `/api/spet/*`. Frontend can live at `/spet/`.

**Not recommended.** The Latteries framework (1340+ lines of Python), the scipy-based statistical analysis, and the pandas pipelines are non-trivial ports. Probably weeks of work, and duplication of functionality already working in Python.

## What to do right now

Recommendation: **ship option 1 today, flag option 2 for a later pass when Richard has bandwidth for infra.**

Concrete steps for option 1:

1. **Commit SPET into this repo.** From `/Users/richardwindesheim/Downloads/Personal-Website/`:
   ```sh
   git add system_prompt_evaluation/ .gitignore
   git status   # verify .env, venv/, __pycache__/, node_modules/, cached_results/llm_cache/ are NOT listed
   git commit -m "Add system_prompt_evaluation source"
   git push origin HEAD:refs/heads/redesign/terminal-nav  # direct push to main is blocked
   ```

2. **Add a GitHub link to PRJ-001 on `/projects/`.** Edit `app/projects/page.tsx`:

   ```tsx
   <article className="entry">
     <div className="entry-header">
       <span className="entry-id">PRJ-001</span>
       <span className="entry-title">System Prompt Evaluation Tool</span>
     </div>
     <div className="entry-meta">built with Daniel Paleka · 2025</div>
     <p className="entry-desc">
       {/* ... existing ... */}
     </p>
     <div className="entry-links">
       <a
         className="entry-link"
         href="https://github.com/r-windesheim/Personal-Website/tree/main/system_prompt_evaluation"
         target="_blank"
         rel="noopener noreferrer"
       >
         source
       </a>
     </div>
   </article>
   ```

   (Verify the URL resolves after the PR merges to main — the `tree/main/...` path will exist once SPET is pushed.)

3. **Verify the build still passes.** The Cloudflare build runs `next build` which doesn't touch Python files, so adding `system_prompt_evaluation/` shouldn't affect anything — but confirm by running `npm run build` locally.

## Pre-flight safety checks (before commit)

Before running `git add`, verify:

- [ ] `system_prompt_evaluation/.env` is **not** tracked — should show as ignored by `git check-ignore system_prompt_evaluation/.env`.
- [ ] `system_prompt_evaluation/venv/` is ignored.
- [ ] `system_prompt_evaluation/__pycache__/` is ignored (and every nested one).
- [ ] `system_prompt_evaluation/frontend/node_modules/` is ignored.
- [ ] `system_prompt_evaluation/cached_results/llm_cache/` is ignored (can be large).
- [ ] `system_prompt_evaluation/logs/` is ignored.
- [ ] `system_prompt_evaluation/.DS_Store` is ignored (covered by root rule).
- [ ] No file inside SPET contains an API key outside `.env` — scan with:
  ```sh
  grep -r "sk-" system_prompt_evaluation/ --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.json" --exclude-dir=node_modules --exclude-dir=venv --exclude-dir=__pycache__
  ```
  and verify each hit is either a placeholder or a comment.

If any of these are tracked when they shouldn't be, add the rule to `.gitignore` and `git rm --cached <path>` before committing.

## When Richard is ready for option 2 (live demo)

Sketch for the subdomain deploy:

1. **Containerize SPET.** Add a `Dockerfile` in `system_prompt_evaluation/` that installs Python deps, runs the frontend build, and serves frontend static + FastAPI via a single process (or runs them on two internal ports behind a reverse proxy).
2. **Pick a host.** Fly.io is the least-friction for a combined Python + Next app. Railway and Render also work.
3. **DNS.** In Cloudflare, add a CNAME `spet.windesheim.co → <host>.fly.dev` (or equivalent).
4. **Gate the demo.** Either (a) require a paste-your-own-key form, or (b) preset a single prompt and cache all responses. Anonymous unrestricted LLM access will burn money fast.
5. **Link from `/projects/`.** Update the `entry-link` to point at `https://spet.windesheim.co`.

## Open questions for Richard

- **Is Daniel Paleka OK with the SPET code being publicly on `r-windesheim/Personal-Website`?** It was in a separate repo before — moving it into the personal-site repo makes it visible under Richard's GitHub profile. If Daniel wants co-ownership or attribution in-repo, add a `CONTRIBUTORS.md` or keep a Daniel-authored line in the README.
- **Is a live demo necessary now**, or is a "source →" link enough for this round of outreach? This decides whether we stop at option 1 or invest in option 2.
- **Is the CLAUDE.md in `system_prompt_evaluation/` still useful to keep?** It documents the tool for future AI coding sessions but is specific to SPET, not windesheim.co. Fine to leave; just noting it'll be visible on GitHub.

## Files to know

- `system_prompt_evaluation/README.md` — user-facing documentation for SPET itself.
- `system_prompt_evaluation/CLAUDE.md` — AI agent guidance for SPET dev, exhaustive.
- `system_prompt_evaluation/PROJECT_STRUCTURE.md` — file-level tree.
- `system_prompt_evaluation/api.py` — FastAPI backend entry.
- `system_prompt_evaluation/frontend/package.json` — Next.js + Tailwind frontend.
- `system_prompt_evaluation/.env` — **contains OpenRouter API key. Never commit.**
- `system_prompt_evaluation/start.sh` — local two-process launcher for dev.
- `system_prompt_evaluation/deprecated/streamlit/` — old UI, not part of the current system.
