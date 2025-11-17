# Behavioral Quirk Detection System

A two-phase approach to detecting emergent AI behaviors not specified in prompts.

## Overview

**Phase 1** (Fast & Free): Pattern-based detection using regex and NLP libraries
**Phase 2** (Expensive & Powerful): LLM-based semantic analysis using latteries

---

## Phase 1: Pattern-Based Detection

**Script**: `quirk_detection.py`

### Phase 1a: Regex-Based Quirks (11 patterns)

Fast pattern matching for linguistic quirks:

1. **Parenthetical Obsession** - Excessive use of parentheses
2. **Apologetic Loop** - "sorry", "apologize", "apologies"
3. **Question Injection** - Questions in responses
4. **Enumeration Obsession** - Bullet points and numbered lists
5. **Hedging Density** - "might", "possibly", "perhaps", "could be"
6. **Certainty Signaling** - "definitely", "absolutely", "clearly"
7. **Metacommentary** - "let me explain", "I'll structure"
8. **Acknowledgment Inflation** - "great question", "good point"
9. **Example Addiction** - "for example", "for instance", "e.g."
10. **Action-Step Addiction** - "next steps", "action items"
11. **Caveat Syndrome** - "however", "but", "although"

### Phase 1b: NLP Library-Based Quirks (8 features)

Requires `textblob` (`pip install textblob`):

12. **Sentiment Polarity** - Positive/negative tone (0-100 scale)
13. **Sentiment Subjectivity** - Objective vs subjective language
14. **Formality Score** - Word length + contraction density
15. **Contraction Rate** - "don't", "can't", "won't"
16. **First-Person Density** - "I", "me", "my", "mine"
17. **Second-Person Density** - "you", "your"
18. **Third-Person Density** - "he", "she", "they", "it"
19. **Conditional Language** - "if", "when", "unless"
20. **Modal Verb Rate** - "can", "could", "may", "might", "must"
21. **Imperative Language** - Commands like "do", "ensure", "avoid"

### Usage

```bash
# Run Phase 1 detection
cd analysis
python quirk_detection.py
```

**Output**:
- `results/quirk_detection_results.csv` - Detected quirks with spike ratios
- Console output with examples and patterns

**Cost**: Free (no API calls)
**Speed**: Fast (~1-2 seconds for 1000 responses)

---

## Phase 2: LLM-Based Detection

**Script**: `llm_quirk_detection.py`

Uses **latteries** (OpenAICaller) for semantic analysis with built-in:
- ✅ Automatic caching (avoids redundant API calls)
- ✅ Retry logic with exponential backoff
- ✅ Rate limiting
- ✅ Async batch processing

### Behavioral Dimensions (6 axes)

1. **Reasoning Style** (0-100)
   - 0 = Pure deductive (general → specific)
   - 100 = Pure inductive (examples → generalizations)

2. **Assertiveness** (0-100)
   - 0 = Tentative, heavily qualified
   - 100 = Assertive, directive, authoritative

3. **Narrative Structure** (0-100)
   - 0 = Pure logical exposition
   - 100 = Heavy storytelling, scenarios

4. **Socratic Tendency** (0-100)
   - 0 = Direct answers only
   - 100 = Primarily uses questions to guide thinking

5. **Empathy Signals** (0-100)
   - 0 = Purely analytical
   - 100 = Strong emotional attunement

6. **Prescriptiveness** (0-100)
   - 0 = Purely descriptive, presents options
   - 100 = Highly directive, "you should do X"

### Usage

```bash
# Run Phase 2 detection on all responses
cd analysis
python llm_quirk_detection.py

# Test on sample first (cheaper)
python llm_quirk_detection.py --sample 50
```

**Output**:
- `results/llm_quirk_detection_results.csv` - Config-specific patterns
- `results/llm_quirk_scores_full.csv` - All responses with dimension scores
- Console output with detected patterns

**Cost**: ~$0.002 per response × 6 dimensions = ~$0.012 per response
- Example: 1000 responses = ~$12

**Speed**: ~5-10 minutes for 1000 responses (with batching)

**Caching**: Results cached in `cached_results/llm_quirk_cache/`
- Re-running the script uses cached results (free & instant)

---

## Detection Thresholds

### Phase 1
- **Spike Ratio**: >1.5x baseline
- **Prevalence**: >50% of responses in config

Example: If average parentheses rate is 2 per 100 words, a config with 3+ triggers detection.

### Phase 2
- **Deviation**: >20 points from baseline

Example: If average assertiveness is 50/100, a config with 71+ or 29- triggers detection.

---

## Section-Level Attribution

**Script**: `section_quirk_attribution.py`

After detecting config-level quirks, this analysis answers: **"Which individual section causes each quirk?"**

### How It Works

