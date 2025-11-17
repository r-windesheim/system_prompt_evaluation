# Codebase Cleanup Summary

## What Was Moved to `deprecated/`

### Streamlit UI (Replaced)
- ✅ `app.py` → `deprecated/streamlit/app.py`
- ✅ `utils/ui_helpers.py` → `deprecated/streamlit/ui_helpers.py`

**Reason:** Replaced by React UI (`/frontend`) + FastAPI (`/api.py`)

### Analysis Scripts (Archived)
- ✅ `analysis/` → `deprecated/analysis_scripts/`
  - 15+ exploratory Python scripts
  - Used for research/data exploration
  - Not imported by core system

**Reason:** Standalone research tools, not part of core application

### Test Files (Archived)
- ✅ `test_imports.py` → `deprecated/test_files/`
- ✅ `test_multi_query.py` → `deprecated/test_files/`
- ✅ `check_quirk_responses.py` → `deprecated/test_files/`
- ✅ `inspect_quirk_responses.py` → `deprecated/test_files/`

**Reason:** Old test files, functionality replaced or integrated

## What Stays (Active Codebase)

### Core Application
- `api.py` - FastAPI backend (NEW)
- `evaluation.py` - Core evaluation engine
- `run_evaluation.py` - CLI evaluation tool
- `config.py` - Central configuration
- `frontend/` - React UI (NEW)

### Utilities
- `utils/quirk_analyzer.py` - Quirk detection (+ new phrase extraction)
- `utils/prompt_analyzer.py` - Prompt decomposition
- `utils/question_asking_analyzer.py` - Question-asking metrics
- `utils/quirk_dimensions.py` - Dimension grouping (used by quirk_analyzer)
- `utils/interaction_analysis.py` - Section interaction analysis
- `utils/rate_limiter.py` - API rate limiting
- `utils/latteries/` - LLM calling framework

### Data & Logs
- `cached_results/` - Results cache and LLM cache
- `evaluation_history/` - Timestamped evaluation backups
- `logs/` - Application logs
- `results/` - Quirk analysis results

### Documentation
- `README.md` - Main README (UPDATED)
- `REACT_SETUP.md` - React setup guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `PROJECT_STRUCTURE.md` - File organization (NEW)
- `CLAUDE.md` - Claude Code instructions
- `PERFORMANCE_ANALYSIS.md` - Performance metrics

### Config & Support Files
- `requirements.txt` - Python dependencies
- `.env` - API keys (gitignored)
- `start.sh` - Quick start script
- `ambiguous_test_queries.py` - Optional query set

## Directory Structure (After Cleanup)

```
system_prompt_evaluation/
├── api.py                      ← NEW: FastAPI backend
├── evaluation.py
├── run_evaluation.py
├── config.py
├── requirements.txt
├── .env
├── start.sh                    ← NEW: Quick start
│
├── frontend/                   ← NEW: React UI
│   ├── pages/
│   ├── components/
│   ├── lib/
│   └── package.json
│
├── utils/
│   ├── quirk_analyzer.py       ← Modified: +phrase extraction
│   ├── prompt_analyzer.py
│   ├── question_asking_analyzer.py
│   ├── quirk_dimensions.py
│   ├── interaction_analysis.py
│   ├── rate_limiter.py
│   └── latteries/
│
├── cached_results/
├── evaluation_history/
├── logs/
├── results/
│
├── deprecated/                 ← NEW: Archived code
│   ├── streamlit/             ← Old UI
│   ├── analysis_scripts/      ← Research tools
│   ├── test_files/            ← Old tests
│   └── README.md
│
├── archived_features/          ← Already existed
│
├── README.md                   ← UPDATED
├── REACT_SETUP.md              ← NEW
├── IMPLEMENTATION_SUMMARY.md   ← NEW
├── PROJECT_STRUCTURE.md        ← NEW
├── CLEANUP_SUMMARY.md          ← NEW (this file)
├── CLAUDE.md
├── PERFORMANCE_ANALYSIS.md
├── FIGMA_SPEC.md
├── V0_PROMPT.md
└── ui_mockup.html
```

## File Count

**Before cleanup:**
- 40+ Python files in root/utils
- Mixed old/new code
- Unclear what to use

**After cleanup:**
- ~15 active Python files
- Clear separation (active vs deprecated)
- Obvious entry points

## Migration Path

### For Users

**Old way (Streamlit):**
```bash
streamlit run app.py  # DEPRECATED
```

**New way (React):**
```bash
./start.sh  # or manually start api.py + npm run dev
```

### For Developers

**What to edit:**
- Backend: `api.py`, `utils/*.py`
- Frontend: `frontend/pages/*.tsx`, `frontend/components/*.tsx`
- Config: `config.py`

**What NOT to edit:**
- `deprecated/*` - Archived, read-only
- `archived_features/*` - Already archived

## Benefits of Cleanup

1. **Clearer structure** - Obvious what's active vs deprecated
2. **Easier onboarding** - New users see only relevant files
3. **Faster navigation** - Less clutter in root directory
4. **Preserved history** - Old code still accessible in `deprecated/`
5. **Better docs** - Updated README points to React UI

## Rollback Plan

If needed, restore Streamlit:
```bash
cp deprecated/streamlit/app.py .
cp deprecated/streamlit/ui_helpers.py utils/
streamlit run app.py
```

But React UI is recommended! 🚀

## Next Steps

1. ✅ Cleanup complete
2. ✅ Documentation updated
3. ✅ README points to React UI
4. 🔄 Test full workflow with React UI
5. 📦 Optional: Create GitHub release (v2.0)

## Questions?

- **"Where's app.py?"** → `deprecated/streamlit/app.py`
- **"How do I run the app now?"** → `./start.sh` or see README.md
- **"Can I still use Streamlit?"** → Yes, from `deprecated/streamlit/`
- **"What happened to analysis scripts?"** → `deprecated/analysis_scripts/`
