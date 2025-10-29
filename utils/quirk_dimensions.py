"""
Quirk Dimension Definitions and Helper Functions

This module groups 35 individual quirks into 7 coherent behavioral dimensions
for better cognitive accessibility in the UI. Each dimension represents a
related cluster of behavioral patterns.
"""

from typing import Dict, List, Any, Optional, Tuple

# =============================================================================
# DIMENSIONAL GROUPINGS
# =============================================================================

QUIRK_DIMENSIONS = {
    'Confidence Spectrum': {
        'quirks': ['hedge_rate', 'certainty_rate', 'apology_rate', 'caveat_rate', 'disclaimer_rate'],
        'description': 'How definitive vs tentative the responses are',
        'visual_type': 'slider',  # Uncertain ← ● → Confident
        'icon': '🎯',
        'low_label': 'Uncertain/Hedging',
        'high_label': 'Confident/Definitive'
    },
    'Structure & Organization': {
        'quirks': ['enumeration_rate', 'action_rate', 'example_rate', 'metacommentary_rate', 'transition_rate'],
        'description': 'Use of lists, examples, and structural elements',
        'visual_type': 'icon_grid',  # Multiple icon bars
        'icon': '📋',
        'components': {
            'enumeration_rate': {'label': 'Lists', 'icon': '📋'},
            'action_rate': {'label': 'Actions', 'icon': '✓'},
            'example_rate': {'label': 'Examples', 'icon': '💡'},
            'metacommentary_rate': {'label': 'Meta', 'icon': '🗨️'},
            'transition_rate': {'label': 'Transitions', 'icon': '→'}
        }
    },
    'Interaction Style': {
        'quirks': ['question_rate', 'acknowledgment_rate', 'instruction_density', 'second_person_rate', 'imperative_rate'],
        'description': 'How the AI engages with the user',
        'visual_type': 'spectrum',  # Conversational ↔ Directive
        'icon': '💬',
        'low_label': 'Conversational',
        'high_label': 'Directive'
    },
    'Tone & Formality': {
        'quirks': ['formality_score', 'contraction_rate', 'sentiment_polarity', 'emotional_language_rate', 'sentiment_subjectivity'],
        'description': 'Overall formality and emotional tone',
        'visual_type': 'gauge',  # Single gauge: Casual → Formal
        'icon': '🎭',
        'low_label': 'Casual',
        'high_label': 'Formal'
    },
    'Clarity vs Detail': {
        'quirks': ['parentheses_rate', 'elaboration_rate', 'specification_rate', 'passive_voice_rate', 'quantifier_rate'],
        'description': 'Balance between brevity and thoroughness',
        'visual_type': 'slider',  # Concise ← ● → Detailed
        'icon': '🔍',
        'low_label': 'Concise',
        'high_label': 'Detailed/Nuanced'
    },
    'Focus & Agency': {
        'quirks': ['first_person_rate', 'second_person_rate', 'third_person_rate', 'self_reference_rate'],
        'description': 'Whose perspective is emphasized',
        'visual_type': 'pie',  # Three slices: AI-focused, User-focused, Topic-focused
        'icon': '👤',
        'components': {
            'first_person_rate': {'label': 'AI-focused', 'color': '#4A90E2'},
            'second_person_rate': {'label': 'User-focused', 'color': '#E94A4A'},
            'third_person_rate': {'label': 'Topic-focused', 'color': '#50C878'}
        }
    },
    'Technical Depth': {
        'quirks': ['technical_jargon_rate', 'specification_rate', 'comparison_rate', 'conditional_rate', 'modal_verb_rate'],
        'description': 'Technical complexity and precision',
        'visual_type': 'bar',  # Simple horizontal bar
        'icon': '⚙️',
        'low_label': 'Plain Language',
        'high_label': 'Technical'
    }
}


# =============================================================================
# LOOKUP FUNCTIONS
# =============================================================================

def get_dimension_for_quirk(quirk_name: str) -> Optional[str]:
    """
    Find which dimension a quirk belongs to.

    Args:
        quirk_name: Name of the quirk (e.g., 'hedge_rate')

    Returns:
        Dimension name or None if quirk not found
    """
    for dimension_name, dimension_data in QUIRK_DIMENSIONS.items():
        if quirk_name in dimension_data['quirks']:
            return dimension_name
    return None


