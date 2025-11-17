# Analysis Scripts

This folder contains specialized analysis scripts for exploring evaluation data.

## Scripts

### Core Analysis
- **`dimension_specific_analysis.py`** - Analyzes each dimension separately (no averaging)
- **`detect_dimension_warfare.py`** - Detects zero-sum tradeoffs between dimensions
- **`analyze_interactions.py`** - Tests section additivity and synergy

### Behavioral Analysis
- **`quirk_detection.py`** - Detects emergent linguistic behaviors (hedging, examples, etc.)
- **`analyze_quirk_examples.py`** - Deep dive into quirk examples with side-by-side comparisons
- **`visualize_quirks.py`** - Creates visualizations for detected quirks

### Performance Analysis
- **`quick_analyses.py`** - Runs baseline vs combinations, best configs, section count effects
- **`length_and_antagonism.py`** - Response length patterns and section antagonism
- **`check_correlations.py`** - Quick correlation matrix check
- **`visualize_findings.py`** - Creates comprehensive visualizations

## Usage

All scripts read from `cached_results/batch_evaluation.csv` by default.

Example:
```bash
python analysis/quirk_detection.py
python analysis/dimension_specific_analysis.py
```

Results are saved to:
- Images → `images/` folder
- CSV results → `results/` folder
