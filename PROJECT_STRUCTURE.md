# Project Structure

Clean, organized codebase for the Quirk Analysis system.

## Core Application Files

```
.
├── api.py                      # FastAPI backend (HTTP wrapper)
├── evaluation.py               # Core evaluation engine
├── run_evaluation.py           # CLI evaluation tool
├── config.py                   # Central configuration
├── requirements.txt            # Python dependencies
├── .env                        # API keys (gitignored)
├── start.sh                    # Quick start script
│
├── frontend/                   # React UI (Next.js)
│   ├── pages/
│   │   ├── index.tsx          # Screen 1: Prompt decomposer
│   │   ├── configure.tsx       # Screen 2: Configuration
│   │   └── results.tsx         # Screen 3: Results showcase
│   ├── components/            # React components
│   ├── lib/                   # API client & types
│   └── package.json
│
└── utils/                      # Python utilities
    ├── quirk_analyzer.py       # Quirk detection & leave-one-out
    ├── prompt_analyzer.py      # Prompt decomposition
    ├── question_asking_analyzer.py  # Question-asking metrics
    ├── quirk_dimensions.py     # Dimension grouping
    ├── interaction_analysis.py # Section interaction analysis
    ├── rate_limiter.py         # API rate limiting
    └── latteries/              # LLM calling framework
        └── caller.py
```

## Data & Results

```
cached_results/
├── batch_evaluation.csv        # Main results cache
├── full_evaluation_backup.csv  # Default sections backup
└── llm_cache/                  # Latteries API cache

evaluation_history/             # Timestamped backups

logs/
├── app.log                     # UI logs
├── evaluation.log              # Evaluation logs
└── api_calls.log              # API request/response logs

results/
├── quirk_analysis_results.csv  # Latest quirk analysis
└── quirk_analysis_history/     # Timestamped quirk analyses
```

## Documentation

```
README.md                       # Main project README
REACT_SETUP.md                  # React UI setup guide
IMPLEMENTATION_SUMMARY.md       # Technical implementation details
CLAUDE.md                       # Claude Code instructions
PERFORMANCE_ANALYSIS.md         # Performance metrics
PROJECT_STRUCTURE.md            # This file
```

## Deprecated Code

```
deprecated/
├── streamlit/                  # Old Streamlit UI
│   ├── app.py                 # Replaced by React frontend
│   └── ui_helpers.py          # Streamlit chart helpers
├── analysis_scripts/           # Exploratory analysis scripts
│   └── [various .py files]    # Research/exploration only
├── test_files/                 # Old test files
└── README.md                   # Deprecation notes
```

## Other Files

```
archived_features/              # Previously archived code
ambiguous_test_queries.py       # Optional ambiguous query set
FIGMA_SPEC.md                   # UI design specification
V0_PROMPT.md                    # v0.dev prompt (not used)
ui_mockup.html                  # HTML mockup (reference)
```

## What to Use

### For Web UI
- Start: `./start.sh` or manually start `api.py` + `npm run dev`
- Access: http://localhost:3000

### For CLI Evaluation
- Run: `python run_evaluation.py`
- Configure: Edit test queries and sections in the script

### For Development
- Backend: Edit `api.py`, `utils/*.py`
- Frontend: Edit `frontend/pages/*.tsx`, `frontend/components/*.tsx`
- Config: Edit `config.py`

## What NOT to Use

- ❌ `deprecated/streamlit/app.py` - Replaced by React UI
- ❌ `deprecated/analysis_scripts/*` - Not part of core system
- ❌ `FIGMA_SPEC.md` / `V0_PROMPT.md` - Design docs, not code

## File Count Summary

- **Core system**: ~15 Python files + React frontend
- **Utils**: ~8 utility modules
- **Deprecated**: ~25 old files (archived)
- **Documentation**: ~8 markdown files
