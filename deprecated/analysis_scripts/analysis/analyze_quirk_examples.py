#!/usr/bin/env python3
"""
Deep dive into quirk examples - show actual response differences
"""
import pandas as pd
import re

print("="*70)
print("QUIRK EXAMPLE DEEP DIVE")
print("="*70)

# Load data
df = pd.read_csv('../cached_results/batch_evaluation.csv')
quirks_df = pd.read_csv('results/quirk_detection_results.csv')

print(f"\n📁 Loaded {len(df)} responses and {len(quirks_df)} detected quirks\n")

# ============================================================================
# ANALYSIS 1: Show actual response examples
# ============================================================================

def count_pattern(text, pattern):
    """Count regex pattern matches"""
    if pd.isna(text) or not isinstance(text, str):
        return 0
    return len(re.findall(pattern, text.lower()))

print("="*70)
print("PART 1: Side-by-Side Quirk Examples")
print("="*70)

# For each quirk, show a quirky response vs a non-quirky response
quirk_patterns = {
    'hedge': r'\b(might|possibly|perhaps|could be|may|potentially)\b',
    'question': r'\?',
    'caveat': r'\b(however|but|although|though|nevertheless)\b',
    'example': r'\b(for example|for instance|e\.g\.|such as|like)\b'
}

for idx, quirk_row in quirks_df.iterrows():
    config = quirk_row['config']
    quirk_type = quirk_row['quirk']

    print(f"\n{'='*70}")
    print(f"QUIRK: {quirk_type.upper()} SYNDROME")
    print(f"Config: {config} (Spike: {quirk_row['spike_ratio']:.1f}x)")
    print(f"{'='*70}")

    # Get responses from this config
    config_responses = df[df['config_name'] == config]

    # Find a response with HIGH quirk rate
    if quirk_type in quirk_patterns:
        pattern = quirk_patterns[quirk_type]

        # Calculate quirk count for each response
        config_responses = config_responses.copy()
        config_responses['quirk_count'] = config_responses['response'].apply(
            lambda x: count_pattern(x, pattern)
        )
        config_responses['word_count_calc'] = config_responses['response'].apply(
            lambda x: len(str(x).split())
        )
        config_responses['quirk_rate'] = (
            config_responses['quirk_count'] / config_responses['word_count_calc']
        ) * 100

        # Get highest quirk response
        quirky_response = config_responses.nlargest(1, 'quirk_rate').iloc[0]

        # Find a non-quirky config for comparison (configs NOT in quirk list)
        quirky_configs = quirks_df['config'].unique()
        non_quirky_configs = [c for c in df['config_name'].unique()
                              if c not in quirky_configs and pd.notna(c)]

        if non_quirky_configs:
            # Get same query from a non-quirky config
            query = quirky_response['test_query']
            non_quirky = df[
                (df['config_name'].isin(non_quirky_configs)) &
                (df['test_query'] == query)
            ]

            if len(non_quirky) > 0:
                non_quirky_response = non_quirky.iloc[0]

                print(f"\n🔴 QUIRKY Response (Config: {config}):")
                print(f"   Query: {query[:80]}...")
                print(f"   {quirk_type.title()} rate: {quirky_response['quirk_rate']:.2f} per 100 words")
                print(f"\n   Response snippet:")
                snippet = quirky_response['response'][:500]
                print(f"   {snippet}...")

                # Count actual instances
                matches = re.findall(pattern, quirky_response['response'].lower())
                unique_matches = list(set(matches))[:10]
                print(f"\n   Found {len(matches)} instances: {', '.join(unique_matches)}")

                print(f"\n🟢 NON-QUIRKY Response (Config: {non_quirky_response['config_name']}):")
                non_quirky_rate = (count_pattern(non_quirky_response['response'], pattern) /
                                  len(str(non_quirky_response['response']).split())) * 100
                print(f"   Same query: {query[:80]}...")
                print(f"   {quirk_type.title()} rate: {non_quirky_rate:.2f} per 100 words")
                print(f"\n   Response snippet:")
                snippet = non_quirky_response['response'][:500]
                print(f"   {snippet}...")

                matches = re.findall(pattern, non_quirky_response['response'].lower())
                unique_matches = list(set(matches))[:10] if matches else []
                print(f"\n   Found {len(matches)} instances: {', '.join(unique_matches) if matches else 'None'}")

                print(f"\n   📊 Difference: {quirky_response['quirk_rate'] - non_quirky_rate:.2f} points")

print("\n" + "="*70)
print("PART 2: Test Section 2 Removal Impact")
print("="*70)

