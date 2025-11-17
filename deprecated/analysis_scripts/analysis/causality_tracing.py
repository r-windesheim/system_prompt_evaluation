#!/usr/bin/env python3
"""
Causality Tracing: Detect Emergent Behaviors in Prompt Combinations

Tests whether quirks are:
- ADDITIVE: Effect = sum of individual sections
- SYNERGISTIC: Effect > sum of parts (amplification)
- EMERGENT: Quirk doesn't exist in subsets (appears from nowhere)
- ANTAGONISTIC: Effect < sum of parts (sections interfere)

This answers: "Is this behavior emergent or just the sum of its parts?"
"""
import pandas as pd
import numpy as np
import re
import sys
from pathlib import Path
from itertools import combinations
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BATCH_EVALUATION_FILE

# Import quirk detection
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

print("="*70)
print("CAUSALITY TRACING: EMERGENT BEHAVIOR DETECTION")
print("="*70)
print()

# ============================================================================
# LOAD DATA AND DETECT QUIRKS
# ============================================================================

def detect_quirks(text):
    """Detect various behavioral quirks in a text (same as phase 1)"""
    if pd.isna(text) or not isinstance(text, str):
        return {}

    word_count = len(text.split())
    if word_count == 0:
        return {}

    quirks = {}

    # Regex-based quirks (simplified for speed)
    quirks['parentheses_rate'] = (text.count('(') / word_count) * 100
    quirks['apology_rate'] = (len(re.findall(r'\b(sorry|apologize|apologies|apology)\b', text.lower())) / word_count) * 100
    quirks['question_rate'] = (text.count('?') / word_count) * 100

    bullets = len(re.findall(r'(?:^|\n)\s*[-•*]\s', text))
    numbers = len(re.findall(r'(?:^|\n)\s*\d+[\.)]\s', text))
    quirks['enumeration_rate'] = ((bullets + numbers) / word_count) * 100

    quirks['hedge_rate'] = (len(re.findall(r'\b(might|possibly|perhaps|could be|may|potentially|arguably|seems like)\b', text.lower())) / word_count) * 100
    quirks['certainty_rate'] = (len(re.findall(r'\b(definitely|absolutely|clearly|obviously|certainly|undoubtedly|always|never)\b', text.lower())) / word_count) * 100
    quirks['metacommentary_rate'] = (len(re.findall(r'\b(let me explain|I\'ll structure|to answer|to address|first, let me|my approach)\b', text.lower())) / word_count) * 100
    quirks['acknowledgment_rate'] = (len(re.findall(r'\b(great question|good point|I understand|that\'s interesting|excellent)\b', text.lower())) / word_count) * 100
    quirks['example_rate'] = (len(re.findall(r'\b(for example|for instance|e\.g\.|such as|like)\b', text.lower())) / word_count) * 100
    quirks['caveat_rate'] = (len(re.findall(r'\b(however|but|although|though|nevertheless|nonetheless|yet)\b', text.lower())) / word_count) * 100

    return quirks

