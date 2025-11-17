#!/usr/bin/env python3
"""Analyze response length patterns and section antagonism"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from config import BATCH_EVALUATION_FILE

# Load data
print("📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# ============================================================================
# ANALYSIS 1: Response Length Patterns
# ============================================================================
print("="*70)
print("ANALYSIS 1: Response Length vs Performance")
print("="*70)

# Calculate average score and word count per config
config_stats = df.groupby('config_name').agg({
    'evaluation_score': 'mean',
    'word_count': 'mean'
}).reset_index()

config_stats = config_stats.sort_values('evaluation_score', ascending=False)

print("\n📊 Top 10 Configs by Performance:")
for i, row in config_stats.head(10).iterrows():
    print(f"   {row['config_name']:20s} → Score: {row['evaluation_score']:.1f} | Words: {row['word_count']:.0f}")

print("\n📊 Bottom 10 Configs by Performance:")
for i, row in config_stats.tail(10).iterrows():
    print(f"   {row['config_name']:20s} → Score: {row['evaluation_score']:.1f} | Words: {row['word_count']:.0f}")

# Correlation
correlation = config_stats['evaluation_score'].corr(config_stats['word_count'])
print(f"\n📈 Correlation between score and word count: r={correlation:.3f}")

if correlation > 0.3:
    print(f"   🚨 WOW: Longer responses = Better scores!")
elif correlation < -0.3:
    print(f"   🚨 WOW: Shorter responses = Better scores!")
else:
    print(f"   ✓ Expected: Length doesn't predict performance")

# Split by performance tier
top_tier = config_stats.head(20)
bottom_tier = config_stats.tail(20)

print(f"\n📊 Word Count by Performance Tier:")
print(f"   Top 20 configs: {top_tier['word_count'].mean():.0f} ± {top_tier['word_count'].std():.0f} words")
print(f"   Bottom 20 configs: {bottom_tier['word_count'].mean():.0f} ± {bottom_tier['word_count'].std():.0f} words")
print(f"   Difference: {top_tier['word_count'].mean() - bottom_tier['word_count'].mean():.0f} words")

# ============================================================================
# CHART: Response Length vs Performance
# ============================================================================
print("\nCreating chart: Response Length vs Performance...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Left: Scatter plot
scatter = ax1.scatter(config_stats['word_count'], config_stats['evaluation_score'],
                     s=100, alpha=0.6, c=config_stats['evaluation_score'],
                     cmap='RdYlGn', edgecolors='black', linewidth=1.5)

# Add regression line
z = np.polyfit(config_stats['word_count'], config_stats['evaluation_score'], 1)
p = np.poly1d(z)
x_line = np.linspace(config_stats['word_count'].min(), config_stats['word_count'].max(), 100)
ax1.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2,
        label=f'Trend: r={correlation:.3f}')

ax1.set_xlabel('Average Response Length (words)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Average Score', fontsize=12, fontweight='bold')
ax1.set_title(f'Response Length vs Performance\n(r={correlation:.3f})',
             fontsize=14, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)
plt.colorbar(scatter, ax=ax1, label='Score')

# Right: Distribution comparison
ax2.hist(top_tier['word_count'], bins=15, alpha=0.7, label='Top 20 configs',
        color='green', edgecolor='black', linewidth=1.5)
ax2.hist(bottom_tier['word_count'], bins=15, alpha=0.7, label='Bottom 20 configs',
        color='red', edgecolor='black', linewidth=1.5)
ax2.axvline(top_tier['word_count'].mean(), color='darkgreen', linestyle='--',
           linewidth=2, label=f'Top mean: {top_tier["word_count"].mean():.0f}')
ax2.axvline(bottom_tier['word_count'].mean(), color='darkred', linestyle='--',
           linewidth=2, label=f'Bottom mean: {bottom_tier["word_count"].mean():.0f}')
ax2.set_xlabel('Average Response Length (words)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Configs', fontsize=12, fontweight='bold')
ax2.set_title('Word Count Distribution by Performance Tier',
             fontsize=14, fontweight='bold')
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('images/length_vs_performance.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/length_vs_performance.png\n")

# ============================================================================
# ANALYSIS 4: Section Antagonism
# ============================================================================
print("="*70)
print("ANALYSIS 4: Section Antagonism (Which sections avoid each other?)")
print("="*70)

# Build co-occurrence matrix
sections = ['1', '2', '3', '4', '5', '6']
cooccurrence = {s: {t: 0 for t in sections} for s in sections}
total_with_section = {s: 0 for s in sections}

for config in df['config_name'].unique():
    if pd.isna(config):
        continue
    config_sections = config.split('+')

    # Count total appearances
    for section in config_sections:
        if section in sections:
            total_with_section[section] += 1

    # Count co-occurrences
    for i, s1 in enumerate(config_sections):
        if s1 not in sections:
            continue
        for s2 in config_sections[i+1:]:
            if s2 not in sections:
                continue
            cooccurrence[s1][s2] += 1
            cooccurrence[s2][s1] += 1  # Symmetric

# Convert to expected vs observed
print("\n📊 Section Co-occurrence Analysis:")
print("   (Comparing actual co-occurrence vs. what we'd expect by chance)\n")

# Calculate expected co-occurrence based on individual frequencies
total_configs = len(df['config_name'].unique())
antagonism_scores = {}

for s1 in sections:
    for s2 in sections:
        if s1 >= s2:  # Skip diagonal and duplicates
            continue

        observed = cooccurrence[s1][s2]

        # Expected: P(s1 AND s2) = P(s1) * P(s2) * total_pairs
        # But we need to account for config size
        # Simple approach: expected = (freq_s1 * freq_s2) / total_configs
        expected = (total_with_section[s1] * total_with_section[s2]) / total_configs

        # Antagonism score: (expected - observed) / expected
        # Positive = antagonism (appear together LESS than expected)
        # Negative = synergy (appear together MORE than expected)
        if expected > 0:
            antagonism = (expected - observed) / expected
        else:
            antagonism = 0

        antagonism_scores[(s1, s2)] = {
            'observed': observed,
            'expected': expected,
            'antagonism': antagonism
        }

# Sort by antagonism score
sorted_antagonism = sorted(antagonism_scores.items(),
                          key=lambda x: x[1]['antagonism'],
                          reverse=True)

print("🔥 STRONGEST ANTAGONISMS (avoid each other):")
for (s1, s2), data in sorted_antagonism[:10]:
    print(f"   Section {s1} + Section {s2}:")
    print(f"      Observed: {data['observed']:.0f} | Expected: {data['expected']:.1f} | Antagonism: {data['antagonism']:.2f}")

print("\n💚 STRONGEST SYNERGIES (appear together often):")
for (s1, s2), data in sorted_antagonism[-10:]:
    print(f"   Section {s1} + Section {s2}:")
    print(f"      Observed: {data['observed']:.0f} | Expected: {data['expected']:.1f} | Synergy: {-data['antagonism']:.2f}")

# ============================================================================
# Build performance matrix for section pairs
# ============================================================================
print("\n📊 Performance of Section Pairs:")
print("   (Average score when both sections appear together)\n")

pair_performance = {}
for config_name in df['config_name'].unique():
    if pd.isna(config_name):
        continue
    config_sections = config_name.split('+')
    config_score = df[df['config_name'] == config_name]['evaluation_score'].mean()

    for i, s1 in enumerate(config_sections):
        if s1 not in sections:
            continue
        for s2 in config_sections[i+1:]:
            if s2 not in sections:
                continue
            pair = tuple(sorted([s1, s2]))
            if pair not in pair_performance:
                pair_performance[pair] = []
            pair_performance[pair].append(config_score)

# Calculate averages
pair_avg_performance = {pair: np.mean(scores) for pair, scores in pair_performance.items()}
sorted_pairs = sorted(pair_avg_performance.items(), key=lambda x: x[1], reverse=True)

print("🏆 BEST PERFORMING PAIRS:")
for (s1, s2), score in sorted_pairs[:10]:
    count = len(pair_performance[(s1, s2)])
    print(f"   Section {s1} + Section {s2}: {score:.1f} (n={count})")

print("\n📉 WORST PERFORMING PAIRS:")
for (s1, s2), score in sorted_pairs[-10:]:
    count = len(pair_performance[(s1, s2)])
    print(f"   Section {s1} + Section {s2}: {score:.1f} (n={count})")

# ============================================================================
# CHART: Section Antagonism Heatmap
# ============================================================================
print("\nCreating chart: Section Antagonism Heatmap...")

# Build antagonism matrix for heatmap
antagonism_matrix = np.zeros((6, 6))
for s1_idx, s1 in enumerate(sections):
    for s2_idx, s2 in enumerate(sections):
        if s1_idx == s2_idx:
            antagonism_matrix[s1_idx, s2_idx] = 0  # Diagonal
        else:
            pair = tuple(sorted([s1, s2]))
            if pair in antagonism_scores:
                antagonism_matrix[s1_idx, s2_idx] = antagonism_scores[pair]['antagonism']
            else:
                antagonism_matrix[s1_idx, s2_idx] = antagonism_scores.get((s2, s1), {}).get('antagonism', 0)

# Build performance matrix for heatmap
performance_matrix = np.zeros((6, 6))
for s1_idx, s1 in enumerate(sections):
    for s2_idx, s2 in enumerate(sections):
        if s1_idx == s2_idx:
            # Diagonal: single section performance
            single_configs = [c for c in df['config_name'].unique()
                            if pd.notna(c) and c == s1]
            if single_configs:
                performance_matrix[s1_idx, s2_idx] = df[df['config_name'].isin(single_configs)]['evaluation_score'].mean()
            else:
                performance_matrix[s1_idx, s2_idx] = np.nan
        else:
            pair = tuple(sorted([s1, s2]))
            if pair in pair_avg_performance:
                performance_matrix[s1_idx, s2_idx] = pair_avg_performance[pair]
            else:
                performance_matrix[s1_idx, s2_idx] = np.nan

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# Left: Antagonism heatmap
sns.heatmap(antagonism_matrix, annot=True, fmt='.2f', cmap='RdYlGn_r',
           center=0, xticklabels=sections, yticklabels=sections,
           linewidths=0.5, linecolor='gray', cbar_kws={'label': 'Antagonism Score'},
           ax=ax1)
ax1.set_title('Section Antagonism Matrix\n(Red = Avoid each other, Green = Synergy)',
             fontsize=14, fontweight='bold', pad=20)
ax1.set_xlabel('Section', fontsize=12, fontweight='bold')
ax1.set_ylabel('Section', fontsize=12, fontweight='bold')

# Right: Performance heatmap
sns.heatmap(performance_matrix, annot=True, fmt='.1f', cmap='RdYlGn',
           center=87.6, vmin=85, vmax=90, xticklabels=sections, yticklabels=sections,
           linewidths=0.5, linecolor='gray', cbar_kws={'label': 'Avg Score'},
           ax=ax2)
ax2.set_title('Section Pair Performance\n(Diagonal = single section, Off-diagonal = pairs)',
             fontsize=14, fontweight='bold', pad=20)
ax2.set_xlabel('Section', fontsize=12, fontweight='bold')
ax2.set_ylabel('Section', fontsize=12, fontweight='bold')

plt.tight_layout()
plt.savefig('images/section_antagonism.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/section_antagonism.png\n")

print("="*70)
print("✅ Analyses complete!")
print("="*70)
