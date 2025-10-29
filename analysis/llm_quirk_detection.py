#!/usr/bin/env python3
"""
Phase 2 Quirk Detection: LLM-based behavioral analysis using latteries

Detects sophisticated behavioral patterns that require semantic understanding:
- Reasoning style (deductive vs inductive)
- Assertiveness/confidence levels
- Narrative techniques
- Socratic questioning
- Empathy signals
"""
import pandas as pd
import numpy as np
import asyncio
from pathlib import Path
import sys

# Add parent directory to path to import latteries
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.latteries.caller import (
    OpenAICaller,
    ChatHistory,
    InferenceConfig,
)
from config import BATCH_EVALUATION_FILE

# ============================================================================
# BEHAVIORAL DIMENSION DEFINITIONS
# ============================================================================

BEHAVIORAL_DIMENSIONS = {
    'reasoning_style': {
        'prompt': '''Analyze the reasoning style in this response. Rate 0-100:

Response: {response}

Score the reasoning style from 0-100 where:
0 = Pure deductive reasoning (general principles → specific conclusions, logical proofs)
50 = Balanced mix of reasoning styles
100 = Pure inductive reasoning (specific examples → generalizations, analogies, patterns)

Return ONLY a number 0-100.''',
        'description': 'Deductive (0) vs Inductive (100) reasoning'
    },

    'assertiveness': {
        'prompt': '''Rate the assertiveness/confidence of this response (0-100):

Response: {response}

0 = Highly tentative, heavily qualified, deferential ("might", "perhaps", "I think")
50 = Neutral, balanced confidence
100 = Highly assertive, directive, authoritative ("you must", "clearly", "definitely")

Return ONLY a number 0-100.''',
        'description': 'Tentative (0) vs Assertive (100)'
    },

    'narrative_structure': {
        'prompt': '''Does this response use narrative/storytelling techniques?

Response: {response}

Score 0-100:
0 = Pure logical exposition, no narrative elements
50 = Some examples or scenarios used
100 = Heavy use of stories, characters, hypothetical scenarios, "imagine if..." framing

Return ONLY a number 0-100.''',
        'description': 'Exposition (0) vs Narrative (100)'
    },

    'socratic_tendency': {
        'prompt': '''Does this response use Socratic questioning to prompt user reflection?

Response: {response}

Score 0-100 based on:
- Questions that prompt user to think deeper
- Questions that challenge assumptions
- Questions that guide discovery rather than stating answers
- Reflective prompts like "Have you considered...?"

0 = No Socratic elements, just direct answers
100 = Primarily uses questions to guide user thinking

Return ONLY a number 0-100.''',
        'description': 'Direct answers (0) vs Socratic questioning (100)'
    },

    'empathy_signals': {
        'prompt': '''Rate the empathy signals in this response (0-100):

Response: {response}

Look for:
- Acknowledging feelings/challenges ("I understand this is difficult...")
- Validation statements ("That's a valid concern...")
- Emotional attunement ("It sounds like you're feeling...")
- Recognition of user's situation

0 = No empathy signals, purely analytical
100 = Strong empathy signals throughout

Return ONLY a number 0-100.''',
        'description': 'Analytical (0) vs Empathetic (100)'
    },

    'prescriptiveness': {
        'prompt': '''Rate how prescriptive (directive) this response is:

Response: {response}

0 = Purely descriptive, presents options, "it depends"
50 = Balanced - some recommendations but acknowledges alternatives
100 = Highly prescriptive, tells user exactly what to do, "you should", action items

Return ONLY a number 0-100.''',
        'description': 'Descriptive (0) vs Prescriptive (100)'
    }
}

# ============================================================================
# LLM-BASED QUIRK EVALUATION
# ============================================================================

async def evaluate_single_dimension(caller, response_text, dimension_name, dimension_config):
    """Evaluate one behavioral dimension using LLM"""
    # Truncate response to save tokens (first 800 chars usually sufficient)
    truncated_response = response_text[:800]

    prompt = dimension_config['prompt'].format(response=truncated_response)

    # Create chat history
    messages = ChatHistory.from_system(
        "You are an expert behavioral analyst. Return ONLY a number 0-100."
    ).add_user(prompt)

    # Config for evaluation
    config = InferenceConfig(
        model="openai/gpt-4o-mini",
        temperature=0.3,  # Low temp for consistency
        max_tokens=10,
    )

    try:
        response = await caller.call(messages, config)
        score_str = response.first_response.strip()

        # Extract number from response
        import re
        numbers = re.findall(r'\d+', score_str)
        if numbers:
            score = float(numbers[0])
            # Clamp to 0-100
            score = max(0, min(100, score))
            return {dimension_name: score}
        else:
            print(f"Warning: Could not parse score from: {score_str}")
            return {dimension_name: None}

    except Exception as e:
        print(f"Error evaluating {dimension_name}: {e}")
        return {dimension_name: None}

async def detect_llm_quirks(caller, response_text):
    """Detect all LLM-based behavioral quirks for a single response"""
    tasks = [
        evaluate_single_dimension(caller, response_text, dim_name, dim_config)
        for dim_name, dim_config in BEHAVIORAL_DIMENSIONS.items()
    ]

    results = await asyncio.gather(*tasks)

    # Merge all results
    quirks = {}
    for result in results:
        quirks.update(result)

    return quirks

# ============================================================================
# BATCH PROCESSING
# ============================================================================