print("📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

print("🔍 Detecting quirks in all responses...")
all_quirks = []
for idx, row in df.iterrows():
    response_text = row.get('response', '')
    config = row.get('config_name', '')

    quirks = detect_quirks(response_text)
    quirks['config'] = config
    all_quirks.append(quirks)

quirks_df = pd.DataFrame(all_quirks)
quirk_types = [col for col in quirks_df.columns if col.endswith('_rate')]
print(f"✓ Analyzed {len(quirks_df)} responses\n")

# ============================================================================
# DETECT CONFIG-LEVEL QUIRKS (same threshold as phase 1)
# ============================================================================

print("🎯 Identifying configs with significant quirks...\n")

baseline_rates = {quirk: quirks_df[quirk].mean() for quirk in quirk_types}

detected_quirks = []
for config in quirks_df['config'].unique():
    if pd.isna(config):
        continue

    config_data = quirks_df[quirks_df['config'] == config]

    for quirk_type in quirk_types:
        config_mean = config_data[quirk_type].mean()
        baseline_mean = baseline_rates[quirk_type]

        if baseline_mean == 0:
            continue

        spike_ratio = config_mean / baseline_mean
        responses_with_quirk = (config_data[quirk_type] > 0).sum()
        prevalence = responses_with_quirk / len(config_data)

        # Detection criteria: >1.5x baseline AND >50% prevalence
        if spike_ratio > 1.5 and prevalence > 0.5:
            detected_quirks.append({
                'config': config,
                'quirk': quirk_type,
                'config_mean': config_mean,
                'baseline': baseline_mean,
                'spike_ratio': spike_ratio
            })

print(f"✓ Found {len(detected_quirks)} config-level quirks\n")

if len(detected_quirks) == 0:
    print("❌ No significant quirks detected. Cannot perform causality tracing.")
    print("   Try lowering the detection threshold (spike_ratio > 1.3)")
    sys.exit(0)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_config_sections(config):
    """Extract section numbers from config string"""
    return sorted([int(s) for s in re.findall(r'\d+', str(config))])

def config_to_string(sections):
    """Convert section list to config string"""
    return '+'.join(map(str, sorted(sections)))

def get_quirk_rate_for_config(config_str, quirk_type):
    """Get the quirk rate for a specific config"""
    config_data = quirks_df[quirks_df['config'] == config_str]
    if len(config_data) == 0:
        return None
    return config_data[quirk_type].mean()

# ============================================================================
# CAUSALITY TRACING
# ============================================================================

print("="*70)
print("TESTING CAUSALITY: Are quirks emergent or additive?")
print("="*70)
print()

causality_results = []

for quirk_info in detected_quirks:
    config = quirk_info['config']
    quirk_type = quirk_info['quirk']
    observed_rate = quirk_info['config_mean']

    sections = parse_config_sections(config)

    if len(sections) < 2:
        # Single section configs can't show emergence
        continue

    # Test individual section effects
    individual_effects = {}
    for section in sections:
        section_config = str(section)
        rate = get_quirk_rate_for_config(section_config, quirk_type)
        if rate is not None:
            individual_effects[section] = rate

    # Calculate expected additive effect
    if len(individual_effects) > 0:
        # Expected = average of individual effects (not sum, since rates don't add)
        # Better approach: compare to what we'd predict from individual sections
        expected_from_individuals = sum(individual_effects.values()) / len(individual_effects)
    else:
        expected_from_individuals = baseline_rates[quirk_type]

    # Test all subsets
    subset_effects = {}
    for r in range(1, len(sections)):
        for subset in combinations(sections, r):
            subset_config = config_to_string(subset)
            rate = get_quirk_rate_for_config(subset_config, quirk_type)
            if rate is not None:
                subset_effects[subset_config] = rate

    # Classify causality
    baseline = baseline_rates[quirk_type]

    # Calculate emergence score
    # Emergence = (observed - max_subset_effect) / baseline
    if subset_effects:
        max_subset_effect = max(subset_effects.values())
        emergence_score = (observed_rate - max_subset_effect) / baseline if baseline > 0 else 0
    else:
        emergence_score = (observed_rate - baseline) / baseline if baseline > 0 else 0

    # Classification
    if emergence_score > 0.5:  # Significant emergence
        classification = "EMERGENT"
        explanation = "Quirk appears in full config but not in subsets"
    elif emergence_score > 0.2:
        classification = "SYNERGISTIC"
        explanation = "Full config shows amplified effect vs subsets"
    elif emergence_score > -0.2:
        classification = "ADDITIVE"
        explanation = "Effect roughly matches combination of parts"
    else:
        classification = "ANTAGONISTIC"
        explanation = "Sections interfere, reducing the effect"

    causality_results.append({
        'config': config,
        'quirk': quirk_type,
        'classification': classification,
        'observed_rate': observed_rate,
        'baseline': baseline,
        'spike_ratio': quirk_info['spike_ratio'],
        'individual_effects': individual_effects,
        'subset_effects': subset_effects,
        'emergence_score': emergence_score,
        'explanation': explanation
    })

# ============================================================================
# REPORT RESULTS BY CLASSIFICATION
# ============================================================================

print("="*70)
print("CAUSALITY CLASSIFICATION RESULTS")
print("="*70)
print()

# Group by classification
by_classification = defaultdict(list)
for result in causality_results:
    by_classification[result['classification']].append(result)

# Sort classifications by wow factor
classification_order = ['EMERGENT', 'SYNERGISTIC', 'ANTAGONISTIC', 'ADDITIVE']

for classification in classification_order:
    results = by_classification[classification]
    if not results:
        continue

    # Sort by emergence score (absolute value)
    results.sort(key=lambda x: abs(x['emergence_score']), reverse=True)

    print(f"\n{'='*70}")
    print(f"🔥 {classification} BEHAVIORS ({len(results)} found)")
    print(f"{'='*70}\n")

    for i, result in enumerate(results[:10], 1):  # Show top 10
        quirk_name = result['quirk'].replace('_rate', '').replace('_', ' ').title()

        print(f"{i}. {result['config']} → {quirk_name}")
        print(f"   {result['explanation']}")
        print(f"   Emergence Score: {result['emergence_score']:.2f}")
        print(f"   Observed: {result['observed_rate']:.3f} | Baseline: {result['baseline']:.3f} | Spike: {result['spike_ratio']:.1f}x")

        # Show individual section effects
        if result['individual_effects']:
            print(f"\n   📊 Individual Section Effects:")
            for section, rate in sorted(result['individual_effects'].items()):
                print(f"      Section {section}: {rate:.3f}")

        # Show subset effects (only if interesting)
        if result['subset_effects'] and classification in ['EMERGENT', 'SYNERGISTIC']:
            print(f"\n   🔍 Subset Testing:")
            for subset_config, rate in sorted(result['subset_effects'].items(),
                                             key=lambda x: len(x[0])):
                print(f"      Config {subset_config}: {rate:.3f}")
            print(f"      Full config {result['config']}: {result['observed_rate']:.3f} ⭐")

        print()

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

print("="*70)
print("SUMMARY")
print("="*70)
print()

total = len(causality_results)
if total > 0:
    for classification in classification_order:
        count = len(by_classification[classification])
        pct = (count / total) * 100
        print(f"   {classification:15s}: {count:3d} ({pct:5.1f}%)")

print()

emergent_count = len(by_classification['EMERGENT'])
synergistic_count = len(by_classification['SYNERGISTIC'])
non_linear = emergent_count + synergistic_count

if non_linear > 0:
    print(f"🚨 WOW FACTOR DETECTED!")
    print(f"   {non_linear} behaviors show NON-LINEAR composition")
    print(f"   ({(non_linear/total*100):.1f}% of all detected quirks)")
    print()
    print(f"   💡 Key insight: Prompt sections don't just add up.")
    print(f"      They create NEW behaviors when combined.")
else:
    print(f"✓ No emergence detected")
    print(f"   All behaviors are predictable from individual sections")

# ============================================================================
# EXPORT RESULTS
# ============================================================================

print()
print("="*70)
print("EXPORTING RESULTS")
print("="*70)
print()

# Export to CSV
export_data = []
for result in causality_results:
    export_data.append({
        'config': result['config'],
        'quirk': result['quirk'].replace('_rate', ''),
        'classification': result['classification'],
        'emergence_score': result['emergence_score'],
        'observed_rate': result['observed_rate'],
        'baseline': result['baseline'],
        'spike_ratio': result['spike_ratio'],
        'explanation': result['explanation']
    })

export_df = pd.DataFrame(export_data)
export_df = export_df.sort_values('emergence_score', ascending=False, key=abs)

output_csv = 'results/causality_tracing.csv'
export_df.to_csv(output_csv, index=False)
print(f"💾 Results saved to: {output_csv}")

# Show most emergent examples
print()
print("="*70)
print("TOP 5 MOST EMERGENT BEHAVIORS")
print("="*70)
print()

top_emergent = export_df[export_df['classification'] == 'EMERGENT'].head(5)
if len(top_emergent) > 0:
    for idx, row in top_emergent.iterrows():
        print(f"• {row['config']} → {row['quirk']}")
        print(f"  Emergence: {row['emergence_score']:.2f} | Spike: {row['spike_ratio']:.1f}x")
        print()
else:
    print("No emergent behaviors found.")

print("="*70)
print("✅ Causality tracing complete!")
print("="*70)
