#!/usr/bin/env python3
"""
Section-Level Quirk Attribution

Determines which individual prompt sections CAUSE specific behavioral quirks.

Uses with/without methodology:
- Compare configs WITH section X vs configs WITHOUT section X
- Calculate impact: (mean_with - mean_without)
- Positive impact = section CAUSES quirk
- Negative impact = section REDUCES quirk
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import re
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BATCH_EVALUATION_FILE

# Import quirk detection
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

print("="*70)
print("SECTION-LEVEL QUIRK ATTRIBUTION")
print("="*70)

# Load data
print("\n📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# ============================================================================
# DETECT QUIRKS (same as quirk_detection.py)
# ============================================================================

def detect_quirks(text):
    """Detect various behavioral quirks in a text"""
    if pd.isna(text) or not isinstance(text, str):
        return {}

    word_count = len(text.split())
    if word_count == 0:
        return {}

    quirks = {}

    # Regex-based quirks
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
    quirks['action_rate'] = (len(re.findall(r'\b(next steps|here\'s what to do|action items|to get started|step \d+)\b', text.lower())) / word_count) * 100
    quirks['caveat_rate'] = (len(re.findall(r'\b(however|but|although|though|nevertheless|nonetheless|yet)\b', text.lower())) / word_count) * 100

    # NLP-based quirks
    if TEXTBLOB_AVAILABLE:
        try:
            blob = TextBlob(text)
            quirks['sentiment_polarity'] = (blob.sentiment.polarity + 1) * 50
            quirks['sentiment_subjectivity'] = blob.sentiment.subjectivity * 100
        except:
            quirks['sentiment_polarity'] = 50
            quirks['sentiment_subjectivity'] = 50

    words = text.split()
    avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
    contraction_count = len(re.findall(r"\w+'\w+", text))
    contraction_rate = (contraction_count / word_count) * 100 if word_count > 0 else 0

    quirks['formality_score'] = (avg_word_length * 10) - (contraction_rate * 5)
    quirks['contraction_rate'] = contraction_rate
    quirks['first_person_rate'] = (len(re.findall(r'\b(I|me|my|mine|myself)\b', text, re.I)) / word_count) * 100
    quirks['second_person_rate'] = (len(re.findall(r'\b(you|your|yours|yourself)\b', text, re.I)) / word_count) * 100
    quirks['third_person_rate'] = (len(re.findall(r'\b(he|she|they|it|him|her|them|his|hers|their|theirs)\b', text, re.I)) / word_count) * 100
    quirks['conditional_rate'] = (len(re.findall(r'\b(if|when|unless|provided that|assuming|suppose)\b', text, re.I)) / word_count) * 100
    quirks['modal_verb_rate'] = (len(re.findall(r'\b(can|could|may|might|must|should|would|will|shall)\b', text, re.I)) / word_count) * 100
    quirks['imperative_rate'] = (len(re.findall(r'\b(do|don\'t|make sure|ensure|avoid|remember|consider|try)\b', text, re.I)) / word_count) * 100

    return quirks

print("🔍 Analyzing quirks in all responses...")
all_quirks = []
for idx, row in df.iterrows():
    response_text = row.get('response', '')
    config = row.get('config_name', '')

    quirks = detect_quirks(response_text)
    quirks['config'] = config
    all_quirks.append(quirks)

quirks_df = pd.DataFrame(all_quirks)
quirk_types = [col for col in quirks_df.columns if col not in ['config']]

print(f"✓ Detected quirks in {len(quirks_df)} responses\n")

# ============================================================================
# SECTION-LEVEL IMPACT ANALYSIS
# ============================================================================

print("="*70)
print("CALCULATING SECTION IMPACT FOR EACH QUIRK")
print("="*70)
print()

# Determine section range from data
sections = []
for config in quirks_df['config'].unique():
    if pd.isna(config):
        continue
    # Extract section numbers from config (e.g., "1+2+3" -> [1, 2, 3])
    section_nums = re.findall(r'\d+', str(config))
    sections.extend(section_nums)

unique_sections = sorted(set(sections), key=int)
print(f"📋 Detected sections: {', '.join(unique_sections)}\n")

# Calculate impact for each section on each quirk
section_quirk_impact = {}

for section_num in unique_sections:
    section_quirk_impact[section_num] = {}

    for quirk_type in quirk_types:
        # Configs WITH this section
        with_section = quirks_df[quirks_df['config'].str.contains(f'(?:^|\\+){section_num}(?:\\+|$)',
                                                                   regex=True, na=False)]
        # Configs WITHOUT this section
        without_section = quirks_df[~quirks_df['config'].str.contains(f'(?:^|\\+){section_num}(?:\\+|$)',
                                                                       regex=True, na=False)]

        if len(with_section) > 0 and len(without_section) > 0:
            with_score = with_section[quirk_type].mean()
            without_score = without_section[quirk_type].mean()
            impact = with_score - without_score

            section_quirk_impact[section_num][quirk_type] = {
                'with': with_score,
                'without': without_score,
                'impact': impact,
                'with_count': len(with_section),
                'without_count': len(without_section)
            }

# ============================================================================
# REPORT: TOP QUIRK DRIVERS
# ============================================================================

print("="*70)
print("TOP QUIRK DRIVERS (sections that CAUSE specific quirks)")
print("="*70)
print()

# For each quirk, find the section with the biggest positive impact
quirk_drivers = []

for quirk_type in quirk_types:
    impacts = []
    for section_num in unique_sections:
        if quirk_type in section_quirk_impact[section_num]:
            impact = section_quirk_impact[section_num][quirk_type]['impact']
            impacts.append((section_num, impact))

    if impacts:
        # Sort by impact (highest first)
        impacts.sort(key=lambda x: x[1], reverse=True)
        top_driver = impacts[0]

        if top_driver[1] > 0.1:  # Only report meaningful impacts
            quirk_drivers.append({
                'quirk': quirk_type,
                'section': top_driver[0],
                'impact': top_driver[1]
            })

# Sort by absolute impact
quirk_drivers.sort(key=lambda x: abs(x['impact']), reverse=True)

if quirk_drivers:
    for i, driver in enumerate(quirk_drivers[:15], 1):  # Show top 15
        quirk_name = driver['quirk'].replace('_rate', '').replace('_', ' ').replace('_score', '').title()
        section = driver['section']
        impact = driver['impact']

        # Get details
        details = section_quirk_impact[section][driver['quirk']]

        print(f"{i:2d}. Section {section} → {quirk_name}")
        print(f"    Impact: +{impact:.2f} points")
        print(f"    With Section {section}: {details['with']:.2f} | Without: {details['without']:.2f}")
        print(f"    Sample size: {details['with_count']} with, {details['without_count']} without")
        print()
else:
    print("✓ No significant quirk drivers detected\n")

# ============================================================================
# REPORT: TOP QUIRK REDUCERS
# ============================================================================

print("="*70)
print("TOP QUIRK REDUCERS (sections that SUPPRESS specific quirks)")
print("="*70)
print()

quirk_reducers = []

for quirk_type in quirk_types:
    impacts = []
    for section_num in unique_sections:
        if quirk_type in section_quirk_impact[section_num]:
            impact = section_quirk_impact[section_num][quirk_type]['impact']
            impacts.append((section_num, impact))

    if impacts:
        # Sort by impact (lowest/most negative first)
        impacts.sort(key=lambda x: x[1])
        top_reducer = impacts[0]

        if top_reducer[1] < -0.1:  # Only report meaningful reductions
            quirk_reducers.append({
                'quirk': quirk_type,
                'section': top_reducer[0],
                'impact': top_reducer[1]
            })

# Sort by absolute impact
quirk_reducers.sort(key=lambda x: abs(x['impact']), reverse=True)

if quirk_reducers:
    for i, reducer in enumerate(quirk_reducers[:15], 1):  # Show top 15
        quirk_name = reducer['quirk'].replace('_rate', '').replace('_', ' ').replace('_score', '').title()
        section = reducer['section']
        impact = reducer['impact']

        # Get details
        details = section_quirk_impact[section][reducer['quirk']]

        print(f"{i:2d}. Section {section} → {quirk_name}")
        print(f"    Impact: {impact:.2f} points (REDUCES)")
        print(f"    With Section {section}: {details['with']:.2f} | Without: {details['without']:.2f}")
        print(f"    Sample size: {details['with_count']} with, {details['without_count']} without")
        print()
else:
    print("✓ No significant quirk reducers detected\n")

# ============================================================================
# SECTION PROFILES (Which sections have most quirks?)
# ============================================================================

print("="*70)
print("SECTION QUIRK PROFILES")
print("="*70)
print()

for section_num in unique_sections:
    print(f"📌 SECTION {section_num}")
    print("-" * 70)

    # Get all impacts for this section
    impacts = []
    for quirk_type, data in section_quirk_impact[section_num].items():
        if abs(data['impact']) > 0.1:  # Only meaningful impacts
            quirk_name = quirk_type.replace('_rate', '').replace('_', ' ').replace('_score', '').title()
            impacts.append({
                'quirk': quirk_name,
                'impact': data['impact']
            })

    # Sort by absolute impact
    impacts.sort(key=lambda x: abs(x['impact']), reverse=True)

    if impacts:
        # Positive impacts (causes quirks)
        positive = [i for i in impacts if i['impact'] > 0]
        if positive:
            print(f"\n   🔥 CAUSES these quirks:")
            for imp in positive[:5]:  # Top 5
                print(f"      • {imp['quirk']:30s} +{imp['impact']:.2f}")

        # Negative impacts (reduces quirks)
        negative = [i for i in impacts if i['impact'] < 0]
        if negative:
            print(f"\n   ❄️  REDUCES these quirks:")
            for imp in negative[:5]:  # Top 5
                print(f"      • {imp['quirk']:30s} {imp['impact']:.2f}")
    else:
        print("   ✓ Neutral - no significant quirk impacts")

    print()

# ============================================================================
# VISUALIZATION: SECTION IMPACT HEATMAP
# ============================================================================

print("="*70)
print("CREATING VISUALIZATION")
print("="*70)
print()

# Build impact matrix
impact_matrix = []
quirk_labels = []

for quirk_type in quirk_types:
    row = []
    for section_num in unique_sections:
        if quirk_type in section_quirk_impact[section_num]:
            impact = section_quirk_impact[section_num][quirk_type]['impact']
            row.append(impact)
        else:
            row.append(0)

    impact_matrix.append(row)
    quirk_name = quirk_type.replace('_rate', '').replace('_', ' ').replace('_score', '').title()
    quirk_labels.append(quirk_name)

impact_matrix = np.array(impact_matrix)

# Create heatmap
fig, ax = plt.subplots(figsize=(10, 12))

# Determine vmin/vmax for symmetric color scale
max_abs = max(abs(impact_matrix.min()), abs(impact_matrix.max()))
vmin, vmax = -max_abs, max_abs

sns.heatmap(impact_matrix,
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=0,
            vmin=vmin,
            vmax=vmax,
            xticklabels=[f'Section {s}' for s in unique_sections],
            yticklabels=quirk_labels,
            linewidths=0.5,
            linecolor='gray',
            cbar_kws={'label': 'Impact (positive = causes quirk)'},
            ax=ax)

ax.set_title('Section Impact on Behavioral Quirks\n(Green = Causes, Red = Reduces)',
            fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('Section', fontsize=12, fontweight='bold')
ax.set_ylabel('Quirk Type', fontsize=12, fontweight='bold')

plt.tight_layout()
output_file = 'analysis/images/section_quirk_attribution.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"📊 Heatmap saved to: {output_file}\n")

# ============================================================================
# EXPORT RESULTS
# ============================================================================

print("="*70)
print("EXPORTING RESULTS")
print("="*70)
print()

# Flatten section_quirk_impact for CSV export
export_data = []
for section_num in unique_sections:
    for quirk_type, data in section_quirk_impact[section_num].items():
        quirk_name = quirk_type.replace('_rate', '').replace('_score', '')
        export_data.append({
            'section': section_num,
            'quirk': quirk_name,
            'impact': data['impact'],
            'with_section_mean': data['with'],
            'without_section_mean': data['without'],
            'with_count': data['with_count'],
            'without_count': data['without_count']
        })

export_df = pd.DataFrame(export_data)
export_df = export_df.sort_values('impact', ascending=False, key=abs)

output_csv = 'results/section_quirk_attribution.csv'
export_df.to_csv(output_csv, index=False)
print(f"💾 Detailed results saved to: {output_csv}")

print("\n" + "="*70)
print("✅ Section quirk attribution complete!")
print("="*70)
