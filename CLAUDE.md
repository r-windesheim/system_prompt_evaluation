# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI system prompt testing framework that systematically evaluates which sections of system prompts drive specific AI behaviors. The tool:
- Decomposes prompts into testable sections
- Evaluates all combinations against diverse test queries
- Measures 6 behavioral dimensions + question-asking behavior
- Provides interactive analysis through a Streamlit web interface
- Analyzes section interactions and synergies

## Quick Start Commands

### Setup
```bash
pip install -r requirements.txt
echo "OPENROUTER_API_KEY=your_key_here" > .env
```

### Running the Application
```bash
# Launch web interface (main usage)
streamlit run app.py

# Run batch evaluation (command line)
python run_evaluation.py

# Test prompt analyzer
python utils/prompt_analyzer.py
```

## Core Architecture

### Data Flow Pipeline
1. **Prompt Decomposition**: System prompts → `List[str]` sections via GPT-4o analysis
2. **Combination Generation**: All 2^n - 1 combinations using `itertools.combinations`
3. **Batch Evaluation**: Async API calls via Latteries framework
4. **Multi-dimensional Scoring**: Each response evaluated across 6+ criteria
5. **Caching**: Results saved to CSV with automatic backups
6. **Interactive Analysis**: Streamlit UI with real-time filtering and visualizations

### Critical Architecture Details

**Efficient Evaluation Strategy** (evaluation.py:318-394)
- **NEW approach**: Generate ONE response per prompt-query combination, then evaluate that SAME response across all dimensions
- **OLD approach wasted ~83%** of API calls by generating separate responses for each dimension
- Each `evaluate_prompt_query_combination()` returns results for ALL evaluation dimensions
- Reduces API calls from 2N to N+1 per combination (N = number of dimensions)

**Latteries Integration** (utils/latteries/caller.py)
- Advanced LLM calling framework with OpenAI-compatible interface
- **Built-in caching**: All responses cached to `cached_results/llm_cache/`
- **Request deduplication**: Identical prompts return cached results instantly
- **Multi-provider support**: OpenAI, Anthropic, OpenRouter, custom endpoints
- **Retry logic**: Automatic retries with exponential backoff
- **Async-first**: Full asyncio support with semaphore-based rate limiting
- Compatibility wrapper at line 1260: `llm_call()` function preserves legacy interface

**Configuration Centralization** (config.py)
- All constants, magic numbers, and configurations in one file
- Model names: `DEFAULT_MODEL`, `FALLBACK_MODEL`
- Concurrency: `DEFAULT_MAX_CONCURRENT = 100` (high throughput via nest_asyncio)
- File paths: `BATCH_EVALUATION_FILE`, `EVALUATION_HISTORY_DIR`, etc.
- Evaluation dimensions: `EVALUATION_DIMENSIONS` (6 standard metrics)
- Scoring constants: `SCORE_YES = 100`, `SCORE_NO = 0`, etc.
- UI colors and styling: `COLOR_PRIMARY`, `RATING_GRADIENTS`, etc.
- Helper functions: `calculate_evaluation_cost()`, `get_rating_from_score()`

**Custom Prompt Analyzer** (utils/prompt_analyzer.py)
- Uses GPT-4o for intelligent prompt decomposition
- Two modes:
  - `exclude_factual=True`: Extract only behavioral instructions
  - `exclude_factual=False`: Decompose ALL content into sections
- Returns **exact original text** without paraphrasing
- Typical output: 4-10 logical sections per prompt

**Async Processing & Concurrency** (evaluation.py:76-81, app.py:39-40)
- **nest_asyncio** fix (app.py:40): Allows nested event loops, prevents anyio deadlocks
- Asyncio with semaphore: `asyncio.Semaphore(DEFAULT_MAX_CONCURRENT)` controls concurrency
- Default: 100 concurrent requests (increased from 50 after fixing nested loop issues)
- All API calls via `utils/latteries/caller.py` with automatic caching
- Comprehensive logging to `logs/evaluation.log` and `logs/api_calls.log`

