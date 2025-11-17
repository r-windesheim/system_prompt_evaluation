#!/usr/bin/env python3
"""
Dimension Warfare Detector

Discovers which evaluation dimensions have zero-sum tradeoffs:
When optimizing dimension A inevitably makes dimension B worse.

This reveals fundamental constraints in AI behavior - you can't have it all!
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr
from pathlib import Path

from config import BATCH_EVALUATION_FILE, EVALUATION_DIMENSIONS


def extract_dimension_scores(df):
    """
    Build a matrix: rows=configs, columns=dimensions, values=scores

    Returns:
        DataFrame with configs as rows, dimensions as columns
    """
    configs = df['config_name'].unique()
    configs = [c for c in configs if c and c != 'nan']

    dimension_matrix = []

    for config in configs:
        row = {'config': config}
        config_data = df[df['config_name'] == config]

        for dim in EVALUATION_DIMENSIONS:
            # Match dimension in evaluation_question column
            dim_keyword = dim.replace('_', ' ')
            dim_data = config_data[
                config_data['evaluation_question'].str.contains(dim_keyword, case=False, na=False)
            ]

            if len(dim_data) > 0:
                row[dim] = dim_data['evaluation_score'].mean()
            else:
                row[dim] = np.nan

        dimension_matrix.append(row)

    return pd.DataFrame(dimension_matrix)


def detect_dimension_warfare(dimension_matrix):
    """
    Find pairs of dimensions with strong negative correlation

    Args:
        dimension_matrix: DataFrame with dimensions as columns

    Returns:
        List of warfare pairs with statistics
    """
    warfare_pairs = []

    for i, dim1 in enumerate(EVALUATION_DIMENSIONS):
        for j, dim2 in enumerate(EVALUATION_DIMENSIONS[i+1:], i+1):
            # Get scores for both dimensions
            valid_data = dimension_matrix[[dim1, dim2]].dropna()

            if len(valid_data) < 10:  # Need sufficient data
                continue

            scores1 = valid_data[dim1].values
            scores2 = valid_data[dim2].values

            # Calculate correlation
            corr, p_value = pearsonr(scores1, scores2)

            # Detect warfare (strong negative correlation)
            if corr < -0.5:  # Threshold for warfare
                # Classify severity
                if corr < -0.8:
                    severity = "SEVERE"
                    interpretation = f"⚔️ ZERO-SUM: Optimizing {dim1} destroys {dim2}"
                elif corr < -0.7:
                    severity = "STRONG"
                    interpretation = f"⚠️ CONFLICT: {dim1} and {dim2} strongly oppose each other"
                else:
                    severity = "MODERATE"
                    interpretation = f"⚡ TENSION: {dim1} and {dim2} have significant tradeoff"

                warfare_pairs.append({
                    'dim1': dim1,
                    'dim2': dim2,
                    'correlation': corr,
                    'p_value': p_value,
                    'severity': severity,
                    'interpretation': interpretation,
                    'n_configs': len(valid_data)
                })

    # Sort by correlation strength (most negative first)
    warfare_pairs.sort(key=lambda x: x['correlation'])

    return warfare_pairs


def validate_warfare(df, dim1, dim2):
    """
    Validate that warfare is real, not spurious

    Checks:
    1. Consistency across data splits
    2. Linear relationship (not just extreme values)

    Returns:
        Validation results with confidence score
    """
    # Build dimension matrix for validation
    dimension_matrix = extract_dimension_scores(df)
    valid_data = dimension_matrix[[dim1, dim2, 'config']].dropna()

    if len(valid_data) < 20:
        return {'validated': False, 'reason': 'Insufficient data'}

    # Check 1: Split-half reliability
    # Randomly split into two halves and check both show warfare
    half = len(valid_data) // 2
    shuffled = valid_data.sample(frac=1, random_state=42)

    split1 = shuffled.iloc[:half]
    split2 = shuffled.iloc[half:]

    corr1, _ = pearsonr(split1[dim1], split1[dim2])
    corr2, _ = pearsonr(split2[dim1], split2[dim2])

    split_consistent = (corr1 < -0.4) and (corr2 < -0.4)

    # Check 2: Linear relationship test
    # Check correlation in low/mid/high ranges of dim1
    sorted_data = valid_data.sort_values(dim1)
    third = len(sorted_data) // 3

    low_range = sorted_data.iloc[:third]
    mid_range = sorted_data.iloc[third:2*third]
    high_range = sorted_data.iloc[2*third:]

    corr_low, _ = pearsonr(low_range[dim1], low_range[dim2]) if len(low_range) > 5 else (0, 1)
    corr_mid, _ = pearsonr(mid_range[dim1], mid_range[dim2]) if len(mid_range) > 5 else (0, 1)
    corr_high, _ = pearsonr(high_range[dim1], high_range[dim2]) if len(high_range) > 5 else (0, 1)

    # Warfare is linear if all ranges show negative correlation
    linear = all(c < -0.2 for c in [corr_low, corr_mid, corr_high])

    # Overall validation
    validated = split_consistent and linear
    confidence = "HIGH" if validated else "MEDIUM" if split_consistent or linear else "LOW"

    return {
        'validated': validated,
        'confidence': confidence,
        'split_consistency': split_consistent,
        'linear_relationship': linear,
        'split_correlations': (round(corr1, 3), round(corr2, 3)),
        'range_correlations': {
            'low': round(corr_low, 3),
            'mid': round(corr_mid, 3),
            'high': round(corr_high, 3)
        }
    }


def create_warfare_scatter(dimension_matrix, dim1, dim2, output_path):
    """
    Create scatter plot showing dimension warfare
    """
    valid_data = dimension_matrix[[dim1, dim2, 'config']].dropna()

    plt.figure(figsize=(10, 8))

    # Create scatter plot
    plt.scatter(valid_data[dim1], valid_data[dim2],
                alpha=0.6, s=100, edgecolors='black', linewidth=1)

    # Add regression line
    z = np.polyfit(valid_data[dim1], valid_data[dim2], 1)
    p = np.poly1d(z)
    x_line = np.linspace(valid_data[dim1].min(), valid_data[dim1].max(), 100)
    plt.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2,
             label=f'Trend: slope={z[0]:.2f}')

    # Calculate correlation
    corr, p_value = pearsonr(valid_data[dim1], valid_data[dim2])

    # Add labels and title
    plt.xlabel(dim1.replace('_', ' ').title(), fontsize=14, fontweight='bold')
    plt.ylabel(dim2.replace('_', ' ').title(), fontsize=14, fontweight='bold')
    plt.title(f'Dimension Warfare: {dim1} vs {dim2}\n'
              f'Correlation: r={corr:.3f} (p={p_value:.4f})',
              fontsize=16, fontweight='bold', pad=20)

    # Add interpretation text
    if corr < -0.7:
        interpretation = "STRONG ZERO-SUM TRADEOFF"
        color = 'darkred'
    elif corr < -0.5:
        interpretation = "MODERATE CONFLICT"
        color = 'orangered'
    else:
        interpretation = "WEAK TENSION"
        color = 'orange'

    plt.text(0.02, 0.98, interpretation,
             transform=plt.gca().transAxes,
             fontsize=12, fontweight='bold', color=color,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"📊 Scatter plot saved to: {output_path}")


def create_warfare_heatmap(dimension_matrix, output_path):
    """
    Create correlation heatmap showing all dimension relationships
    """
    # Calculate correlation matrix
    corr_matrix = dimension_matrix[EVALUATION_DIMENSIONS].corr()

    plt.figure(figsize=(12, 10))

    # Create heatmap
    sns.heatmap(corr_matrix,
                annot=True,
                fmt='.2f',
                cmap='RdYlGn',
                center=0,
                vmin=-1,
                vmax=1,
                square=True,
                linewidths=0.5,
                linecolor='gray',
                cbar_kws={'label': 'Correlation', 'shrink': 0.8})

    plt.title('Dimension Correlation Matrix\n(Red = Warfare, Green = Synergy)',
              fontsize=16, fontweight='bold', pad=20)

    # Rotate labels
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    # Make labels more readable
    ax = plt.gca()
    ax.set_xticklabels([label.get_text().replace('_', ' ').title()
                        for label in ax.get_xticklabels()], fontsize=10)
    ax.set_yticklabels([label.get_text().replace('_', ' ').title()
                        for label in ax.get_yticklabels()], fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"🔥 Heatmap saved to: {output_path}")


def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Detect dimension warfare in evaluation results"
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=BATCH_EVALUATION_FILE,
        help=f'Path to evaluation results CSV (default: {BATCH_EVALUATION_FILE})'
    )

    args = parser.parse_args()

    # Load data
    print(f"\n📁 Loading data from: {args.csv}")
    try:
        df = pd.read_csv(args.csv)
        print(f"✓ Loaded {len(df)} evaluation results")
    except FileNotFoundError:
        print(f"❌ File not found: {args.csv}")
        print(f"   Run an evaluation first to generate results")
        return
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return

    # Check for required columns
    if 'config_name' not in df.columns or df['config_name'].isna().all():
        print("❌ No config_name metadata found")
        print("   This analysis requires metadata tracking")
        print("   Run evaluation with section_names parameter")
        return

    print_section("Step 1: Extract Dimension Scores")

    dimension_matrix = extract_dimension_scores(df)
    print(f"✓ Built dimension matrix: {len(dimension_matrix)} configs × {len(EVALUATION_DIMENSIONS)} dimensions")

    # Show data quality
    completeness = dimension_matrix[EVALUATION_DIMENSIONS].notna().sum().sum()
    total_cells = len(dimension_matrix) * len(EVALUATION_DIMENSIONS)
    print(f"✓ Data completeness: {completeness}/{total_cells} ({completeness/total_cells*100:.1f}%)")

    print_section("Step 2: Detect Dimension Warfare")

    warfare_pairs = detect_dimension_warfare(dimension_matrix)

    if not warfare_pairs:
        print("✅ No dimension warfare detected!")
        print("   All dimensions appear independent or positively correlated")
        return

    print(f"⚔️  Found {len(warfare_pairs)} warfare pairs:\n")

    for i, warfare in enumerate(warfare_pairs, 1):
        print(f"{i}. {warfare['interpretation']}")
        print(f"   Correlation: r={warfare['correlation']:.3f} (p={warfare['p_value']:.4f})")
        print(f"   Severity: {warfare['severity']}")
        print(f"   Configs tested: {warfare['n_configs']}")
        print()

    print_section("Step 3: Validate Top Warfare Pair")

    if warfare_pairs:
        top_warfare = warfare_pairs[0]
        dim1, dim2 = top_warfare['dim1'], top_warfare['dim2']

        print(f"Validating: {dim1} vs {dim2}")
        validation = validate_warfare(df, dim1, dim2)

        print(f"\n✓ Validation Results:")
        print(f"   Confidence: {validation['confidence']}")
        print(f"   Split consistency: {'✓' if validation['split_consistency'] else '✗'}")
        print(f"   Linear relationship: {'✓' if validation['linear_relationship'] else '✗'}")
        print(f"   Split correlations: {validation['split_correlations']}")
        print(f"   Range correlations: {validation['range_correlations']}")

        if validation['validated']:
            print(f"\n✅ WARFARE CONFIRMED: {dim1} and {dim2} have real zero-sum tradeoff")
        else:
            print(f"\n⚠️  Warfare possible but needs more data for confirmation")

    print_section("Step 4: Generate Visualizations")

    # Create scatter plot for top warfare pair
    if warfare_pairs:
        output_scatter = f'images/warfare_{dim1}_vs_{dim2}.png'
        create_warfare_scatter(dimension_matrix, dim1, dim2, output_scatter)

    # Create overall correlation heatmap
    output_heatmap = 'images/dimension_correlation_heatmap.png'
    create_warfare_heatmap(dimension_matrix, output_heatmap)

    print_section("Summary")

    if warfare_pairs:
        severe_count = sum(1 for w in warfare_pairs if w['severity'] == 'SEVERE')
        strong_count = sum(1 for w in warfare_pairs if w['severity'] == 'STRONG')
        moderate_count = sum(1 for w in warfare_pairs if w['severity'] == 'MODERATE')

        print(f"📊 Warfare Summary:")
        print(f"   Severe (r < -0.8): {severe_count}")
        print(f"   Strong (r < -0.7): {strong_count}")
        print(f"   Moderate (r < -0.5): {moderate_count}")
        print(f"\n💡 Insight:")
        print(f"   You found {len(warfare_pairs)} fundamental tradeoffs in AI behavior!")
        print(f"   These dimensions CANNOT be optimized simultaneously.")
        print(f"   Pick your battles wisely when designing prompts.")
    else:
        print("✅ No warfare detected - dimensions appear mostly independent")


if __name__ == "__main__":
    main()
