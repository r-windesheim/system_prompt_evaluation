"""
Interaction Analysis Utilities

Analyzes how prompt sections interact with each other.
Checks for non-linear effects, synergy, and interference.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set
from itertools import combinations


def check_data_quality(df: pd.DataFrame) -> Dict:
    """
    Check if we have sufficient data for interaction analysis

    Args:
        df: DataFrame with evaluation results containing config_name column

    Returns:
        Dictionary with data quality metrics
    """
    # Check if we have metadata
    if 'config_name' not in df.columns or df['config_name'].isna().all():
        return {
            'has_metadata': False,
            'error': 'No config_name metadata found. Run a new evaluation with metadata tracking.'
        }

    # Get unique configs
    configs = df[df['config_name'].notna()]['config_name'].unique()

    # Parse config names to count sections
    config_sizes = {}
    for config in configs:
        if config and '+' in config:
            size = len(config.split('+'))
        elif config:
            size = 1
        else:
            size = 0
        config_sizes[size] = config_sizes.get(size, 0) + 1

    # Extract section pairs
    section_pairs = set()
    for config in configs:
        if not config or '+' not in config:
            continue
        sections = config.split('+')
        for pair in combinations(sections, 2):
            section_pairs.add(tuple(sorted(pair)))

    # Determine total possible pairs (for n=6 sections: C(6,2) = 15)
    # Extract max section number from configs
    max_section = 0
    for config in configs:
        if config:
            numbers = [int(x) for x in config.replace('+', ' ').split()]
            if numbers:
                max_section = max(max_section, max(numbers))

    total_possible_pairs = max_section * (max_section - 1) // 2 if max_section > 0 else 0

    return {
        'has_metadata': True,
        'total_configs': len(configs),
        'config_distribution': config_sizes,
        'section_pairs_covered': len(section_pairs),
        'total_possible_pairs': total_possible_pairs,
        'pair_coverage_pct': (len(section_pairs) / total_possible_pairs * 100) if total_possible_pairs > 0 else 0,
        'max_section_number': max_section,
        'ready_for_analysis': len(section_pairs) >= 10  # Need at least 10 pairs
    }


def find_winning_configs(df: pd.DataFrame, n_top: int = 10, n_bottom: int = 10) -> Dict:
    """
    Identify top and bottom performing configs and analyze section frequency

    Args:
        df: DataFrame with evaluation results
        n_top: Number of top configs to analyze
        n_bottom: Number of bottom configs to analyze

    Returns:
        Dictionary with top/bottom config analysis
    """
    if 'config_name' not in df.columns or df['config_name'].isna().all():
        return {'error': 'No config_name metadata found'}

    # Calculate average score per config
    config_scores = df.groupby('config_name')['evaluation_score'].mean().sort_values(ascending=False)

    # Get top and bottom configs
    top_configs = config_scores.head(n_top)
    bottom_configs = config_scores.tail(n_bottom)

    # Count section frequency in top configs
    top_section_freq = {}
    for config in top_configs.index:
        if config and config != 'nan':
            sections = config.split('+')
            for section in sections:
                top_section_freq[section] = top_section_freq.get(section, 0) + 1

    # Count section frequency in bottom configs
    bottom_section_freq = {}
    for config in bottom_configs.index:
        if config and config != 'nan':
            sections = config.split('+')
            for section in sections:
                bottom_section_freq[section] = bottom_section_freq.get(section, 0) + 1

    return {
        'top_configs': {str(k): float(v) for k, v in top_configs.items()},
        'bottom_configs': {str(k): float(v) for k, v in bottom_configs.items()},
        'top_section_freq': top_section_freq,
        'bottom_section_freq': bottom_section_freq,
        'top_avg_score': float(top_configs.mean()),
        'bottom_avg_score': float(bottom_configs.mean()),
        'score_range': float(top_configs.iloc[0] - bottom_configs.iloc[-1])
    }


def calculate_additivity_check(df: pd.DataFrame, metric: str = 'evaluation_score') -> Dict:
    """
    Test if section effects are additive (linear) or interactive (non-linear)

    For each pair A, B:
    - Expected score = score(A) + score(B) - baseline
    - Actual score = score(A+B)
    - Deviation = actual - expected

    Args:
        df: DataFrame with evaluation results
        metric: Column name to analyze (default: evaluation_score)

    Returns:
        Dictionary with additivity test results
    """
    if 'config_name' not in df.columns or df['config_name'].isna().all():
        return {'error': 'No config_name metadata found'}

    # Get average scores per config
    config_scores = df.groupby('config_name')[metric].mean()

    # Separate singles and pairs
    singles = {}
    pairs_actual = {}

    for config, score in config_scores.items():
        if not config or config == 'nan':
            continue
        sections = config.split('+')
        if len(sections) == 1:
            singles[sections[0]] = score
        elif len(sections) == 2:
            pairs_actual[tuple(sorted(sections))] = score

    # Calculate expected vs actual for pairs
    comparisons = []
    for (sec_a, sec_b), actual_score in pairs_actual.items():
        if sec_a in singles and sec_b in singles:
            # Linear assumption: score(A+B) ≈ score(A) + score(B) - baseline
            # Simplified: just use sum for now (baseline cancels in difference)
            expected_score = singles[sec_a] + singles[sec_b]
            deviation = actual_score - expected_score

            comparisons.append({
                'pair': f"{sec_a}+{sec_b}",
                'actual': actual_score,
                'expected': expected_score,
                'deviation': deviation,
                'interaction_strength': abs(deviation)
            })

    if not comparisons:
        return {'error': 'Not enough data to test additivity (need singles + pairs)'}

    # Calculate correlation between expected and actual
    actual_vals = [c['actual'] for c in comparisons]
    expected_vals = [c['expected'] for c in comparisons]

    if len(actual_vals) > 2:
        correlation, p_value = stats.pearsonr(actual_vals, expected_vals)
    else:
        correlation, p_value = 0, 1

    # Calculate average deviation
    avg_deviation = np.mean([abs(c['deviation']) for c in comparisons])

    return {
        'comparisons': comparisons,
        'n_pairs_tested': len(comparisons),
        'correlation': float(correlation),
        'p_value': float(p_value),
        'avg_abs_deviation': float(avg_deviation),
        'interpretation': _interpret_additivity(correlation)
    }


def _interpret_additivity(r: float) -> str:
    """Interpret correlation coefficient for additivity check"""
    if r > 0.8:
        return "Strong additivity - sections combine linearly (minimal interactions)"
    elif r > 0.6:
        return "Moderate additivity - some interactions present"
    elif r > 0.4:
        return "Weak additivity - significant interactions detected"
    else:
        return "Non-additive - strong interaction effects dominate"


def calculate_interaction_matrix(
    df: pd.DataFrame,
    metric: str = 'evaluation_score',
    min_sections: int = 6
) -> pd.DataFrame:
    """
    Calculate pairwise interaction effects between sections

    Interaction = score(A+B) - score(A) - score(B) + baseline
    - Positive = synergy (better together)
    - Negative = interference (worse together)

    Args:
        df: DataFrame with evaluation results
        metric: Column name to analyze
        min_sections: Expected number of sections (for matrix size)

    Returns:
        DataFrame with sections as rows/cols, values are interaction effects
    """
    if 'config_name' not in df.columns or df['config_name'].isna().all():
        return pd.DataFrame()

    # Get average scores per config
    config_scores = df.groupby('config_name')[metric].mean()

    # Get baseline (all sections together or average of all)
    all_sections_config = [c for c in config_scores.index if c and '+' in c and len(c.split('+')) == min_sections]
    if all_sections_config:
        baseline = config_scores[all_sections_config[0]]
    else:
        baseline = config_scores.mean()

    # Separate singles and pairs
    singles = {}
    pairs_actual = {}

    for config, score in config_scores.items():
        if not config or config == 'nan':
            continue
        sections = config.split('+')
        if len(sections) == 1:
            singles[sections[0]] = score
        elif len(sections) == 2:
            pairs_actual[tuple(sorted(sections))] = score

    # Build interaction matrix
    section_ids = sorted(singles.keys(), key=lambda x: int(x))
    n = len(section_ids)

    interaction_matrix = np.zeros((n, n))

    for i, sec_a in enumerate(section_ids):
        for j, sec_b in enumerate(section_ids):
            if i == j:
                interaction_matrix[i, j] = 0  # Self-interaction is 0
            elif i < j:
                pair = tuple(sorted([sec_a, sec_b]))
                if pair in pairs_actual and sec_a in singles and sec_b in singles:
                    # Interaction = actual - (effect_A + effect_B)
                    # effect_A = score(A) - baseline, effect_B = score(B) - baseline
                    # So: interaction = score(A+B) - score(A) - score(B) + baseline
                    interaction = pairs_actual[pair] - singles[sec_a] - singles[sec_b] + baseline
                    interaction_matrix[i, j] = interaction
                    interaction_matrix[j, i] = interaction  # Symmetric

    # Create DataFrame
    df_matrix = pd.DataFrame(
        interaction_matrix,
        index=[f"Section {s}" for s in section_ids],
        columns=[f"Section {s}" for s in section_ids]
    )

    return df_matrix


def get_strongest_interactions(interaction_matrix: pd.DataFrame, n: int = 5) -> List[Dict]:
    """
    Extract strongest interactions (both positive and negative)

    Args:
        interaction_matrix: DataFrame from calculate_interaction_matrix
        n: Number of top interactions to return

    Returns:
        List of dictionaries with strongest interactions
    """
    if interaction_matrix.empty:
        return []

    # Extract upper triangle (avoid duplicates)
    interactions = []
    for i in range(len(interaction_matrix)):
        for j in range(i+1, len(interaction_matrix.columns)):
            value = interaction_matrix.iloc[i, j]
            interactions.append({
                'section_a': interaction_matrix.index[i],
                'section_b': interaction_matrix.columns[j],
                'interaction': float(value),
                'type': 'synergy' if value > 0 else 'interference'
            })

    # Sort by absolute value
    interactions.sort(key=lambda x: abs(x['interaction']), reverse=True)

    return interactions[:n]