**Evaluation Backup System** (evaluation.py:118-137)
- Every evaluation run creates timestamped backup in `evaluation_history/`
- Format: `{run_type}_{timestamp}.csv`
- Main cache: `cached_results/batch_evaluation.csv`
- Default sections backup: `cached_results/full_evaluation_backup.csv`
- Automatic on every `run_batch_evaluation()` call

### File Responsibilities

**app.py** (1068 lines)
- Streamlit web interface with dark theme
- **Two modes**:
  - "Toggleable Sections": Pre-built or custom sections with checkboxes
  - "Custom Prompt Analyzer": Paste prompt → analyze → evaluate
- Real-time dataset switching between default and custom evaluations
- **Visualizations**:
  - Radar and bar charts (plotly)
  - Section Impact Heatmap (shows which sections affect which metrics)
  - Question-asking behavior charts
  - Response metrics: word count, readability (Flesch), grade level
- In-app evaluation runner with progress tracking (lines 936-1064)
- Config name display: Shows which prompt combination is selected (lines 457-471)

**evaluation.py** (533 lines)
- `PromptEvaluator` class: Core evaluation engine
- `generate_prompt_combinations()`: Creates all 2^n - 1 section combinations
- `evaluate_prompt_query_combination()`: **NEW EFFICIENT** - evaluates one prompt-query pair across all dimensions (lines 318-394)
- `run_batch_evaluation()`: Orchestrates full batch with async/await and semaphore
- `create_evaluation_backup()`: Timestamped backup creation (lines 118-137)
- `calculate_response_metrics()`: Text analysis including question-asking behavior (lines 37-60)
- Metadata tracking: section_indices, section_names, config_name (lines 425-439)

**run_evaluation.py** (331 lines)
- Interactive CLI for configurable evaluations
- **50+ diverse test queries** including edge cases and challenging scenarios (lines 36-91)
- Two evaluation modes:
  - Y/N questions (fast, binary scoring)
  - 0-100 scoring (detailed, granular)
- **Query set selection**: Standard queries vs. Ambiguous queries (if available)
- Cost estimation before running (lines 256-264)
- Default sections for testing (6 sections covering identity, directness, critical thinking, uncertainty, examples, encouragement) (lines 26-33)
- Metadata tracking with section_names dict (lines 283-291)

**config.py** (264 lines)
- **Centralized configuration** for entire project
- Model configuration: `DEFAULT_MODEL = "openai/gpt-5-nano-2025-08-07"`
- Concurrency: `DEFAULT_MAX_CONCURRENT = 100`
- File paths: All cache and log file locations
- Evaluation dimensions: `EVALUATION_DIMENSIONS` list (6 metrics)
- Dimension keyword mappings: `DIMENSION_KEYWORDS` for parsing
- Default prompt sections: `DEFAULT_PROMPT_SECTIONS` (6 pre-built sections)
- UI configuration: Colors, query count options, rating thresholds
- Helper functions: Cost calculation, rating conversions, styling
- Ambiguous queries flag: `HAS_AMBIGUOUS_QUERIES` (auto-detected)

**utils/llm_call.py** (95 lines - DEPRECATED)
- **DEPRECATED**: Basic httpx-based API wrapper
- **Replaced by Latteries**: `utils/latteries/caller.py` now handles all LLM calls
- Kept for reference only - new code should use Latteries

**utils/latteries/caller.py** (1340+ lines)
- **Primary LLM calling framework** with advanced features
- `OpenAICaller`: Main caller class with OpenRouter support
- `llm_call()` wrapper (lines 1260-1340): Compatibility function for evaluation code
- Built-in caching via `APIRequestCache` and `CallerCache` classes
- Request deduplication and automatic retries
- Multiple provider support: OpenAI, Anthropic, custom endpoints
- Async-first with proper timeout handling (300s per-request, 10min total for quirk analysis)
- Global caller instance initialized lazily (line 1257)
- **Empty response handling** (NEW): 3-attempt retry with exponential backoff (1s, 2s, 4s)
- **Content filter detection**: Checks `response.hit_content_filter` before retrying