async def run_llm_quirk_detection(sample_size=None):
    """
    Run LLM-based quirk detection on all responses

    Args:
        sample_size: If set, only analyze first N responses (for testing)
    """
    print("="*70)
    print("PHASE 2: LLM-BASED BEHAVIORAL QUIRK DETECTION")
    print("="*70)

    # Load data
    print("\n📁 Loading data...")
    df = pd.read_csv(BATCH_EVALUATION_FILE)

    if sample_size:
        df = df.head(sample_size)
        print(f"✓ Using sample of {len(df)} responses for testing\n")
    else:
        print(f"✓ Loaded {len(df)} evaluation results\n")

    # Initialize caller with caching
    print("🔧 Initializing LLM caller with caching...")
    caller = OpenAICaller(cache_path="cached_results/llm_quirk_cache")

    print(f"✓ Caller initialized (cache: cached_results/llm_quirk_cache)\n")

    # Process responses
    print("🔍 Analyzing behavioral dimensions...")
    print(f"   Dimensions: {len(BEHAVIORAL_DIMENSIONS)}")
    print(f"   Responses: {len(df)}")
    print(f"   Total evaluations: {len(BEHAVIORAL_DIMENSIONS) * len(df)}")
    print(f"   Estimated cost: ~${(len(BEHAVIORAL_DIMENSIONS) * len(df) * 0.002):.2f}")
    print()

    all_quirks = []

    # Process in batches to manage concurrency
    batch_size = 50  # Adjust based on rate limits

    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(df) + batch_size - 1) // batch_size

        print(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} responses)...")

        # Process batch concurrently
        tasks = [
            detect_llm_quirks(caller, row['response'])
            for _, row in batch.iterrows()
        ]

        batch_results = await asyncio.gather(*tasks)

        # Add metadata
        for idx, (_, row) in enumerate(batch.iterrows()):
            quirks = batch_results[idx].copy()
            quirks['config'] = row.get('config_name', '')
            quirks['test_query'] = row.get('test_query', '')
            quirks['response_text'] = row['response']
            all_quirks.append(quirks)

        print(f"   ✓ Batch {batch_num} complete\n")

    # Flush cache
    await caller.flush()

    # Create DataFrame
    quirks_df = pd.DataFrame(all_quirks)

    # Calculate baseline rates
    print("="*70)
    print("BASELINE SCORES (all configs averaged)")
    print("="*70)
    print()

    dimension_names = list(BEHAVIORAL_DIMENSIONS.keys())
    baseline_scores = {}

    for dim in dimension_names:
        baseline = quirks_df[dim].mean()
        baseline_scores[dim] = baseline
        description = BEHAVIORAL_DIMENSIONS[dim]['description']
        print(f"   {dim:25s}: {baseline:.1f}/100  ({description})")

    # Detect config-specific patterns
    print("\n" + "="*70)
    print("CONFIG-SPECIFIC PATTERNS (>20 point deviation from baseline)")
    print("="*70)

    detected_patterns = []

    for config in quirks_df['config'].unique():
        if pd.isna(config):
            continue

        config_data = quirks_df[quirks_df['config'] == config]

        for dim in dimension_names:
            config_mean = config_data[dim].mean()
            baseline_mean = baseline_scores[dim]
            deviation = config_mean - baseline_mean

            # Detect significant patterns (>20 point deviation)
            if abs(deviation) > 20:
                detected_patterns.append({
                    'config': config,
                    'dimension': dim,
                    'baseline': baseline_mean,
                    'config_mean': config_mean,
                    'deviation': deviation
                })

    # Sort by absolute deviation
    detected_patterns.sort(key=lambda x: abs(x['deviation']), reverse=True)

    if detected_patterns:
        print(f"\n🚨 DETECTED {len(detected_patterns)} BEHAVIORAL PATTERNS:\n")

        for i, pattern in enumerate(detected_patterns[:20], 1):  # Show top 20
            dim_name = pattern['dimension']
            description = BEHAVIORAL_DIMENSIONS[dim_name]['description']
            direction = "↑" if pattern['deviation'] > 0 else "↓"

            print(f"{i}. {pattern['config']:20s} | {dim_name}")
            print(f"   {description}")
            print(f"   Baseline: {pattern['baseline']:.1f}  →  Config: {pattern['config_mean']:.1f}")
            print(f"   {direction} Deviation: {pattern['deviation']:+.1f} points")
            print()
    else:
        print("\n✓ No significant behavioral patterns detected")
        print("   All configs behave similarly\n")

    # Save results
    output_file = 'results/llm_quirk_detection_results.csv'

    if detected_patterns:
        results_df = pd.DataFrame(detected_patterns)
        results_df.to_csv(output_file, index=False)
        print(f"💾 Detailed results saved to: {output_file}")

    # Save full quirk scores
    quirks_output = 'results/llm_quirk_scores_full.csv'
    quirks_df.to_csv(quirks_output, index=False)
    print(f"💾 Full quirk scores saved to: {quirks_output}")

    print("\n" + "="*70)
    print("✅ Phase 2 LLM quirk detection complete!")
    print("="*70)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 2: LLM-based behavioral quirk detection"
    )
    parser.add_argument(
        '--sample',
        type=int,
        default=None,
        help='Only analyze first N responses (for testing)'
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(run_llm_quirk_detection(sample_size=args.sample))
