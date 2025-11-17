#!/usr/bin/env python3
"""Create visualizations for key findings"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from config import BATCH_EVALUATION_FILE, EVALUATION_DIMENSIONS

# Load data
print("📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# ============================================================================
# CHART 1: Config Win Distribution (the WOW finding)
# ============================================================================
print("Creating Chart 1: Config Win Distribution...")

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

# Count wins
config_win_counts = {}
for query, info in best_configs_per_query.items():
    config = info['config']
    config_win_counts[config] = config_win_counts.get(config, 0) + 1

# Sort and plot
sorted_wins = sorted(config_win_counts.items(), key=lambda x: x[1], reverse=True)
configs = [c for c, _ in sorted_wins]
wins = [w for _, w in sorted_wins]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Left: Bar chart of top configs
ax1.barh(range(len(configs[:15])), wins[:15], color='steelblue', edgecolor='black', linewidth=1.5)
ax1.set_yticks(range(len(configs[:15])))
ax1.set_yticklabels(configs[:15], fontsize=10)
ax1.set_xlabel('Number of Queries Won', fontsize=12, fontweight='bold')
ax1.set_title('🚨 WOW: No Config Dominates\nBest config only wins 16% of queries',
              fontsize=14, fontweight='bold', color='darkred')
ax1.axvline(len(queries) * 0.5, color='red', linestyle='--', linewidth=2, alpha=0.7,
            label=f'50% threshold ({len(queries)/2:.0f} wins)')
ax1.legend()
ax1.grid(axis='x', alpha=0.3)
ax1.invert_yaxis()

# Right: Distribution histogram
ax2.hist(wins, bins=range(0, max(wins)+2), color='coral', edgecolor='black', linewidth=1.5, alpha=0.7)
ax2.set_xlabel('Number of Wins', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Configs', fontsize=12, fontweight='bold')
ax2.set_title(f'Win Distribution Across {len(config_win_counts)} Winning Configs',
              fontsize=14, fontweight='bold')
ax2.grid(axis='y', alpha=0.3)
ax2.text(0.7, 0.9, f'{len(config_win_counts)} configs\nwon ≥1 query',
         transform=ax2.transAxes, fontsize=11,
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.tight_layout()
plt.savefig('images/config_win_distribution.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/config_win_distribution.png\n")

# ============================================================================
# CHART 2: Heatmap of Query vs Top Configs
# ============================================================================
print("Creating Chart 2: Query vs Config Performance Heatmap...")

# Get top 15 configs by overall score
config_scores = df.groupby('config_name')['evaluation_score'].mean().sort_values(ascending=False)
top_configs = config_scores.head(15).index.tolist()

# Create matrix: queries × top configs
matrix_data = []
query_labels = []
for i, query in enumerate(queries[:15]):  # Limit to 15 queries for readability
    row = []
    query_data = df[df['test_query'] == query]
    for config in top_configs:
        config_data = query_data[query_data['config_name'] == config]
        if len(config_data) > 0:
            row.append(config_data['evaluation_score'].mean())
        else:
            row.append(np.nan)
    matrix_data.append(row)
    # Truncate query text for label
    query_labels.append(query[:50] + '...' if len(query) > 50 else query)

matrix_df = pd.DataFrame(matrix_data, columns=top_configs, index=query_labels)

plt.figure(figsize=(14, 10))
sns.heatmap(matrix_df, annot=True, fmt='.0f', cmap='RdYlGn', center=87.6,
            vmin=84, vmax=91, linewidths=0.5, linecolor='gray',
            cbar_kws={'label': 'Score'})
plt.title('Query-Specific Config Performance\n(Shows optimal config varies by query)',
          fontsize=14, fontweight='bold', pad=20)
plt.xlabel('Config', fontsize=12, fontweight='bold')
plt.ylabel('Query (first 15)', fontsize=12, fontweight='bold')
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0, fontsize=8)
plt.tight_layout()
plt.savefig('images/query_config_heatmap.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/query_config_heatmap.png\n")

# ============================================================================
# NEW ANALYSIS: Section Frequency in Top Configs
# ============================================================================
print("="*70)
print("NEW ANALYSIS: Which Sections Appear in Winning Configs?")
print("="*70)

# Count section appearances in top configs
section_freq = {str(i): 0 for i in range(1, 7)}
for config in config_scores.head(20).index:
    sections = config.split('+')
    for section in sections:
        section_freq[section] = section_freq.get(section, 0) + 1

print("\n📊 Section Frequency in Top 20 Configs:")
for section, count in sorted(section_freq.items(), key=lambda x: int(x[0])):
    pct = (count / 20) * 100
    print(f"   Section {section}: {count}/20 ({pct:.0f}%)")

# Do the same for bottom configs
section_freq_bottom = {str(i): 0 for i in range(1, 7)}
for config in config_scores.tail(20).index:
    sections = config.split('+')
    for section in sections:
        section_freq_bottom[section] = section_freq_bottom.get(section, 0) + 1

print("\n📊 Section Frequency in Bottom 20 Configs:")
for section, count in sorted(section_freq_bottom.items(), key=lambda x: int(x[0])):
    pct = (count / 20) * 100
    print(f"   Section {section}: {count}/20 ({pct:.0f}%)")

# Calculate difference
print("\n💡 Section Impact (Top - Bottom):")
for section in sorted(section_freq.keys(), key=lambda x: int(x)):
    diff = section_freq[section] - section_freq_bottom.get(section, 0)
    if diff > 0:
        print(f"   Section {section}: +{diff} (appears MORE in top configs)")
    elif diff < 0:
        print(f"   Section {section}: {diff} (appears MORE in bottom configs)")
    else:
        print(f"   Section {section}: {diff} (neutral)")

# ============================================================================
# NEW ANALYSIS: Dimension-Specific Best Configs
# ============================================================================
print("\n" + "="*70)
print("NEW ANALYSIS: Best Config Per Dimension")
print("="*70)

dimension_best = {}
for dim in EVALUATION_DIMENSIONS:
    dim_keyword = dim.replace('_', ' ')
    dim_data = df[df['evaluation_question'].str.contains(dim_keyword, case=False, na=False)]
    dim_config_scores = dim_data.groupby('config_name')['evaluation_score'].mean()
    best_config = dim_config_scores.idxmax()
    best_score = dim_config_scores.max()
    dimension_best[dim] = {'config': best_config, 'score': best_score}
    print(f"   {dim:25s} → {best_config:20s} ({best_score:.1f})")

# Check if same config is best for all
unique_best_configs = set(info['config'] for info in dimension_best.values())
if len(unique_best_configs) == 1:
    print(f"\n✓ Expected: Same config ({list(unique_best_configs)[0]}) is best for all dimensions")
else:
    print(f"\n🚨 WOW: Different configs are best for different dimensions!")
    print(f"   {len(unique_best_configs)} different 'best' configs across {len(EVALUATION_DIMENSIONS)} dimensions")

# ============================================================================
# NEW ANALYSIS: Config Consistency (Variance)
# ============================================================================
print("\n" + "="*70)
print("NEW ANALYSIS: Config Consistency (Variance Analysis)")
print("="*70)

# Calculate variance for each config
config_variance = {}
config_mean = {}
for config in df['config_name'].unique():
    if pd.isna(config):
        continue
    config_data = df[df['config_name'] == config]
    scores = config_data['evaluation_score'].values
    config_variance[config] = np.var(scores)
    config_mean[config] = np.mean(scores)

# Sort by variance
sorted_variance = sorted(config_variance.items(), key=lambda x: x[1])

print("\n📊 Most Consistent Configs (low variance):")
for config, var in sorted_variance[:10]:
    std = np.sqrt(var)
    mean = config_mean[config]
    print(f"   {config:20s} → σ²={var:.1f} (σ={std:.1f}, μ={mean:.1f})")

print("\n📊 Most Volatile Configs (high variance):")
for config, var in sorted_variance[-10:]:
    std = np.sqrt(var)
    mean = config_mean[config]
    print(f"   {config:20s} → σ²={var:.1f} (σ={std:.1f}, μ={mean:.1f})")

# Check correlation between performance and variance
variances = [config_variance[c] for c in config_scores.index if c in config_variance]
means = [config_mean[c] for c in config_scores.index if c in config_variance]
correlation = np.corrcoef(means, variances)[0, 1]

print(f"\n📈 Correlation between performance and variance: r={correlation:.3f}")
if correlation > 0.3:
    print(f"   🚨 WOW: High performers are MORE volatile (adaptable)")
elif correlation < -0.3:
    print(f"   🚨 WOW: High performers are MORE consistent (reliable)")
else:
    print(f"   ✓ Expected: No strong relationship between performance and consistency")

# ============================================================================
# CHART 3: Consistency vs Performance
# ============================================================================
print("\nCreating Chart 3: Consistency vs Performance...")

fig, ax = plt.subplots(figsize=(10, 8))

stds = [np.sqrt(config_variance[c]) for c in config_scores.index if c in config_variance]
means = [config_mean[c] for c in config_scores.index if c in config_variance]

scatter = ax.scatter(means, stds, s=100, alpha=0.6, c=means, cmap='RdYlGn',
                     edgecolors='black', linewidth=1.5)

# Add regression line
z = np.polyfit(means, stds, 1)
p = np.poly1d(z)
x_line = np.linspace(min(means), max(means), 100)
ax.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2,
        label=f'Trend: r={correlation:.3f}')

ax.set_xlabel('Average Score', fontsize=12, fontweight='bold')
ax.set_ylabel('Standard Deviation (Consistency)', fontsize=12, fontweight='bold')
ax.set_title('Config Performance vs Consistency\n(Does being good = being adaptable?)',
            fontsize=14, fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)
plt.colorbar(scatter, label='Average Score')
plt.tight_layout()
plt.savefig('images/performance_vs_consistency.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/performance_vs_consistency.png\n")

print("\n" + "="*70)
print("✅ All analyses complete!")
print("="*70)
print("\nGenerated files:")
print("   1. images/config_win_distribution.png")
print("   2. images/query_config_heatmap.png")
print("   3. images/performance_vs_consistency.png")
print("   4. images/score_vs_sections.png (from previous script)")