**utils/prompt_analyzer.py** (206 lines)
- `decompose_system_prompt()`: LLM-powered prompt analysis via GPT-4o (lines 13-129)
- `validate_sections()`: Quality check for decomposed sections (lines 131-179)
- `exclude_factual` parameter controls extraction mode:
  - `True`: Only behavioral instructions ("Be direct", "Think critically")
  - `False`: All content (facts, context, instructions, everything)
- Returns exact original text - no paraphrasing
- Format: Numbered list of sections

**utils/ui_helpers.py** (553 lines)
- Chart creation helpers for Streamlit
- `extract_dimension_scores()`: Parse evaluation results into scores (lines 15-56)
- `create_radar_chart()`: Multi-series radar with baseline comparison (lines 59-114)
- `create_bar_chart()`: Grouped bar chart for dimensions (lines 117-161)
- `create_response_metrics_charts()`: Word count + readability scatter (lines 164-262)
- `extract_question_asking_metrics()`: Question-asking behavior stats (lines 294-339)
- `create_question_asking_chart()`: Bar chart for asking vs. assuming (lines 342-404)
- `create_section_impact_heatmap()`: **NEW** - Shows which sections affect which metrics (lines 473-552)
- `calculate_section_impact()`: Calculates differential impact of each section (lines 407-470)

**utils/question_asking_analyzer.py** (238 lines)
- **NEW feature**: Analyzes if AI asks questions vs. makes assumptions
- `analyze_question_asking()`: Main analysis function (lines 57-153)
- Detects:
  - Question marks
  - Clarification phrases ("could you clarify", "what do you mean")
  - Assumption phrases ("I'll assume", "presumably")
  - Question sentences
- Returns:
  - `asks_vs_assumes`: "asks", "assumes", or "neutral"
  - `question_asking_score`: 0-100 (higher = more questioning)
  - Detailed counts and detected phrases
- Integrated into `calculate_response_metrics()` in evaluation.py

**utils/interaction_analysis.py** (321 lines)
- **NEW feature**: Analyzes how prompt sections interact
- `check_data_quality()`: Validates data for interaction analysis (lines 14-74)
- `find_winning_configs()`: Identifies top/bottom performing combinations (lines 77-123)
- `calculate_additivity_check()`: Tests if effects are linear or interactive (lines 126-200)
- `calculate_interaction_matrix()`: Pairwise interaction effects (lines 215-288)
- `get_strongest_interactions()`: Extract top synergies/interferences (lines 291-321)
- Requires config_name metadata from evaluations

**utils/quirk_analyzer.py** (568 lines)
- **Real-time behavioral quirk detection** via leave-one-out testing
- `detect_quirks()`: Regex-based detection of 20+ linguistic patterns (lines 40-141)
- `analyze_prompt_quirks()`: Main analysis - tests full prompt + N leave-one-out variants (lines 275-460)
- `is_xml_tag_section()`: **NEW** - Detects XML-only sections to skip (lines 236-268)
- **Quirk types detected**:
  - Parentheses, apologies, questions, enumeration, hedging, certainty
  - Metacommentary, acknowledgments, examples, action items, caveats
  - Pronoun density (1st/2nd/3rd person), conditional language, modals
  - Formality score, contractions, sentiment (via TextBlob if available)
- **Leave-one-out methodology**:
  - Generate N responses with full prompt (baseline)
  - Generate N responses WITHOUT each section (N configs)
  - Compare quirk rates: impact = full_rate - without_rate
  - Identifies which section CAUSES which quirk
- **XML section handling** (NEW - lines 307-323):
  - Auto-detects sections >70% XML tags
  - Skips them to prevent broken prompts
  - Tracks skipped sections in results metadata
- **Failure tracking** (NEW - lines 347-355, 387-395):
  - Detects configs with 0 valid responses
  - Excludes failed configs from impact calculation
  - Returns `failed_configs` and `xml_only_sections` lists
- **Output format**:
  - Returns dict with `detected_quirks`, `all_quirk_rates`, `failed_configs`
  - Each quirk includes: section attribution, examples, spike ratio, impact
  - CSV export with timestamped backups to `results/quirk_analysis_history/`