def get_all_quirk_names() -> List[str]:
    """
    Get flat list of all quirk names across all dimensions.

    Returns:
        List of quirk names
    """
    all_quirks = []
    for dimension_data in QUIRK_DIMENSIONS.values():
        all_quirks.extend(dimension_data['quirks'])
    return all_quirks


# =============================================================================
# DIMENSION SCORE CALCULATION
# =============================================================================

def calculate_dimension_score(dimension_quirks: List[str], all_quirks: Dict[str, Any]) -> float:
    """
    Aggregate multiple quirk impacts into a single dimension score.

    Strategy:
    - For each quirk in the dimension, calculate spike_ratio (with_section / without_section)
    - Average the spike ratios to get overall dimension impact
    - Handle edge cases (division by zero, missing quirks)

    Args:
        dimension_quirks: List of quirk names in this dimension
        all_quirks: Dict from format_quirk_results_for_ui() containing all detected quirks

    Returns:
        Average spike ratio for the dimension (1.0 = no change, 2.0 = doubled)
    """
    spike_ratios = []

    for quirk_name in dimension_quirks:
        # Find this quirk in the detected quirks
        quirk_found = False
        for quirk in all_quirks:
            if quirk.get('quirk_type') == quirk_name:
                quirk_found = True
                full_rate = quirk.get('full_prompt_rate', 0)
                without_rate = quirk.get('without_section_rate', 0)

                # Calculate spike ratio with safeguards
                if without_rate > 0:
                    spike_ratio = full_rate / without_rate
                elif full_rate > 0:
                    spike_ratio = 999  # Infinite spike (0 → positive)
                else:
                    spike_ratio = 1.0  # No change (0 → 0)

                spike_ratios.append(spike_ratio)
                break

        if not quirk_found:
            # Quirk not detected (below threshold) - assume no impact
            spike_ratios.append(1.0)

    # Return average spike ratio
    if spike_ratios:
        return sum(spike_ratios) / len(spike_ratios)
    else:
        return 1.0


# =============================================================================
# AUTO-SUMMARY GENERATION
# =============================================================================

def generate_auto_summary(detected_quirks: List[Dict[str, Any]]) -> str:
    """
    Generate a one-sentence summary of the biggest behavioral changes.

    Example output:
    "This section makes responses 4.2x more confident with 3.1x more lists and examples"

    Args:
        detected_quirks: List of quirk dicts from format_quirk_results_for_ui()

    Returns:
        Human-readable one-sentence summary
    """
    if not detected_quirks:
        return "No significant behavioral changes detected."

    # Find top 2-3 most impacted quirks by spike ratio
    quirks_with_spikes = []
    for quirk in detected_quirks:
        full_rate = quirk.get('full_prompt_rate', 0)
        without_rate = quirk.get('without_section_rate', 0)

        if without_rate > 0:
            spike_ratio = full_rate / without_rate
        elif full_rate > 0:
            spike_ratio = 999
        else:
            spike_ratio = 1.0

        quirks_with_spikes.append({
            'quirk_type': quirk.get('quirk_type'),
            'spike_ratio': spike_ratio,
            'direction': quirk.get('direction', 'increases')
        })

    # Sort by absolute deviation from 1.0 (biggest changes first)
    quirks_with_spikes.sort(key=lambda x: abs(x['spike_ratio'] - 1.0), reverse=True)

    # Take top 2-3 quirks
    top_quirks = quirks_with_spikes[:3]

    # Build sentence
    quirk_descriptions = []
    for q in top_quirks:
        quirk_name = q['quirk_type'].replace('_rate', '').replace('_score', '').replace('_', ' ')
        spike = q['spike_ratio']
        direction = q['direction']

        if spike > 1.5:
            quirk_descriptions.append(f"{spike:.1f}x more {quirk_name}")
        elif spike < 0.67:
            reduction = 1 / spike if spike > 0 else 999
            quirk_descriptions.append(f"{reduction:.1f}x less {quirk_name}")

    if not quirk_descriptions:
        return "This section causes subtle behavioral changes across multiple dimensions."

    # Construct sentence
    if len(quirk_descriptions) == 1:
        summary = f"This section causes {quirk_descriptions[0]}"
    elif len(quirk_descriptions) == 2:
        summary = f"This section causes {quirk_descriptions[0]} and {quirk_descriptions[1]}"
    else:
        summary = f"This section causes {', '.join(quirk_descriptions[:-1])}, and {quirk_descriptions[-1]}"

    return summary