Uses **with/without methodology**:
- Compare configs WITH section X vs configs WITHOUT section X
- Calculate impact: `mean_with - mean_without`
- Positive impact = section CAUSES quirk
- Negative impact = section REDUCES quirk

### Example Output

```
TOP QUIRK DRIVERS:
1. Section 2 → Hedging
   Impact: +1.4 points
   With Section 2: 3.2 | Without: 1.8

2. Section 5 → Examples
   Impact: +2.1 points
   With Section 5: 4.3 | Without: 2.2

SECTION QUIRK PROFILES:
📌 SECTION 2
   🔥 CAUSES these quirks:
      • Hedging                      +1.42
      • Caveats                      +0.89

   ❄️  REDUCES these quirks:
      • Certainty                    -1.12
```

### Usage

```bash
cd analysis
python section_quirk_attribution.py
```

**Output**:
- `results/section_quirk_attribution.csv` - Impact scores for all section-quirk pairs
- `images/section_quirk_attribution.png` - Heatmap visualization
- Console output with top drivers/reducers

**Cost**: Free (uses cached responses)
**Speed**: Fast (~2-3 seconds)

---

## Workflow

### Quick Analysis (Free)
```bash
# Step 1: Detect config-level quirks
python analysis/quirk_detection.py

# Step 2: Attribute quirks to individual sections
python analysis/section_quirk_attribution.py
```

### Deep Analysis (Paid)
```bash
# Test on sample first
python analysis/llm_quirk_detection.py --sample 100

# If results look good, run full analysis
python analysis/llm_quirk_detection.py
```

### Compare Results
```python
import pandas as pd

# Phase 1 results
phase1 = pd.read_csv('results/quirk_detection_results.csv')
print(phase1.groupby('quirk')['config'].count())

# Phase 2 results
phase2 = pd.read_csv('results/llm_quirk_detection_results.csv')
print(phase2.groupby('dimension')['config'].count())
```

---

## Understanding Results

### Phase 1 Example Output
```
#1 - HEDGING SYNDROME
Config: 2+3+5
Baseline rate: 1.234 per 100 words
Config rate: 2.567 per 100 words
Spike: 2.1x baseline
Prevalence: 78% of responses
```

**Interpretation**: Config "2+3+5" uses hedging language 2.1x more than average, appearing in 78% of responses.

### Phase 2 Example Output
```
1. 1+4+6 | reasoning_style
   Deductive (0) vs Inductive (100)
   Baseline: 52.3  →  Config: 78.9
   ↑ Deviation: +26.6 points
```

**Interpretation**: Config "1+4+6" strongly favors inductive reasoning (examples → generalizations), 26 points above baseline.

---

## Requirements

### Phase 1
```bash
pip install pandas numpy textblob
python -m textblob.download_corpora
```

### Phase 2
```bash
pip install pandas numpy
# Latteries already in codebase (utils/latteries/caller.py)
# Requires OPENROUTER_API_KEY in environment
```

---

## Advanced: Combining Phases

Analyze correlations between Phase 1 and Phase 2 quirks:

```python
import pandas as pd

# Load both results
p1 = pd.read_csv('results/quirk_detection_results.csv')
p2 = pd.read_csv('results/llm_quirk_detection_results.csv')

# Merge by config
merged = p1.merge(p2, on='config', suffixes=('_p1', '_p2'))

# Find correlations
print("Do high hedging rates correlate with low assertiveness?")
hedging_configs = p1[p1['quirk'] == 'hedge']['config'].values
assertiveness_scores = p2[p2['dimension'] == 'assertiveness']
assertive_configs = assertiveness_scores[assertiveness_scores['config_mean'] < 40]

overlap = set(hedging_configs) & set(assertive_configs['config'].values)
print(f"Overlapping configs: {overlap}")
```

---

## Tips

1. **Always run Phase 1 first** - it's free and finds obvious patterns
2. **Test Phase 2 on samples** - use `--sample 50` to check if it's detecting useful patterns
3. **Check the cache** - Phase 2 caches results, so re-runs are free
4. **Tune thresholds** - edit detection criteria in the scripts if needed:
   - Phase 1: line 129 (`spike_ratio > 1.5`)
   - Phase 2: line 157 (`abs(deviation) > 20`)

---

## Troubleshooting

### "textblob not installed"
```bash
pip install textblob
python -m textblob.download_corpora
```

### "OPENROUTER_API_KEY not found"
```bash
echo "OPENROUTER_API_KEY=your_key_here" >> .env
```

### Phase 2 is slow
- Reduce `batch_size` in `llm_quirk_detection.py` (line 150)
- Test on smaller sample first: `--sample 100`

### Empty results
- Lower detection thresholds
- Check if your data has enough variance