- **Cost**: ~$0.004 for quick scan (30 responses), ~$0.028 for full attribution (35 sections)

## Evaluation Dimensions

Six standard evaluation criteria (run_evaluation.py:94-175, config.py:73-80):

1. **Helpfulness**: Actionable, comprehensive information (0-100)
2. **Directness**: Concise without fluff (0-100)
3. **Critical Thinking**: Nuanced analysis, multiple perspectives (0-100)
4. **Accuracy**: Factual correctness (0-100)
5. **Tone Appropriateness**: Context-appropriate communication (0-100)
6. **Safety & Ethics**: Responsible guidance (0-100)

Plus **Question-Asking Behavior** (analyzed separately):
- Score 0-100 measuring tendency to ask clarifying questions
- Categories: "asks", "assumes", "neutral"
- Metrics: question marks, clarification phrases, assumption phrases

## Key Implementation Notes

### Cost Management
- Use `openai/gpt-5-nano-2025-08-07` for evaluations (~$0.002 per assessment)
- Default concurrency: 100 requests (balances speed and API limits)
- Y/N questions are faster/cheaper than 0-100 scoring
- Full evaluation of 6 sections × 50 queries × 6 dimensions ≈ $4
- Latteries caching eliminates duplicate API costs

### Dataset Switching (app.py:246-271)
- `use_original_dataset=True` → loads `cached_results/full_evaluation_backup.csv` (default sections)
- `use_original_dataset=False` → loads `cached_results/batch_evaluation.csv` (custom evaluations)
- UI detects custom results by comparing file sizes and unique prompt counts
- Toggle button switches between default and custom sections (lines 424-431)

### Session State Management (app.py)
- `st.session_state.custom_sections`: Stores analyzed custom sections
- `st.session_state.use_default_sections`: Toggles between default and custom
- `st.session_state.evaluation_complete`: Prevents evaluation re-runs
- `st.session_state.interface_mode`: "Toggleable Sections" or "Custom Prompt Analyzer"
- `st.session_state.show_eval_config`: Shows/hides evaluation config modal

### Response Metrics (evaluation.py:37-60)
- Uses `textstat` library for readability analysis
- Flesch Reading Ease (0-100, higher = easier)
- Flesch-Kincaid Grade Level
- Word count, character count, sentence count
- **NEW**: Question-asking metrics integrated via `analyze_question_asking()`

### Metadata Tracking (evaluation.py:425-439)
- `section_indices`: Comma-separated indices (e.g., "0,2,4")
- `section_names`: Comma-separated names if provided
- `config_name`: Human-readable config (e.g., "1+3+5" for sections 1, 3, and 5)
- Enables config-based filtering and interaction analysis
- Passed through entire evaluation pipeline

## Gotchas and Important Details

1. **Manual Refresh Required**: After running in-app evaluation, user must refresh browser (F5) to see new results due to Streamlit caching (app.py:1051)

2. **Evaluation Prevents Restarts**: `evaluation_complete` flag prevents accidental re-runs; must explicitly clear it (app.py:915-918)

3. **Backup Files Not Auto-Loaded**: `evaluation_history/` backups are for recovery only; UI only reads from `cached_results/`

4. **Y/N Score Conversion**: Y/N answers converted to 100/0 scores for consistent charting (evaluation.py:149-158)

5. **Section Text Matching**: UI filters by exact system_prompt text matching; whitespace differences break the match (app.py:609)

6. **nest_asyncio Required**: App uses `nest_asyncio.apply()` (line 40) to allow nested event loops - **do not remove** or asyncio will deadlock

7. **Latteries Caching**: All LLM calls are cached to `cached_results/llm_cache/`. Delete this directory to force re-evaluation (expensive!)

8. **Config Name Format**: Config names use 1-indexed section numbers (e.g., "1+3+5" means sections 0, 2, 4 in the list) (evaluation.py:434)

9. **Ambiguous Queries Optional**: If `ambiguous_test_queries.py` exists, adds second query set for question-asking behavior testing (config.py:112-117)

10. **High Concurrency Safe**: 100+ concurrent requests now safe due to nest_asyncio fix; was limited to 50 before (config.py:29)

