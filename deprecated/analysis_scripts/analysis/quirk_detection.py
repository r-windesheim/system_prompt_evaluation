#!/usr/bin/env python3
"""
Behavioral Quirk Detection System - Phase 1 (Regex + NLP-based)

Detects emergent behaviors in LLM responses that are:
- NOT specified in prompt instructions
- Appear significantly more in certain configs
- Concrete and observable

Phase 1a: Regex-based patterns (fast)
Phase 1b: NLP library-based features (sentiment, formality, pronouns)
"""
import pandas as pd
import numpy as np
import re
from collections import defaultdict
from config import BATCH_EVALUATION_FILE

# Import NLP libraries
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    print("⚠️  Warning: textblob not installed. Install with: pip install textblob")
    TEXTBLOB_AVAILABLE = False

print("="*70)
print("BEHAVIORAL QUIRK DETECTION - PHASE 1")
print("="*70)

# Load data
print("\n📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# ============================================================================
# QUIRK DEFINITIONS (Tier 1 - Regex-based)
# ============================================================================

def detect_quirks(text):
    """Detect various behavioral quirks in a text"""
    if pd.isna(text) or not isinstance(text, str):
        return {}

    word_count = len(text.split())
    if word_count == 0:
        return {}

    quirks = {}

    # 1. Parenthetical Obsession - parentheses rate per 100 words
    parentheses_count = text.count('(')
    quirks['parentheses_rate'] = (parentheses_count / word_count) * 100

    # 2. Apologetic Loop - apology phrases
    apology_patterns = r'\b(sorry|apologize|apologies|apology)\b'
    apology_count = len(re.findall(apology_patterns, text.lower()))
    quirks['apology_rate'] = (apology_count / word_count) * 100

    # 3. Question Injection - questions in response
    question_count = text.count('?')
    quirks['question_rate'] = (question_count / word_count) * 100

    # 4. Enumeration Obsession - bullet/numbered lists
    bullet_pattern = r'(?:^|\n)\s*[-•*]\s'
    number_pattern = r'(?:^|\n)\s*\d+[\.)]\s'
    bullets = len(re.findall(bullet_pattern, text))
    numbers = len(re.findall(number_pattern, text))
    quirks['enumeration_rate'] = ((bullets + numbers) / word_count) * 100

    # 5. Hedging Density - uncertainty language
    hedge_patterns = r'\b(might|possibly|perhaps|could be|may|potentially|arguably|seems like)\b'
    hedge_count = len(re.findall(hedge_patterns, text.lower()))
    quirks['hedge_rate'] = (hedge_count / word_count) * 100

    # 6. Certainty Signaling - confidence language
    certainty_patterns = r'\b(definitely|absolutely|clearly|obviously|certainly|undoubtedly|always|never)\b'
    certainty_count = len(re.findall(certainty_patterns, text.lower()))
    quirks['certainty_rate'] = (certainty_count / word_count) * 100

    # 7. Metacommentary - explaining structure/approach
    meta_patterns = r'\b(let me explain|I\'ll structure|to answer|to address|first, let me|my approach)\b'
    meta_count = len(re.findall(meta_patterns, text.lower()))
    quirks['metacommentary_rate'] = (meta_count / word_count) * 100

    # 8. Acknowledgment Inflation - validating the user
    acknowledgment_patterns = r'\b(great question|good point|I understand|that\'s interesting|excellent)\b'
    acknowledgment_count = len(re.findall(acknowledgment_patterns, text.lower()))
    quirks['acknowledgment_rate'] = (acknowledgment_count / word_count) * 100

    # 9. Example Addiction - example frequency
    example_patterns = r'\b(for example|for instance|e\.g\.|such as|like)\b'
    example_count = len(re.findall(example_patterns, text.lower()))
    quirks['example_rate'] = (example_count / word_count) * 100

    # 10. Action-Step Addiction - next steps language
    action_patterns = r'\b(next steps|here\'s what to do|action items|to get started|step \d+)\b'
    action_count = len(re.findall(action_patterns, text.lower()))
    quirks['action_rate'] = (action_count / word_count) * 100

    # 11. Caveat Syndrome - qualification words
    caveat_patterns = r'\b(however|but|although|though|nevertheless|nonetheless|yet)\b'
    caveat_count = len(re.findall(caveat_patterns, text.lower()))
    quirks['caveat_rate'] = (caveat_count / word_count) * 100

    # ========================================================================
    # PHASE 1B: NLP LIBRARY-BASED QUIRKS
    # ========================================================================

    # 12. Sentiment Polarity (TextBlob)
    if TEXTBLOB_AVAILABLE:
        try:
            blob = TextBlob(text)
            # Scale from -1..1 to 0..100 for consistency
            quirks['sentiment_polarity'] = (blob.sentiment.polarity + 1) * 50
            quirks['sentiment_subjectivity'] = blob.sentiment.subjectivity * 100
        except:
            quirks['sentiment_polarity'] = 50  # Neutral
            quirks['sentiment_subjectivity'] = 50

    # 13. Formality Score (lexical features)
    words = text.split()
    avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
    contraction_count = len(re.findall(r"\w+'\w+", text))
    contraction_rate = (contraction_count / word_count) * 100 if word_count > 0 else 0

    # Formality = longer words + fewer contractions
    # Scale 0-100 where 100 = very formal
    quirks['formality_score'] = (avg_word_length * 10) - (contraction_rate * 5)
    quirks['contraction_rate'] = contraction_rate

    # 14. First-Person Density ("I", "me", "my")
    first_person = r'\b(I|me|my|mine|myself)\b'
    first_person_count = len(re.findall(first_person, text, re.I))
    quirks['first_person_rate'] = (first_person_count / word_count) * 100

    # 15. Second-Person Density ("you", "your")
    second_person = r'\b(you|your|yours|yourself)\b'
    second_person_count = len(re.findall(second_person, text, re.I))
    quirks['second_person_rate'] = (second_person_count / word_count) * 100

    # 16. Third-Person Density
    third_person = r'\b(he|she|they|it|him|her|them|his|hers|their|theirs)\b'
    third_person_count = len(re.findall(third_person, text, re.I))
    quirks['third_person_rate'] = (third_person_count / word_count) * 100

    # 17. Conditional Language ("if", "when", "unless")
    conditional = r'\b(if|when|unless|provided that|assuming|suppose)\b'
    conditional_count = len(re.findall(conditional, text, re.I))
    quirks['conditional_rate'] = (conditional_count / word_count) * 100

    # 18. Modal Verbs (possibility/necessity)
    modals = r'\b(can|could|may|might|must|should|would|will|shall)\b'
    modal_count = len(re.findall(modals, text, re.I))
    quirks['modal_verb_rate'] = (modal_count / word_count) * 100

    # 19. Imperative Language (commands)
    imperatives = r'\b(do|don\'t|make sure|ensure|avoid|remember|consider|try)\b'
    imperative_count = len(re.findall(imperatives, text, re.I))
    quirks['imperative_rate'] = (imperative_count / word_count) * 100

    return quirks

# ============================================================================
# ANALYZE ALL RESPONSES
# ============================================================================

print("🔍 Analyzing quirks in all responses...\n")

# Detect quirks in each response
all_quirks = []
for idx, row in df.iterrows():
    response_text = row.get('response', '')
    config = row.get('config_name', '')

    quirks = detect_quirks(response_text)
    quirks['config'] = config
    quirks['response_text'] = response_text
    all_quirks.append(quirks)

quirks_df = pd.DataFrame(all_quirks)

# Calculate baseline rates (all responses combined)
quirk_types = [col for col in quirks_df.columns if col.endswith('_rate')]

print("📊 BASELINE RATES (all configs averaged):\n")
baseline_rates = {}
for quirk in quirk_types:
    baseline = quirks_df[quirk].mean()
    baseline_rates[quirk] = baseline
    quirk_name = quirk.replace('_rate', '').replace('_', ' ').title()
    print(f"   {quirk_name:25s}: {baseline:.3f} per 100 words")

# ============================================================================
# DETECT CONFIG-SPECIFIC QUIRKS
# ============================================================================

print("\n" + "="*70)
print("QUIRK DETECTION: Configs with >3x baseline AND >60% prevalence")
print("="*70)

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

        # Count how many responses show this quirk (non-zero)
        responses_with_quirk = (config_data[quirk_type] > 0).sum()
        prevalence = responses_with_quirk / len(config_data)

        # Detection criteria - relaxed to catch more quirks
        if spike_ratio > 1.5 and prevalence > 0.5:
            # Find example responses
            examples = config_data[config_data[quirk_type] > 0].nlargest(3, quirk_type)

            detected_quirks.append({
                'config': config,
                'quirk': quirk_type,
                'baseline': baseline_mean,
                'config_mean': config_mean,
                'spike_ratio': spike_ratio,
                'prevalence': prevalence,
                'examples': examples['response_text'].tolist()
            })

# Sort by spike ratio
detected_quirks.sort(key=lambda x: x['spike_ratio'], reverse=True)

# No longer need the retry logic - threshold is already set to 1.5x

# ============================================================================
# REPORT DETECTED QUIRKS
# ============================================================================

if detected_quirks:
    print(f"\n🚨 DETECTED {len(detected_quirks)} BEHAVIORAL QUIRKS:\n")

    for i, quirk in enumerate(detected_quirks[:20], 1):  # Show top 20
        quirk_name = quirk['quirk'].replace('_rate', '').replace('_', ' ').title()

        print(f"\n{'='*70}")
        print(f"#{i} - {quirk_name.upper()} SYNDROME")
        print(f"{'='*70}")
        print(f"Config: {quirk['config']}")
        print(f"Baseline rate: {quirk['baseline']:.3f} per 100 words")
        print(f"Config rate: {quirk['config_mean']:.3f} per 100 words")
        print(f"Spike: {quirk['spike_ratio']:.1f}x baseline")
        print(f"Prevalence: {quirk['prevalence']*100:.0f}% of responses")

        print(f"\n📝 Example snippets:")
        for j, example in enumerate(quirk['examples'][:2], 1):  # Show 2 examples
            if len(example) > 300:
                snippet = example[:300] + "..."
            else:
                snippet = example
            print(f"\n   Example {j}:")
            print(f"   {snippet}")
            print()
else:
    print("\n✓ No significant behavioral quirks detected")
    print("   All configs behave similarly")

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

print("\n" + "="*70)
print("SUMMARY STATISTICS")
print("="*70)

# Group quirks by config
quirks_by_config = defaultdict(list)
for quirk in detected_quirks:
    quirks_by_config[quirk['config']].append(quirk['quirk'])

if quirks_by_config:
    print("\n🎯 Configs with most quirks:")
    sorted_configs = sorted(quirks_by_config.items(), key=lambda x: len(x[1]), reverse=True)
    for config, quirk_list in sorted_configs[:10]:
        print(f"   {config:20s}: {len(quirk_list)} quirks")
        for q in quirk_list:
            quirk_name = q.replace('_rate', '').replace('_', ' ').title()
            print(f"      - {quirk_name}")

# Most common quirks
quirk_counts = defaultdict(int)
for quirk in detected_quirks:
    quirk_counts[quirk['quirk']] += 1

if quirk_counts:
    print("\n📊 Most common quirks across all configs:")
    sorted_quirks = sorted(quirk_counts.items(), key=lambda x: x[1], reverse=True)
    for quirk_type, count in sorted_quirks:
        quirk_name = quirk_type.replace('_rate', '').replace('_', ' ').title()
        print(f"   {quirk_name:25s}: appears in {count} configs")

# ============================================================================
# EXPORT RESULTS
# ============================================================================

# Save detailed results
output_file = 'results/quirk_detection_results.csv'
if detected_quirks:
    results_df = pd.DataFrame([
        {
            'config': q['config'],
            'quirk': q['quirk'].replace('_rate', ''),
            'baseline_rate': q['baseline'],
            'config_rate': q['config_mean'],
            'spike_ratio': q['spike_ratio'],
            'prevalence_pct': q['prevalence'] * 100
        }
        for q in detected_quirks
    ])
    results_df.to_csv(output_file, index=False)
    print(f"\n💾 Detailed results saved to: {output_file}")
else:
    print(f"\n💾 No quirks to export")

print("\n" + "="*70)
print("✅ Quirk detection complete!")
print("="*70)
