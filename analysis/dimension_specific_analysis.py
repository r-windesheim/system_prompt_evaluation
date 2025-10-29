#!/usr/bin/env python3
"""Dimension-specific analysis - NO AVERAGING across dimensions"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from config import BATCH_EVALUATION_FILE, EVALUATION_DIMENSIONS

print("="*70)
print("DIMENSION-SPECIFIC ANALYSIS")
print("(Analyzing each dimension separately - no averaging!)")
print("="*70)

# Load data
print("\n📁 Loading data...")
df = pd.read_csv(BATCH_EVALUATION_FILE)
print(f"✓ Loaded {len(df)} evaluation results\n")

# Map evaluation questions to dimensions
def get_dimension(question):
    """Extract dimension from evaluation question"""
    for dim in EVALUATION_DIMENSIONS:
        dim_keyword = dim.replace('_', ' ')
        if dim_keyword.upper() in question.upper():
            return dim
    return None

df['dimension'] = df['evaluation_question'].apply(get_dimension)

# ============================================================================
# ANALYSIS 1: Section Impact PER DIMENSION
# ============================================================================
print("="*70)
print("ANALYSIS 1: Section Impact Per Dimension")
print("="*70)

# For each section, calculate its impact on each dimension
section_dimension_impact = {}

for section_num in range(1, 7):
    section_dimension_impact[section_num] = {}

    for dim in EVALUATION_DIMENSIONS:
        dim_data = df[df['dimension'] == dim]

        # Configs WITH this section
        with_section = dim_data[dim_data['config_name'].str.contains(f'(?:^|\\+){section_num}(?:\\+|$)',
                                                                      regex=True, na=False)]
        # Configs WITHOUT this section
        without_section = dim_data[~dim_data['config_name'].str.contains(f'(?:^|\\+){section_num}(?:\\+|$)',
                                                                          regex=True, na=False)]

        if len(with_section) > 0 and len(without_section) > 0:
            with_score = with_section['evaluation_score'].mean()
            without_score = without_section['evaluation_score'].mean()
            impact = with_score - without_score
            section_dimension_impact[section_num][dim] = {
                'with': with_score,
                'without': without_score,
                'impact': impact
            }

# Print section impacts
for section_num in range(1, 7):
    print(f"\n📊 SECTION {section_num} Impact by Dimension:")
    impacts = section_dimension_impact[section_num]

    # Sort by impact
    sorted_dims = sorted(impacts.items(), key=lambda x: x[1]['impact'], reverse=True)

    for dim, data in sorted_dims:
        impact = data['impact']
        symbol = "+" if impact > 0 else ""
        color = "🟢" if impact > 1 else "🔴" if impact < -1 else "⚪"
        print(f"   {color} {dim:25s}: {symbol}{impact:+.1f} points (with: {data['with']:.1f}, without: {data['without']:.1f})")

# ============================================================================
# ANALYSIS 2: Find Specialist vs Generalist Configs
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS 2: Specialist vs Generalist Configs")
print("="*70)

# Calculate variance across dimensions for each config
config_dimension_scores = {}

for config in df['config_name'].unique():
    if pd.isna(config):
        continue

    config_data = df[df['config_name'] == config]
    dimension_scores = {}

    for dim in EVALUATION_DIMENSIONS:
        dim_data = config_data[config_data['dimension'] == dim]
        if len(dim_data) > 0:
            dimension_scores[dim] = dim_data['evaluation_score'].mean()

    if len(dimension_scores) == 6:  # Only if we have all dimensions
        scores = list(dimension_scores.values())
        config_dimension_scores[config] = {
            'scores': dimension_scores,
            'mean': np.mean(scores),
            'variance': np.var(scores),
            'std': np.std(scores),
            'range': max(scores) - min(scores)
        }

# Sort by variance
sorted_by_variance = sorted(config_dimension_scores.items(),
                           key=lambda x: x[1]['variance'],
                           reverse=True)

print("\n🎯 SPECIALISTS (high variance = different scores across dimensions):")
for config, stats in sorted_by_variance[:10]:
    print(f"\n   {config:20s} | Variance: {stats['variance']:.1f} | Range: {stats['range']:.1f}")
    for dim, score in sorted(stats['scores'].items(), key=lambda x: x[1], reverse=True):
        print(f"      {dim:25s}: {score:.1f}")

print("\n⚖️  GENERALISTS (low variance = consistent across dimensions):")
for config, stats in sorted_by_variance[-10:]:
    print(f"\n   {config:20s} | Variance: {stats['variance']:.1f} | Range: {stats['range']:.1f}")
    for dim, score in sorted(stats['scores'].items(), key=lambda x: x[1], reverse=True):
        print(f"      {dim:25s}: {score:.1f}")

# ============================================================================
# ANALYSIS 3: Best Config Per Dimension
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS 3: Best Config Per Dimension")
print("="*70)

dimension_rankings = {}

for dim in EVALUATION_DIMENSIONS:
    dim_data = df[df['dimension'] == dim]
    config_scores = dim_data.groupby('config_name')['evaluation_score'].mean().sort_values(ascending=False)

    dimension_rankings[dim] = config_scores

    print(f"\n🏆 {dim} - Top 5 Configs:")
    for i, (config, score) in enumerate(config_scores.head(5).items(), 1):
        print(f"   {i}. {config:20s} → {score:.1f}")

    print(f"\n📉 {dim} - Bottom 5 Configs:")
    for i, (config, score) in enumerate(config_scores.tail(5).items(), 1):
        print(f"   {i}. {config:20s} → {score:.1f}")

# ============================================================================
# ANALYSIS 4: Section 6 Impact Analysis (the toxic section)
# ============================================================================
print("\n" + "="*70)
print("ANALYSIS 4: Section 6 Deep Dive (Why is it toxic?)")
print("="*70)

for dim in EVALUATION_DIMENSIONS:
    dim_data = df[df['dimension'] == dim]

    with_6 = dim_data[dim_data['config_name'].str.contains('6', na=False)]
    without_6 = dim_data[~dim_data['config_name'].str.contains('6', na=False)]

    if len(with_6) > 0 and len(without_6) > 0:
        with_score = with_6['evaluation_score'].mean()
        without_score = without_6['evaluation_score'].mean()
        impact = with_score - without_score

        symbol = "🔴" if impact < -0.5 else "🟡" if impact < 0 else "🟢"
        print(f"{symbol} {dim:25s}: {impact:+.1f} points (with S6: {with_score:.1f}, without: {without_score:.1f})")

# ============================================================================
# CHART 1: Section Impact Heatmap (per dimension)
# ============================================================================
print("\nCreating Chart 1: Section Impact by Dimension...")

impact_matrix = np.zeros((6, 6))  # 6 sections × 6 dimensions

for section_idx, section_num in enumerate(range(1, 7)):
    for dim_idx, dim in enumerate(EVALUATION_DIMENSIONS):
        if dim in section_dimension_impact[section_num]:
            impact_matrix[section_idx, dim_idx] = section_dimension_impact[section_num][dim]['impact']

fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(impact_matrix, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
           xticklabels=[d.replace('_', ' ').replace(' ', '\n') for d in EVALUATION_DIMENSIONS],
           yticklabels=[f'Section {i}' for i in range(1, 7)],
           linewidths=0.5, linecolor='gray', cbar_kws={'label': 'Impact (points)'},
           vmin=-3, vmax=3)
ax.set_title('Section Impact by Dimension\n(Green = Helps, Red = Hurts)',
            fontsize=14, fontweight='bold', pad=20)
ax.set_xlabel('Dimension', fontsize=12, fontweight='bold')
ax.set_ylabel('Section', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('images/section_impact_by_dimension.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/section_impact_by_dimension.png")

# ============================================================================
# CHART 2: Specialist vs Generalist Scatter
# ============================================================================
print("\nCreating Chart 2: Specialist vs Generalist Plot...")

variances = [stats['variance'] for stats in config_dimension_scores.values()]
means = [stats['mean'] for stats in config_dimension_scores.values()]
ranges = [stats['range'] for stats in config_dimension_scores.values()]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Left: Variance vs Mean
scatter1 = ax1.scatter(means, variances, s=100, alpha=0.6, c=variances,
                      cmap='coolwarm', edgecolors='black', linewidth=1.5)
ax1.set_xlabel('Average Score (across dimensions)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Variance Across Dimensions', fontsize=12, fontweight='bold')
ax1.set_title('Specialist vs Generalist Configs\n(High variance = Specialist)',
             fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)

# Add labels for extremes
top_specialist = sorted_by_variance[0]
top_generalist = sorted_by_variance[-1]
ax1.annotate(f'{top_specialist[0]}\n(Specialist)',
            xy=(top_specialist[1]['mean'], top_specialist[1]['variance']),
            xytext=(10, 10), textcoords='offset points',
            bbox=dict(boxstyle='round', facecolor='red', alpha=0.7),
            fontsize=9, fontweight='bold')
ax1.annotate(f'{top_generalist[0]}\n(Generalist)',
            xy=(top_generalist[1]['mean'], top_generalist[1]['variance']),
            xytext=(10, -20), textcoords='offset points',
            bbox=dict(boxstyle='round', facecolor='green', alpha=0.7),
            fontsize=9, fontweight='bold')

plt.colorbar(scatter1, ax=ax1, label='Variance')

# Right: Range distribution
ax2.hist(ranges, bins=20, color='steelblue', edgecolor='black', linewidth=1.5, alpha=0.7)
ax2.axvline(np.median(ranges), color='red', linestyle='--', linewidth=2,
           label=f'Median: {np.median(ranges):.1f}')
ax2.set_xlabel('Score Range (Max - Min across dimensions)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Configs', fontsize=12, fontweight='bold')
ax2.set_title('Distribution of Specialization\n(Larger range = More specialized)',
             fontsize=14, fontweight='bold')
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('images/specialist_vs_generalist.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/specialist_vs_generalist.png")

# ============================================================================
# CHART 3: Dimension Rankings - Who wins each dimension?
# ============================================================================
print("\nCreating Chart 3: Dimension Rankings Comparison...")

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
axes = axes.flatten()

for idx, dim in enumerate(EVALUATION_DIMENSIONS):
    ax = axes[idx]

    top_configs = dimension_rankings[dim].head(10)
    configs = [c[:15] for c in top_configs.index]  # Truncate names
    scores = top_configs.values

    bars = ax.barh(range(len(configs)), scores, color='steelblue',
                   edgecolor='black', linewidth=1.5)

    # Color the bars by score
    for i, (bar, score) in enumerate(zip(bars, scores)):
        if score > 90:
            bar.set_color('green')
        elif score < 85:
            bar.set_color('red')

    ax.set_yticks(range(len(configs)))
    ax.set_yticklabels(configs, fontsize=9)
    ax.set_xlabel('Score', fontsize=10, fontweight='bold')
    ax.set_title(f'{dim.replace("_", " ")}', fontsize=11, fontweight='bold')
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3)
    ax.set_xlim(min(scores) - 1, max(scores) + 1)

plt.tight_layout()
plt.savefig('images/dimension_rankings.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/dimension_rankings.png")

# ============================================================================
# SUMMARY: Key Findings
# ============================================================================
print("\n" + "="*70)
print("KEY FINDINGS")
print("="*70)

# Find which section helps/hurts each dimension most
print("\n🔍 Which section matters most for each dimension?\n")
for dim in EVALUATION_DIMENSIONS:
    impacts = []
    for section_num in range(1, 7):
        if dim in section_dimension_impact[section_num]:
            impact = section_dimension_impact[section_num][dim]['impact']
            impacts.append((section_num, impact))

    impacts.sort(key=lambda x: abs(x[1]), reverse=True)
    best = max(impacts, key=lambda x: x[1])
    worst = min(impacts, key=lambda x: x[1])

    print(f"{dim:25s}")
    print(f"   🟢 Best:  Section {best[0]} ({best[1]:+.1f} points)")
    print(f"   🔴 Worst: Section {worst[0]} ({worst[1]:+.1f} points)")

# Specialist performance
print("\n🎯 Do specialists outperform generalists?\n")
top_10_specialists = sorted_by_variance[:10]
top_10_generalists = sorted_by_variance[-10:]

specialist_avg = np.mean([s[1]['mean'] for s in top_10_specialists])
generalist_avg = np.mean([s[1]['mean'] for s in top_10_generalists])

print(f"   Top 10 Specialists avg: {specialist_avg:.1f}")
print(f"   Top 10 Generalists avg: {generalist_avg:.1f}")
print(f"   Difference: {specialist_avg - generalist_avg:+.1f}")

if specialist_avg > generalist_avg + 0.5:
    print(f"   🚨 WOW: Specialists outperform generalists!")
elif generalist_avg > specialist_avg + 0.5:
    print(f"   🚨 WOW: Generalists outperform specialists!")
else:
    print(f"   ✓ Expected: No clear advantage")

print("\n" + "="*70)
print("✅ Dimension-specific analysis complete!")
print("="*70)