11. **Interaction Analysis Requires Metadata**: Section interaction features only work with evaluations that include config_name metadata (utils/interaction_analysis.py:24-29)

12. **Quirk Analysis CSV Format**: Quirk results saved to `results/quirk_analysis_results.csv` with backups in `results/quirk_analysis_history/`. Each row = one quirk with attribution, examples, and impact metrics

13. **XML Sections Auto-Skipped**: Quirk analyzer automatically detects and skips XML-only sections (>70% XML tags) to prevent broken prompts during leave-one-out testing

14. **Quirk Example Bug (FIXED)**: Earlier versions had identical examples in both columns. Run new analysis after latest update to see proper WITH/WITHOUT comparisons

## New Features (Since Original Version)

### Latteries Integration
- **Professional LLM calling framework** replaces basic httpx implementation
- Built-in caching eliminates duplicate API costs
- Multi-provider support (OpenAI, Anthropic, OpenRouter)
- Automatic retries with exponential backoff
- Request deduplication across entire project

### Configuration Centralization
- **All magic numbers moved to config.py**
- Single source of truth for constants
- Easy to adjust concurrency, models, colors, etc.
- Helper functions for common calculations

### Question-Asking Behavior Analysis
- **New dimension**: Measures if AI asks questions vs. makes assumptions
- Integrated into all evaluations automatically
- Separate charts in UI showing asking vs. assuming behavior
- Supports ambiguous query set for targeted testing

### Section Interaction Analysis
- **Detect synergies**: When sections work better together
- **Detect interference**: When sections conflict
- Additivity checks: Test if effects are linear or interactive
- Interaction matrix: Pairwise effects between all sections
- Winning config analysis: What combinations perform best

### Metadata Tracking
- **Config names**: Human-readable identifiers like "1+3+5"
- Section indices and names preserved throughout pipeline
- Enables filtering, grouping, and interaction analysis
- Displayed in UI for easy reference

### Section Impact Heatmap
- **Visual analysis**: Which sections affect which metrics
- Color-coded: Green = positive impact, Red = negative impact
- Calculates differential (with section vs. without section)
- Integrated into main UI as chart option

### Performance Improvements
- **83% reduction in API calls** via single-response evaluation
- **100 concurrent requests** via nest_asyncio fix (was 50)
- Latteries caching eliminates all duplicate requests
- Semaphore-based rate limiting prevents API throttling

### UI Enhancements
- Two-mode interface: Toggleable Sections + Custom Analyzer
- Config name display and filtering
- Section impact heatmap visualization
- Question-asking behavior charts
- Dynamic dataset switching (default vs. custom)
- Progress tracking for in-app evaluations

### Behavioral Quirk Analysis (RECENTLY FIXED)
- **Real-time quirk detection**: Identify emergent linguistic patterns in AI responses
- **Leave-one-out testing**: Generate responses with/without each section to determine causality
- **20+ quirk types**: Parentheses, hedging, formality, pronoun density, etc.
- **Recent bug fixes** (Oct 2024):
  - **XML section handling**: Auto-detects and skips XML-only sections (e.g., `</tag> <tag>`) that would break prompt structure
  - **Baseline tracking**: Detects failed configurations (0 valid responses) and excludes from impact calculation
  - **Example comparison**: Fixed bug where both examples were identical - now shows proper WITH/WITHOUT comparison
  - **UI warnings**: Shows alerts when baseline=0 or suspiciously low, indicating possible data issues
- **How it works**:
  1. Generate 30 responses with full prompt
  2. Generate 30 responses WITHOUT each section (leave-one-out)
  3. Detect quirks in all responses (regex patterns)
  4. Calculate impact: `with_section_rate - without_section_rate`
  5. Identify which section CAUSES which quirk
- **Output**: CSV with quirk attribution, spike ratios, examples, and section text
- **Cost**: ~$0.004 for 30 responses, ~$0.028 for full 35-section analysis
- **Access**: Custom Prompt Analyzer mode → "🔍 Analyze Behavioral Quirks" button

## Testing Queries

