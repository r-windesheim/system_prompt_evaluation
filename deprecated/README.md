# Deprecated Code

This directory contains code that has been replaced or is no longer actively used.

## Structure

### `streamlit/`
Old Streamlit-based UI (replaced by React frontend in `/frontend`)
- `app.py` - Main Streamlit application
- `ui_helpers.py` - Streamlit chart/visualization helpers

**Replaced by:** React UI (`/frontend`) + FastAPI (`/api.py`)

### `analysis_scripts/`
Standalone exploratory analysis scripts (not part of core system)
- Various scripts for analyzing quirk data
- Not imported by core system, just for research/exploration

### `test_files/`
Old test files and experimental code

## Active Codebase

See `/REACT_SETUP.md` for current architecture.

**Core files:**
- `/api.py` - FastAPI backend
- `/evaluation.py` - Core evaluation logic
- `/run_evaluation.py` - CLI evaluation tool
- `/config.py` - Central configuration
- `/frontend/` - React UI
- `/utils/quirk_analyzer.py` - Quirk detection
- `/utils/prompt_analyzer.py` - Prompt decomposition
