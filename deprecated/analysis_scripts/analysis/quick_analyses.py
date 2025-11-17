#!/usr/bin/env python3
"""Quick analyses: baseline performance, best configs, section count effects"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from config import BATCH_EVALUATION_FILE

# Load data
print("📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# ============================================================================
# ANALYSIS 1: Does baseline (no sections) beat everything?
# ============================================================================
print("="*70)
print("ANALYSIS 1: Baseline vs All Combinations")
print("="*70)

# Calculate average score per config
config_scores = df.groupby('config_name')['evaluation_score'].mean().sort_values(ascending=False)

# Find baseline (should be empty or minimal sections)
# Look for configs with minimal section count
section_counts = {}
for config in df['config_name'].unique():
    if pd.isna(config) or config == 'nan':
        continue
    # Count sections by counting commas in section_indices + 1
    config_data = df[df['config_name'] == config].iloc[0]
    if 'section_indices' in config_data and pd.notna(config_data['section_indices']):
        indices = str(config_data['section_indices'])
        count = len(indices.split(',')) if ',' in indices else 1
    else:
        count = len(config.split(',')) if ',' in config else 1
    section_counts[config] = count

# Find single-section configs (closest to "baseline")
single_section_configs = [c for c, count in section_counts.items() if count == 1]

print(f"\n📊 Performance Overview:")
print(f"   Total configs tested: {len(config_scores)}")
print(f"   Overall average score: {df['evaluation_score'].mean():.1f}/100")
print(f"\n🏆 TOP 10 CONFIGS:")
for i, (config, score) in enumerate(config_scores.head(10).items(), 1):
    sections = section_counts.get(config, '?')
    print(f"   {i:2d}. {config:20s} → {score:.1f} ({sections} sections)")

print(f"\n📉 BOTTOM 10 CONFIGS:")
for i, (config, score) in enumerate(config_scores.tail(10).items(), 1):
    sections = section_counts.get(config, '?')
    print(f"   {i:2d}. {config:20s} → {score:.1f} ({sections} sections)")

# Compare single-section vs multi-section
if single_section_configs:
    single_scores = [config_scores[c] for c in single_section_configs]
    multi_configs = [c for c in config_scores.index if section_counts.get(c, 0) > 1]
    multi_scores = [config_scores[c] for c in multi_configs]

    print(f"\n📊 Single Section vs Multi-Section:")
    print(f"   Single-section avg: {np.mean(single_scores):.1f}")
    print(f"   Multi-section avg: {np.mean(multi_scores):.1f}")
    print(f"   Difference: {np.mean(multi_scores) - np.mean(single_scores):.1f} points")

    if np.mean(single_scores) > np.mean(multi_scores):
        print(f"   🚨 WOW: Single sections outperform combinations!")
    else:
        print(f"   ✓ Expected: More sections = better performance")

# ============================================================================
# ANALYSIS 2: Find best config per query
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS 2: Best Config Per Query")
print("="*70)

# Get unique queries
queries = df['test_query'].unique()

best_configs_per_query = {}
for query in queries:
    query_data = df[df['test_query'] == query]
    query_config_scores = query_data.groupby('config_name')['evaluation_score'].mean()
    best_config = query_config_scores.idxmax()
    best_score = query_config_scores.max()
    best_configs_per_query[query] = {
        'config': best_config,
        'score': best_score
    }

# Count how often each config is "best"
config_win_counts = {}
for query, info in best_configs_per_query.items():
    config = info['config']
    config_win_counts[config] = config_win_counts.get(config, 0) + 1

# Sort by win count
sorted_wins = sorted(config_win_counts.items(), key=lambda x: x[1], reverse=True)

print(f"\n🏆 Config Win Counts (how many queries each config won):")
print(f"   Total queries: {len(queries)}")
for i, (config, wins) in enumerate(sorted_wins[:10], 1):
    pct = (wins / len(queries)) * 100
    sections = section_counts.get(config, '?')
    print(f"   {i:2d}. {config:20s} → {wins:2d} wins ({pct:5.1f}%) | {sections} sections")

# Check if one config dominates
top_winner_pct = (sorted_wins[0][1] / len(queries)) * 100
if top_winner_pct > 50:
    print(f"\n✓ Expected: One config ({sorted_wins[0][0]}) wins {top_winner_pct:.1f}% of queries")
else:
    print(f"\n🚨 WOW: No single config dominates! Best only wins {top_winner_pct:.1f}% of queries")
    print(f"   → Optimal config is highly query-dependent!")

# ============================================================================
# ANALYSIS 3: Plot score vs # sections
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS 3: Score vs Number of Sections")
print("="*70)

# Calculate average score by section count
section_count_scores = {}
for config, score in config_scores.items():
    count = section_counts.get(config, 0)
    if count not in section_count_scores:
        section_count_scores[count] = []
    section_count_scores[count].append(score)

# Calculate means and stds
section_counts_sorted = sorted(section_count_scores.keys())
means = [np.mean(section_count_scores[c]) for c in section_counts_sorted]
stds = [np.std(section_count_scores[c]) for c in section_counts_sorted]

print(f"\n📊 Average Score by Section Count:")
for count, mean, std in zip(section_counts_sorted, means, stds):
    n = len(section_count_scores[count])
    print(f"   {count} sections: {mean:.1f} ± {std:.1f} (n={n})")

# Check for nonlinear effects
if len(means) > 2:
    # Calculate differences between consecutive points
    diffs = [means[i+1] - means[i] for i in range(len(means)-1)]
    print(f"\n📈 Changes between consecutive section counts:")
    for i, diff in enumerate(diffs):
        print(f"   {section_counts_sorted[i]}→{section_counts_sorted[i+1]} sections: {diff:+.1f} points")

    # Check for big jumps
    max_jump = max(abs(d) for d in diffs)
    if max_jump > 3:
        jump_idx = [i for i, d in enumerate(diffs) if abs(d) == max_jump][0]
        print(f"\n🚨 WOW: Largest jump is {max_jump:.1f} points at {section_counts_sorted[jump_idx]}→{section_counts_sorted[jump_idx+1]} sections")
        print(f"   → Nonlinear threshold effect detected!")
    else:
        print(f"\n✓ Expected: Gradual changes (max change: {max_jump:.1f} points)")

# Create plot
plt.figure(figsize=(10, 6))
plt.errorbar(section_counts_sorted, means, yerr=stds,
             marker='o', markersize=10, linewidth=2, capsize=5, capthick=2)
plt.xlabel('Number of Prompt Sections', fontsize=12, fontweight='bold')
plt.ylabel('Average Score', fontsize=12, fontweight='bold')
plt.title('Score vs Number of Sections\n(Error bars = ±1 std dev)', fontsize=14, fontweight='bold')
plt.grid(True, alpha=0.3)
plt.tight_layout()

output_path = 'images/score_vs_sections.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"\n📊 Plot saved to: {output_path}")

# Summary
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print("\n🔍 Key Findings:")
print(f"   1. Best overall config: {config_scores.idxmax()} ({config_scores.max():.1f} points)")
print(f"   2. Most versatile config (wins most queries): {sorted_wins[0][0]} ({sorted_wins[0][1]} wins)")
print(f"   3. Optimal section count: {section_counts_sorted[means.index(max(means))]} sections ({max(means):.1f} avg score)")