The tool includes 50+ carefully designed test queries (run_evaluation.py:36-91):
- **Challenging scenarios**: Testing assumptions, uncertainty handling
- **Edge cases**: Impossible requests, ambiguous questions, ethical dilemmas
- **Diverse topics**: Programming, personal advice, controversial topics
- **Deliberately difficult**: Designed to reveal prompt behavior differences

Optional **Ambiguous queries** (ambiguous_test_queries.py):
- 30 intentionally vague questions
- Tests question-asking vs. assumption-making behavior
- Examples: "Can you help with Python?", "Tell me about the issue"

## Development Workflow

### Adding New Evaluation Dimensions
1. Add dimension name to `EVALUATION_DIMENSIONS` in config.py
2. Add keyword mappings to `DIMENSION_KEYWORDS` in config.py
3. Add evaluation question to `detailed_evaluation_questions` or `yn_evaluation_questions` in run_evaluation.py
4. UI will automatically display new dimension in charts

### Adding New Query Sets
1. Create new file like `ambiguous_test_queries.py`
2. Define `QUERY_SET_NAME = [list, of, queries]`
3. Add import and detection logic to config.py
4. Add selection option to run_evaluation.py and app.py

### Customizing Models
1. Update `DEFAULT_MODEL` in config.py
2. Ensure model is OpenAI-compatible via OpenRouter
3. Adjust `calculate_evaluation_cost()` if pricing differs
4. Test with small batch first

### Debugging API Issues
1. Check `logs/api_calls.log` for request/response details
2. Check `logs/evaluation.log` for evaluation-level errors
3. Check `logs/app.log` for UI-related issues
4. Latteries cache in `cached_results/llm_cache/` preserves all successful calls

### Running Partial Evaluations
1. Modify test_queries slice in run_evaluation.py (line 248)
2. Or use fewer sections for faster iteration
3. Results still saved to main cache file
4. Consider using Y/N questions for speed

## File Structure

```
├── app.py                          # Main Streamlit UI
├── evaluation.py                   # Core evaluation engine
├── run_evaluation.py               # CLI evaluation runner
├── config.py                       # Centralized configuration
├── requirements.txt                # Python dependencies
├── .env                            # API keys (gitignored)
├── cached_results/
│   ├── batch_evaluation.csv        # Main results cache
│   ├── full_evaluation_backup.csv  # Default sections backup
│   └── llm_cache/                  # Latteries API cache
├── evaluation_history/             # Timestamped backups
├── logs/
│   ├── app.log                     # UI logs
│   ├── evaluation.log              # Evaluation logs
│   └── api_calls.log               # API request/response logs
└── utils/
    ├── llm_call.py                 # DEPRECATED - old API wrapper
    ├── prompt_analyzer.py          # Prompt decomposition
    ├── ui_helpers.py               # Chart creation
    ├── question_asking_analyzer.py # Question-asking analysis
    ├── interaction_analysis.py     # Section interaction analysis
    └── latteries/
        └── caller.py               # Main LLM calling framework
```

## Common Tasks

### Run Full Evaluation
```bash
python run_evaluation.py
# Select: 2 (0-100 scoring), 1 (standard queries), 50 (all queries)
```

### Test Custom Prompt
1. Open `streamlit run app.py`
2. Click "Custom Analyzer" mode
3. Paste prompt → "Analyze Prompt"
4. Review sections → "Run Evaluation"
5. Wait for completion → Refresh browser (F5)

### Compare Prompt Variations
1. Run evaluation with first prompt (save as custom)
2. Toggle "Use Default" to see baseline
3. Charts show comparison automatically

### Debug Failed Evaluations
```bash
# Check logs
tail -f logs/evaluation.log

# Retry failed calls (if retry script exists)
python retry_failed_evaluations.py

# Clear cache to force re-run
rm -rf cached_results/llm_cache/*
```

### Export Results
```bash
# Results are already in CSV format
cp cached_results/batch_evaluation.csv my_results_$(date +%Y%m%d).csv

# Backups are timestamped automatically
ls evaluation_history/
```

