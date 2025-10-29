#!/usr/bin/env python3
"""
Section Interaction Analysis

Analyzes how prompt sections interact with each other.
Tests if effects are additive or if sections interfere/synergize.

Usage:
    python analyze_interactions.py [--csv path/to/results.csv]
"""
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

from utils.interaction_analysis import (
    check_data_quality,
    find_winning_configs,
    calculate_additivity_check,
    calculate_interaction_matrix,
    get_strongest_interactions
)
from config import BATCH_EVALUATION_FILE


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def run_data_quality_check(df: pd.DataFrame):
    """Run and display data quality checks"""
    print_section("Step 1: Data Quality Check")

    quality = check_data_quality(df)

    if not quality.get('has_metadata'):
        print(f"❌ {quality.get('error')}")
        return False

    print(f"✓ Total unique configs: {quality['total_configs']}")
    print(f"✓ Config distribution:")
    for size, count in sorted(quality['config_distribution'].items()):
        size_name = "single" if size == 1 else f"{size}-section combos"
        print(f"    {size_name}: {count}")

    print(f"\n✓ Section pairs covered: {quality['section_pairs_covered']}/{quality['total_possible_pairs']} ({quality['pair_coverage_pct']:.1f}%)")
    print(f"✓ Max section number: {quality['max_section_number']}")

    if quality['ready_for_analysis']:
        print(f"\n✅ Data quality sufficient for analysis")
    else:
        print(f"\n⚠️  Limited data - results may be unreliable")

    return quality['ready_for_analysis']


def run_winning_configs_analysis(df: pd.DataFrame):
    """Analyze top and bottom performing configs"""
    print_section("Step 2: Top/Bottom Config Analysis")

    results = find_winning_configs(df, n_top=10, n_bottom=10)

    if 'error' in results:
        print(f"❌ {results['error']}")
        return

    print(f"🏆 Top 10 Configurations (avg score: {results['top_avg_score']:.1f}/100):")
    for i, (config, score) in enumerate(list(results['top_configs'].items())[:10], 1):
        print(f"   {i:2d}. {config:20s} → {score:.1f}")

    print(f"\n📉 Bottom 10 Configurations (avg score: {results['bottom_avg_score']:.1f}/100):")
    for i, (config, score) in enumerate(list(results['bottom_configs'].items())[-10:], 1):
        print(f"   {i:2d}. {config:20s} → {score:.1f}")

    print(f"\n📊 Section Frequency Analysis:")
    print(f"\nTop 10 configs - section frequency:")
    for section, count in sorted(results['top_section_freq'].items(), key=lambda x: int(x[0])):
        pct = (count / 10) * 100
        print(f"   Section {section}: {count}/10 ({pct:.0f}%)")

    print(f"\nBottom 10 configs - section frequency:")
    for section, count in sorted(results['bottom_section_freq'].items(), key=lambda x: int(x[0])):
        pct = (count / 10) * 100
        print(f"   Section {section}: {count}/10 ({pct:.0f}%)")

    # Find sections that differ significantly
    print(f"\n💡 Insights:")
    for section in set(list(results['top_section_freq'].keys()) + list(results['bottom_section_freq'].keys())):
        top_freq = results['top_section_freq'].get(section, 0)
        bottom_freq = results['bottom_section_freq'].get(section, 0)
        diff = top_freq - bottom_freq

        if abs(diff) >= 4:  # Significant difference
            if diff > 0:
                print(f"   ✓ Section {section} appears {diff} more times in top configs (positive correlation)")
            else:
                print(f"   ✗ Section {section} appears {abs(diff)} more times in bottom configs (negative correlation)")