# Calculate quirk rates for configs WITH and WITHOUT Section 2
print("\nDoes removing Section 2 ('Be kind') eliminate quirks?\n")

# Function to detect quirks in text
def calculate_all_quirk_rates(text):
    """Calculate all quirk rates for a text"""
    if pd.isna(text) or not isinstance(text, str):
        return {}

    word_count = len(text.split())
    if word_count == 0:
        return {}

    rates = {}
    for quirk_name, pattern in quirk_patterns.items():
        count = count_pattern(text, pattern)
        rates[quirk_name] = (count / word_count) * 100

    return rates

# Calculate quirk rates for all responses
all_quirk_data = []
for idx, row in df.iterrows():
    config = row['config_name']
    if pd.isna(config):
        continue

    has_section_2 = '2' in config.split('+')
    quirk_rates = calculate_all_quirk_rates(row['response'])

    all_quirk_data.append({
        'config': config,
        'has_section_2': has_section_2,
        **quirk_rates
    })

quirk_analysis_df = pd.DataFrame(all_quirk_data)

# Compare WITH vs WITHOUT Section 2
with_section_2 = quirk_analysis_df[quirk_analysis_df['has_section_2'] == True]
without_section_2 = quirk_analysis_df[quirk_analysis_df['has_section_2'] == False]

print(f"Configs WITH Section 2: {len(with_section_2['config'].unique())} configs")
print(f"Configs WITHOUT Section 2: {len(without_section_2['config'].unique())} configs")

print("\n" + "="*70)
print("QUIRK RATES: WITH vs WITHOUT Section 2")
print("="*70)

for quirk_type in quirk_patterns.keys():
    with_rate = with_section_2[quirk_type].mean()
    without_rate = without_section_2[quirk_type].mean()
    reduction = ((with_rate - without_rate) / with_rate * 100) if with_rate > 0 else 0

    symbol = "🔴" if with_rate > without_rate else "🟢"

    print(f"\n{quirk_type.upper()} SYNDROME:")
    print(f"   {symbol} WITH Section 2:    {with_rate:.3f} per 100 words")
    print(f"   {symbol} WITHOUT Section 2: {without_rate:.3f} per 100 words")
    print(f"   Difference: {with_rate - without_rate:+.3f} ({reduction:.1f}% reduction)")

    if reduction > 20:
        print(f"   🚨 WOW: Removing Section 2 reduces {quirk_type} by {reduction:.0f}%!")

# Find configs without Section 2 that still have quirks
print("\n" + "="*70)
print("Configs WITHOUT Section 2 that still show quirks:")
print("="*70)

quirky_without_2 = []
for config in without_section_2['config'].unique():
    config_data = without_section_2[without_section_2['config'] == config]

    for quirk_type in quirk_patterns.keys():
        config_rate = config_data[quirk_type].mean()
        baseline_rate = quirk_analysis_df[quirk_type].mean()

        if baseline_rate > 0:
            spike = config_rate / baseline_rate
            if spike > 1.5:
                quirky_without_2.append({
                    'config': config,
                    'quirk': quirk_type,
                    'rate': config_rate,
                    'spike': spike
                })

if quirky_without_2:
    print("\nQuirks still present without Section 2:")
    for item in quirky_without_2:
        print(f"   {item['config']:20s} - {item['quirk']:10s}: {item['spike']:.1f}x baseline")
else:
    print("\n✅ NO quirks detected in configs without Section 2!")
    print("   Section 2 is the root cause of ALL quirks!")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)

print("\n🔍 Key Findings:")

# Calculate overall quirk reduction
total_with = sum(with_section_2[q].mean() for q in quirk_patterns.keys())
total_without = sum(without_section_2[q].mean() for q in quirk_patterns.keys())
overall_reduction = ((total_with - total_without) / total_with * 100) if total_with > 0 else 0

print(f"\n1. Overall quirk rate WITH Section 2: {total_with:.3f}")
print(f"2. Overall quirk rate WITHOUT Section 2: {total_without:.3f}")
print(f"3. Total reduction: {overall_reduction:.1f}%")

if overall_reduction > 30:
    print(f"\n🚨 MAJOR FINDING: Section 2 is responsible for {overall_reduction:.0f}% of quirk behavior!")
    print("   'Be kind and considerate' creates linguistic hesitation and over-explanation.")
elif overall_reduction > 10:
    print(f"\n✓ Section 2 contributes to quirks ({overall_reduction:.0f}% increase)")
else:
    print(f"\n✓ Section 2 has minimal impact on quirks")

print("\n✅ Analysis complete!")