### Run Quirk Analysis
1. Open `streamlit run app.py`
2. Click "Custom Analyzer" mode
3. Paste prompt → "Analyze Prompt"
4. Click "🔍 Analyze Behavioral Quirks"
5. Enter test query (or use default: photosynthesis)
6. Click "Start Analysis"
7. Wait 5-20 minutes (30 responses × 35 configs)
8. Results appear below with attribution and examples

**Quirk Analysis Output**:
- Shows which section causes which quirk
- Impact scores: baseline → with_section (+change)
- Example comparison: WITH quirk vs. WITHOUT quirk
- Warnings if baseline=0 or suspicious
- Saved to `results/quirk_analysis_results.csv`

**Previous Results**:
```bash
# View all quirk analysis runs
ls -lh results/quirk_analysis_history/

# View specific run
cat results/quirk_analysis_history/quirk_analysis_TIMESTAMP.csv
```

## Performance Considerations

- **Concurrency**: 100 simultaneous requests (adjustable in config.py)
- **Caching**: Latteries eliminates duplicate API costs
- **API calls per evaluation**: N_combinations × N_queries × (1 + N_dimensions)
- **Time per evaluation**: ~30-60 seconds for 6 sections, 10 queries, 100 concurrency
- **Cost per evaluation**: ~$0.50-$5 depending on size (cached calls = free)
- **Cache size**: Can grow to 100s of MB - periodically clean `llm_cache/`

## Troubleshooting

### "Evaluation stuck at X%"
- Check `logs/evaluation.log` for errors
- API rate limits may slow progress
- Consider reducing concurrency in config.py

### "No data for this combination"
- Prompt text doesn't match exactly (whitespace matters)
- Try running evaluation with current sections
- Check `batch_evaluation.csv` for available prompts

### "anyio deadlock" or "asyncio error"
- Ensure `nest_asyncio.apply()` is called (app.py:40)
- Do not remove nest_asyncio import

### "Empty response from API"
- **Auto-retried**: System now retries empty responses 3 times with exponential backoff (1s, 2s, 4s)
- **Content filter**: If response hits content filter, error thrown immediately (no retry)
- **Persistent failures**: Check OPENROUTER_API_KEY in .env
- **Model issues**: Check model availability on OpenRouter
- **Debug logs**: Review `logs/api_calls.log` for detailed error information
- **Recent fix** (Oct 2024): Added retry logic to `llm_call()` in caller.py:1302-1340
- Warning message shows retry attempts: "Warning: Empty response from API (attempt 1/3), retrying in 1s..."

### Charts not updating after evaluation
- Streamlit caching: Must refresh browser (F5)
- Clear Streamlit cache: Click "C" in app, then "Clear cache"
- Check if evaluation actually saved to CSV

### Quirk analysis shows baseline=0 or identical examples
- **baseline=0**: Indicates configuration failed (likely XML structure broken)
  - Solution: Update to latest code - XML sections now auto-skipped
  - Warning will appear in UI: "⚠️ Baseline may be unreliable"
- **Identical examples**: Bug in older versions
  - Solution: Re-run quirk analysis with updated code
  - New runs will show proper WITH/WITHOUT comparison
- **Check results file**: `results/quirk_analysis_results.csv`
- **View backups**: `results/quirk_analysis_history/` for previous runs

## Best Practices

1. **Start small**: Test with 5-10 queries before full evaluation
2. **Use Y/N mode**: Faster and cheaper for initial exploration
3. **Monitor logs**: Tail logs in separate terminal during runs
4. **Backup results**: Copy important evaluations from batch_evaluation.csv
5. **Clean cache**: Periodically delete old llm_cache files to save space
6. **Test sections**: Verify decomposition quality before running full evaluation
7. **Use metadata**: Always run evaluations with metadata for interaction analysis
8. **Compare carefully**: Ensure exact section text matches when comparing results
9. **Quirk analysis**: Use simple queries like "Explain X" to see clearest quirk patterns
10. **Check baselines**: Always verify `without_section` > 0 before trusting impact scores
11. **Review examples**: Actual response examples more informative than numeric scores
12. **XML prompts**: Latest code auto-skips XML sections - update if seeing baseline=0 issues
