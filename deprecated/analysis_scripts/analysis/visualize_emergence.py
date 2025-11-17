#!/usr/bin/env python3
"""
Visualize Emergent Behaviors

Creates compelling visualizations showing:
1. Subset testing tree (how we detected emergence)
2. Emergence waterfall charts
3. Comparison of emergent vs additive behaviors
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import seaborn as sns
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*70)
print("VISUALIZING EMERGENT BEHAVIORS")
print("="*70)
print()

# Load causality results
print("📁 Loading causality tracing results...")
df = pd.read_csv('results/causality_tracing.csv')
print(f"✓ Loaded {len(df)} causality results\n")

# ============================================================================
# FIGURE 1: EMERGENCE WATERFALL - THE STAR EXAMPLE (2+4+5 → Caveat)
# ============================================================================

print("Creating Figure 1: Emergence Waterfall (2+4+5 → Caveat)...")

# Get the star example
star = df[df['classification'] == 'EMERGENT'].iloc[0]

fig, ax = plt.subplots(figsize=(14, 8))

# Data for waterfall
stages = [
    'Baseline',
    'Section 2\nalone',
    'Section 4\nalone',
    'Section 5\nalone',
    'Best Pair\n(4+5)',
    'Full Config\n(2+4+5)\n⭐ EMERGENT'
]

# Values for caveat rate
values = [
    star['baseline'],           # 0.327
    0.345,                      # Section 2
    0.332,                      # Section 4
    0.370,                      # Section 5
    0.397,                      # Best pair (4+5)
    star['observed_rate']       # 0.657
]

colors = ['gray', 'lightblue', 'lightblue', 'lightblue', 'orange', 'red']

# Create bars
bars = ax.bar(range(len(stages)), values, color=colors, edgecolor='black', linewidth=2)

# Add value labels on bars
for i, (bar, val) in enumerate(zip(bars, values)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
            f'{val:.3f}',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

# Add emergence annotation
ax.annotate('', xy=(5, values[5]), xytext=(4, values[4]),
            arrowprops=dict(arrowstyle='->', lw=3, color='red'))
ax.text(4.5, (values[4] + values[5])/2,
        f'+65% JUMP\nEMERGENCE!',
        ha='center', va='center', fontsize=12, fontweight='bold',
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

# Baseline reference line
ax.axhline(y=star['baseline'], color='gray', linestyle='--', alpha=0.5, linewidth=2)
ax.text(0.5, star['baseline'] - 0.03, 'Baseline', fontsize=10, color='gray')

# Expected additive line (max of subsets)
ax.axhline(y=0.397, color='orange', linestyle='--', alpha=0.7, linewidth=2)
ax.text(3.5, 0.397 + 0.02, 'Expected from subsets', fontsize=10, color='orange')

ax.set_xticks(range(len(stages)))
ax.set_xticklabels(stages, fontsize=11)
ax.set_ylabel('Caveat Rate (per 100 words)', fontsize=13, fontweight='bold')
ax.set_title('🚨 EMERGENT BEHAVIOR DETECTED: Caveat Syndrome\n' +
             'Config 2+4+5 shows 2.0x baseline (0.657) despite no subset exceeding 0.397',
             fontsize=15, fontweight='bold', pad=20)
ax.set_ylim(0, 0.75)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('analysis/images/emergence_waterfall.png', dpi=300, bbox_inches='tight')
print("✓ Saved: analysis/images/emergence_waterfall.png\n")

# ============================================================================
# FIGURE 2: SUBSET TESTING TREE
# ============================================================================

print("Creating Figure 2: Subset Testing Tree...")

fig, ax = plt.subplots(figsize=(16, 10))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Define positions for tree nodes
positions = {
    # Level 0: Individual sections
    '2': (1, 2), '4': (5, 2), '5': (9, 2),
    # Level 1: Pairs
    '2+4': (2, 5), '2+5': (5, 5), '4+5': (8, 5),
    # Level 2: Full config
    '2+4+5': (5, 8)
}

# Values for each config
config_values = {
    '2': 0.345, '4': 0.332, '5': 0.370,
    '2+4': 0.281, '2+5': 0.341, '4+5': 0.397,
    '2+4+5': 0.657
}

# Draw nodes
for config, (x, y) in positions.items():
    value = config_values[config]

    # Color based on level
    if config == '2+4+5':
        color = 'red'
        size = 1200
    elif '+' in config and len(config.split('+')) == 2:
        color = 'orange'
        size = 1000
    else:
        color = 'lightblue'
        size = 1000

    ax.scatter(x, y, s=size, color=color, edgecolor='black', linewidth=2, zorder=3)
    ax.text(x, y, f'{config}\n{value:.3f}',
            ha='center', va='center', fontsize=11, fontweight='bold')

# Draw arrows (edges)
edges = [
    ('2', '2+4'), ('4', '2+4'),
    ('2', '2+5'), ('5', '2+5'),
    ('4', '4+5'), ('5', '4+5'),
    ('2+4', '2+4+5'), ('2+5', '2+4+5'), ('4+5', '2+4+5')
]

for start, end in edges:
    x1, y1 = positions[start]
    x2, y2 = positions[end]
    ax.annotate('', xy=(x2, y2-0.4), xytext=(x1, y1+0.4),
                arrowprops=dict(arrowstyle='->', lw=1.5, color='gray', alpha=0.6))

# Add labels
ax.text(5, 0.5, 'Individual Sections\n(No Emergence)',
        ha='center', fontsize=12, fontweight='bold', color='blue')
ax.text(5, 3.5, 'Section Pairs\n(Still No Emergence)',
        ha='center', fontsize=12, fontweight='bold', color='darkorange')
ax.text(5, 9.5, '⭐ FULL CONFIG: EMERGENCE! ⭐\nJump from 0.397 → 0.657 (+65%)',
        ha='center', fontsize=13, fontweight='bold', color='red',
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7, pad=0.5))

# Add title
ax.text(5, 10.8, 'Subset Testing Tree: How We Detected Emergence',
        ha='center', fontsize=16, fontweight='bold')

plt.tight_layout()
plt.savefig('analysis/images/emergence_tree.png', dpi=300, bbox_inches='tight')
print("✓ Saved: analysis/images/emergence_tree.png\n")

# ============================================================================
# FIGURE 3: CLASSIFICATION OVERVIEW
# ============================================================================

print("Creating Figure 3: Classification Overview...")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# Left: Pie chart of classifications
classification_counts = df['classification'].value_counts()
colors_pie = ['#ff4444', '#ff8800', '#4444ff', '#888888']
explode = [0.1 if c == 'EMERGENT' else 0.05 if c == 'SYNERGISTIC' else 0
           for c in classification_counts.index]

wedges, texts, autotexts = ax1.pie(classification_counts,
                                     labels=classification_counts.index,
                                     autopct='%1.1f%%',
                                     colors=colors_pie,
                                     explode=explode,
                                     startangle=90,
                                     textprops={'fontsize': 12, 'fontweight': 'bold'})

ax1.set_title('Causality Classification\n50% Show Non-Linear Behavior!',
             fontsize=14, fontweight='bold', pad=20)

# Right: Emergence score comparison
emergent = df[df['classification'] == 'EMERGENT'].sort_values('emergence_score', ascending=False)
synergistic = df[df['classification'] == 'SYNERGISTIC'].sort_values('emergence_score', ascending=False)
additive = df[df['classification'] == 'ADDITIVE'].sort_values('emergence_score', ascending=False, key=abs)

y_pos = 0
y_positions = {}
labels = []
scores = []
colors_bar = []

# Plot emergent
for idx, row in emergent.iterrows():
    label = f"{row['config']} → {row['quirk']}"
    labels.append(label)
    scores.append(row['emergence_score'])
    colors_bar.append('#ff4444')
    y_positions[label] = y_pos
    y_pos += 1

# Plot synergistic
for idx, row in synergistic.iterrows():
    label = f"{row['config']} → {row['quirk']}"
    labels.append(label)
    scores.append(row['emergence_score'])
    colors_bar.append('#ff8800')
    y_positions[label] = y_pos
    y_pos += 1

# Plot additive
for idx, row in additive.iterrows():
    label = f"{row['config']} → {row['quirk']}"
    labels.append(label)
    scores.append(row['emergence_score'])
    colors_bar.append('#4444ff')
    y_positions[label] = y_pos
    y_pos += 1

ax2.barh(range(len(labels)), scores, color=colors_bar, edgecolor='black', linewidth=1.5)
ax2.set_yticks(range(len(labels)))
ax2.set_yticklabels(labels, fontsize=9)
ax2.set_xlabel('Emergence Score', fontsize=12, fontweight='bold')
ax2.set_title('Emergence Scores by Behavior\n(Higher = More Emergent)',
             fontsize=14, fontweight='bold', pad=20)
ax2.axvline(x=0.5, color='red', linestyle='--', alpha=0.5, linewidth=2,
           label='Emergence Threshold')
ax2.axvline(x=0.2, color='orange', linestyle='--', alpha=0.5, linewidth=2,
           label='Synergy Threshold')
ax2.legend(fontsize=10)
ax2.grid(axis='x', alpha=0.3)
ax2.invert_yaxis()

plt.tight_layout()
plt.savefig('analysis/images/emergence_classification.png', dpi=300, bbox_inches='tight')
print("✓ Saved: analysis/images/emergence_classification.png\n")

# ============================================================================
# FIGURE 4: EMERGENCE vs BASELINE
# ============================================================================

print("Creating Figure 4: Emergence vs Baseline Comparison...")

fig, ax = plt.subplots(figsize=(14, 8))

# Get emergent and synergistic behaviors
non_linear = df[df['classification'].isin(['EMERGENT', 'SYNERGISTIC'])].sort_values('emergence_score', ascending=False)

configs = [f"{row['config']}\n{row['quirk']}" for _, row in non_linear.iterrows()]
baseline_values = [row['baseline'] for _, row in non_linear.iterrows()]
observed_values = [row['observed_rate'] for _, row in non_linear.iterrows()]

x = np.arange(len(configs))
width = 0.35

bars1 = ax.bar(x - width/2, baseline_values, width, label='Baseline',
               color='gray', alpha=0.7, edgecolor='black', linewidth=1.5)
bars2 = ax.bar(x + width/2, observed_values, width, label='Observed (Full Config)',
               color='red', alpha=0.8, edgecolor='black', linewidth=1.5)

# Add spike ratio annotations
for i, (_, row) in enumerate(non_linear.iterrows()):
    spike = row['spike_ratio']
    ax.text(i, max(baseline_values[i], observed_values[i]) + 0.05,
            f'{spike:.1f}x',
            ha='center', va='bottom', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

ax.set_xlabel('Config → Quirk', fontsize=12, fontweight='bold')
ax.set_ylabel('Quirk Rate (per 100 words)', fontsize=12, fontweight='bold')
ax.set_title('Non-Linear Behaviors: Observed vs Baseline\n(Red bars exceed what individual sections predict)',
            fontsize=15, fontweight='bold', pad=20)
ax.set_xticks(x)
ax.set_xticklabels(configs, fontsize=10, rotation=0)
ax.legend(fontsize=12)
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('analysis/images/emergence_comparison.png', dpi=300, bbox_inches='tight')
print("✓ Saved: analysis/images/emergence_comparison.png\n")

# ============================================================================
# SUMMARY
# ============================================================================

print("="*70)
print("VISUALIZATION SUMMARY")
print("="*70)
print()
print("Generated 4 figures:")
print("  1. analysis/images/emergence_waterfall.png - Shows 2+4+5 caveat emergence")
print("  2. analysis/images/emergence_tree.png - Subset testing tree diagram")
print("  3. analysis/images/emergence_classification.png - Classification overview")
print("  4. analysis/images/emergence_comparison.png - Non-linear behaviors vs baseline")
print()
print("="*70)
print("✅ Visualization complete!")
print("="*70)