def run_additivity_check(df: pd.DataFrame) -> bool:
    """Test if section effects are additive"""
    print_section("Step 3: Non-Linearity Check (Additivity Test)")

    results = calculate_additivity_check(df)

    if 'error' in results:
        print(f"❌ {results['error']}")
        return False

    print(f"Tested {results['n_pairs_tested']} section pairs\n")
    print(f"Correlation (actual vs expected): r = {results['correlation']:.3f}, p = {results['p_value']:.4f}")
    print(f"Average absolute deviation: {results['avg_abs_deviation']:.2f} points")
    print(f"\n📊 Interpretation: {results['interpretation']}")

    # Create scatter plot
    comparisons = results['comparisons']
    actual = [c['actual'] for c in comparisons]
    expected = [c['expected'] for c in comparisons]

    plt.figure(figsize=(10, 6))
    plt.scatter(expected, actual, alpha=0.6, s=100, edgecolors='black', linewidth=1)

    # Add regression line
    z = np.polyfit(expected, actual, 1)
    p = np.poly1d(z)
    plt.plot(expected, p(expected), "r--", alpha=0.8, linewidth=2, label=f'Fit: y={z[0]:.2f}x+{z[1]:.2f}')

    # Add perfect additivity line
    min_val, max_val = min(expected), max(expected)
    plt.plot([min_val, max_val], [min_val, max_val], 'g--', alpha=0.5, linewidth=2, label='Perfect additivity')

    plt.xlabel('Expected Score (A + B)', fontsize=12)
    plt.ylabel('Actual Score (A+B)', fontsize=12)
    plt.title(f'Additivity Check: Actual vs Expected\n(r={results["correlation"]:.3f}, p={results["p_value"]:.4f})', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    output_path = 'images/additivity_check.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n📈 Plot saved to: {output_path}")

    # Recommend next steps
    if results['correlation'] > 0.7:
        print(f"\n⚠️  High additivity detected - section interactions are minimal")
        print(f"   Semantic similarity analysis may not reveal much")
        return False
    else:
        print(f"\n✅ Significant interactions detected - worth investigating further")
        return True


def run_interaction_heatmap(df: pd.DataFrame):
    """Generate interaction matrix and heatmap"""
    print_section("Step 4: Section Pair Interaction Heatmap")

    interaction_matrix = calculate_interaction_matrix(df, metric='evaluation_score')

    if interaction_matrix.empty:
        print("❌ Not enough data to calculate interaction matrix")
        return

    print(f"Interaction Matrix (interaction = score(A+B) - score(A) - score(B) + baseline):")
    print(f"  Positive = Synergy (sections work better together)")
    print(f"  Negative = Interference (sections conflict)\n")

    # Print matrix
    print(interaction_matrix.to_string())

    # Save to CSV
    output_csv = 'results/interaction_matrix.csv'
    interaction_matrix.to_csv(output_csv)
    print(f"\n💾 Matrix saved to: {output_csv}")

    # Get strongest interactions
    strongest = get_strongest_interactions(interaction_matrix, n=5)
    if strongest:
        print(f"\n🔝 Top 5 Strongest Interactions:")
        for i, inter in enumerate(strongest, 1):
            symbol = "+" if inter['type'] == 'synergy' else "-"
            print(f"   {i}. {inter['section_a']} + {inter['section_b']}: {symbol}{abs(inter['interaction']):.2f} ({inter['type']})")

    # Create heatmap
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        interaction_matrix,
        annot=True,
        fmt='.1f',
        cmap='RdYlGn',
        center=0,
        cbar_kws={'label': 'Interaction Effect'},
        linewidths=0.5,
        linecolor='gray'
    )
    plt.title('Section Pair Interaction Matrix\n(Green=Synergy, Red=Interference)', fontsize=14, pad=20)
    plt.xlabel('Section B', fontsize=12)
    plt.ylabel('Section A', fontsize=12)
    plt.tight_layout()

    output_path = 'images/section_interaction_heatmap.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n📈 Heatmap saved to: {output_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze section interactions in prompt evaluation results"
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

    # Run analysis steps
    if not run_data_quality_check(df):
        print(f"\n⚠️  Stopping - insufficient data quality")
        return

    run_winning_configs_analysis(df)

    interactions_detected = run_additivity_check(df)

    if interactions_detected:
        run_interaction_heatmap(df)

        # Final recommendation
        print_section("Final Recommendation")
        print("✅ Significant section interactions detected")
        print("📊 Next steps:")
        print("   1. Review interaction heatmap for specific synergies/conflicts")
        print("   2. Consider semantic similarity analysis if patterns are unclear")
        print("   3. Test hypotheses with targeted evaluations")
    else:
        print_section("Final Recommendation")
        print("⚠️  Sections appear mostly additive (minimal interactions)")
        print("📊 Next steps:")
        print("   1. Focus on individual section optimization")
        print("   2. Semantic analysis unlikely to add significant value")


if __name__ == "__main__":
    main()