# =============================================================================
# TOP CHANGES DETECTION
# =============================================================================

def get_top_3_changes(detected_quirks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Auto-detect the top 3 most impactful behavioral changes.

    Ranks by:
    1. Absolute impact magnitude (difference in rates)
    2. Statistical significance (p-value)
    3. Effect size (Cohen's d)

    Args:
        detected_quirks: List of quirk dicts from format_quirk_results_for_ui()

    Returns:
        List of top 3 quirk dicts with added 'rank' field
    """
    if not detected_quirks:
        return []

    # Score each quirk by composite importance
    scored_quirks = []
    for quirk in detected_quirks:
        impact = quirk.get('impact', 0)
        p_value = quirk.get('p_value', 1.0)
        effect_size = abs(quirk.get('effect_size', 0))

        # Composite score (higher = more important)
        # - Absolute impact magnitude (primary)
        # - Statistical significance bonus (p < 0.05)
        # - Effect size multiplier
        score = abs(impact) * (2 if p_value < 0.05 else 1) * (1 + effect_size)

        scored_quirks.append({
            **quirk,
            'importance_score': score
        })

    # Sort by importance score
    scored_quirks.sort(key=lambda x: x['importance_score'], reverse=True)

    # Return top 3 with rank labels
    top_3 = scored_quirks[:3]
    for i, quirk in enumerate(top_3, start=1):
        quirk['rank'] = i

    return top_3


# =============================================================================
# DIMENSION AGGREGATION
# =============================================================================

def aggregate_quirks_by_dimension(detected_quirks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Group detected quirks by their dimensions and calculate dimension-level scores.

    Args:
        detected_quirks: List of quirk dicts from format_quirk_results_for_ui()

    Returns:
        Dict with dimension names as keys, containing:
        - 'quirks': List of quirks in this dimension
        - 'dimension_score': Average spike ratio
        - 'visual_type': Type of visualization to use
        - 'icon': Emoji icon
        - 'description': Dimension description
    """
    dimensions_data = {}

    for dimension_name, dimension_info in QUIRK_DIMENSIONS.items():
        # Find quirks belonging to this dimension
        dimension_quirks = []
        for quirk in detected_quirks:
            if quirk.get('quirk_type') in dimension_info['quirks']:
                dimension_quirks.append(quirk)

        # Calculate dimension score
        dimension_score = calculate_dimension_score(dimension_info['quirks'], detected_quirks)

        # Build dimension data
        dimensions_data[dimension_name] = {
            'quirks': dimension_quirks,
            'dimension_score': dimension_score,
            'visual_type': dimension_info['visual_type'],
            'icon': dimension_info['icon'],
            'description': dimension_info['description'],
            'low_label': dimension_info.get('low_label', ''),
            'high_label': dimension_info.get('high_label', ''),
            'components': dimension_info.get('components', {})
        }

    return dimensions_data


# =============================================================================
# VISUAL HELPERS
# =============================================================================

def get_slider_position(dimension_score: float) -> int:
    """
    Convert dimension score (spike ratio) to slider position (0-100).

    Args:
        dimension_score: Average spike ratio (1.0 = no change)

    Returns:
        Position 0-100 (50 = neutral, 0 = strong decrease, 100 = strong increase)
    """
    # Map spike ratio to 0-100 scale
    # 0.5 → 0 (halved)
    # 1.0 → 50 (no change)
    # 2.0 → 100 (doubled)

    if dimension_score < 1.0:
        # Decrease: map 0.0-1.0 to 0-50
        position = dimension_score * 50
    else:
        # Increase: map 1.0-2.0+ to 50-100
        position = 50 + min((dimension_score - 1.0) * 50, 50)

    return int(position)


def get_gauge_percentage(dimension_score: float) -> int:
    """
    Convert dimension score to gauge fill percentage (0-100).

    Args:
        dimension_score: Average spike ratio

    Returns:
        Fill percentage 0-100
    """
    # Simple linear mapping: higher score = higher fill
    # Cap at 100%
    percentage = min(dimension_score * 50, 100)
    return int(percentage)
