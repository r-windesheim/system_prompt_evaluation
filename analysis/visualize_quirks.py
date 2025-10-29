#!/usr/bin/env python3
"""Visualize detected behavioral quirks"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load quirk results
df = pd.read_csv('results/quirk_detection_results.csv')

print(f"Loaded {len(df)} detected quirks\n")

# Create visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

# Left: Spike ratio by config and quirk type
configs = df['config'].tolist()
quirks = df['quirk'].tolist()
spikes = df['spike_ratio'].tolist()

# Create labels
labels = [f"{c}\n({q})" for c, q in zip(configs, quirks)]

# Color by quirk type
quirk_colors = {
    'caveat': '#e74c3c',      # Red
    'example': '#3498db',     # Blue
    'hedge': '#f39c12',       # Orange
    'question': '#9b59b6',    # Purple
}
colors = [quirk_colors.get(q, 'gray') for q in quirks]

# Plot horizontal bar chart
y_pos = np.arange(len(labels))
bars = ax1.barh(y_pos, spikes, color=colors, edgecolor='black', linewidth=1.5)

ax1.set_yticks(y_pos)
ax1.set_yticklabels(labels, fontsize=9)
ax1.set_xlabel('Spike Ratio (Config Rate / Baseline)', fontsize=12, fontweight='bold')
ax1.set_title('🚨 Detected Behavioral Quirks\n(1.5x-2x baseline rate)',
             fontsize=14, fontweight='bold')
ax1.axvline(1.5, color='green', linestyle='--', linewidth=2, alpha=0.7,
           label='1.5x threshold')
ax1.axvline(2.0, color='red', linestyle='--', linewidth=2, alpha=0.7,
           label='2.0x threshold')
ax1.legend()
ax1.grid(axis='x', alpha=0.3)
ax1.invert_yaxis()

# Right: Quirk frequency across sections
# Map which sections appear in each config
section_quirk_counts = {str(i): {'caveat': 0, 'example': 0, 'hedge': 0, 'question': 0}
                        for i in range(1, 7)}

for idx, row in df.iterrows():
    config = row['config']
    quirk = row['quirk']
    sections = config.split('+')

    for section in sections:
        section_quirk_counts[section][quirk] += 1

# Create grouped bar chart
sections = sorted(section_quirk_counts.keys(), key=int)
quirk_types = ['caveat', 'example', 'hedge', 'question']

x = np.arange(len(sections))
width = 0.2

for i, quirk_type in enumerate(quirk_types):
    counts = [section_quirk_counts[s][quirk_type] for s in sections]
    ax2.bar(x + i*width, counts, width, label=quirk_type.title(),
           color=quirk_colors[quirk_type], edgecolor='black', linewidth=1)

ax2.set_xlabel('Section Number', fontsize=12, fontweight='bold')
ax2.set_ylabel('Quirk Count', fontsize=12, fontweight='bold')
ax2.set_title('Quirk Distribution by Section\n(Which sections trigger which quirks?)',
             fontsize=14, fontweight='bold')
ax2.set_xticks(x + width * 1.5)
ax2.set_xticklabels(sections)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('images/quirk_visualization.png', dpi=300, bbox_inches='tight')
print("✓ Saved: images/quirk_visualization.png\n")

# Print section analysis
print("="*70)
print("SECTION-QUIRK ANALYSIS")
print("="*70)

section_names = {
    '1': "Be brutally honest",
    '2': "Be kind and considerate",
    '3': "Provide complete information",
    '4': "Focus on practical advice",
    '5': "Point out flaws",
    '6': "Be encouraging"
}

print("\nWhich sections trigger which quirks?\n")
for section, quirks in sorted(section_quirk_counts.items(), key=lambda x: int(x[0])):
    total = sum(quirks.values())
    if total > 0:
        print(f"Section {section} ({section_names[section]}):")
        for quirk, count in sorted(quirks.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"   {quirk.title():15s}: {count} configs")
        print()

print("="*70)
print("KEY INSIGHTS")
print("="*70)

# Find which section appears most in quirky configs
section_frequency = {str(i): 0 for i in range(1, 7)}
for config in df['config']:
    sections = config.split('+')
    for section in sections:
        section_frequency[section] += 1

print("\nSections appearing most in quirky configs:")
for section, count in sorted(section_frequency.items(), key=lambda x: x[1], reverse=True):
    print(f"   Section {section} ({section_names[section]}): {count}/9 quirky configs")

# Find dominant quirks
quirk_totals = df.groupby('quirk').size().sort_values(ascending=False)
print("\nMost common quirk types:")
for quirk, count in quirk_totals.items():
    print(f"   {quirk.title()}: {count} configs")

print("\n✅ Visualization complete!")
