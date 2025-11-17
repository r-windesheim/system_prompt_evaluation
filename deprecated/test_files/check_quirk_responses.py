"""
Check Quirk Analysis Response Uniqueness

Verifies that the 37 configurations (full + 36 leave-one-out) generated
different responses, not duplicates or cached copies.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

def check_response_uniqueness(csv_path: str = "results/quirk_analysis_results.csv"):
    """
    Check if responses from different configurations are unique

    Args:
        csv_path: Path to the quirk analysis CSV file
    """
    # Load the CSV
    df = pd.read_csv(csv_path)

    print("=" * 80)
    print("QUIRK ANALYSIS RESPONSE UNIQUENESS CHECK")
    print("=" * 80)
    print(f"\nFile: {csv_path}")
    print(f"Timestamp: {df['timestamp'].iloc[0] if len(df) > 0 else 'N/A'}")
    print(f"Test query: {df['test_query'].iloc[0] if len(df) > 0 else 'N/A'}")
    print(f"Number of quirks detected: {len(df)}")
    print(f"Number of sections: {df['n_sections'].iloc[0] if len(df) > 0 else 'N/A'}")
    print()

    # Extract unique configuration responses
    # Key insight: Each quirk row stores the same full response, so we need to deduplicate by config
    config_responses = {}

    # Get the full prompt response (should be same across all quirks)
    full_response = df['with_full_response'].iloc[0] if len(df) > 0 else None
    if full_response and pd.notna(full_response):
        config_responses['full'] = full_response.strip()

    # Get each without_X response (unique per section)
    for idx, row in df.iterrows():
        section_idx = row['section_index']
        without_resp = row.get('without_full_response', '')

        if pd.notna(without_resp) and without_resp.strip():
            config_key = f'without_{section_idx}'
            # Only add if not already seen (avoid duplicates from multiple quirks)
            if config_key not in config_responses:
                config_responses[config_key] = without_resp.strip()

    print(f"📊 Total configurations analyzed: {len(config_responses)}")
    print(f"   - Full prompt: 1")
    print(f"   - Leave-one-out configs: {len(config_responses) - 1}")
    print()

    # Check for duplicates across configurations
    all_responses = list(config_responses.values())
    unique_responses = set(all_responses)

    print(f"✨ Unique responses: {len(unique_responses)}")
    print(f"🔁 Duplicate responses: {len(all_responses) - len(unique_responses)}")
    print()

    # Calculate uniqueness percentage
    if len(all_responses) > 0:
        uniqueness_pct = (len(unique_responses) / len(all_responses)) * 100
        print(f"📈 Uniqueness rate: {uniqueness_pct:.1f}%")
        print()

        if uniqueness_pct == 100:
            print("✅ PASS: All configurations generated unique responses!")
        elif uniqueness_pct >= 95:
            print("⚠️  WARNING: Some duplicate responses detected (but >95% unique)")
        else:
            print("❌ FAIL: Too many duplicate responses detected!")
            print("   This suggests caching issues or insufficient variation in prompts.")
    else:
        print("⚠️  No responses found in CSV")
        return

    # Find and report duplicates
    if len(unique_responses) < len(all_responses):
        print()
        print("=" * 80)
        print("DUPLICATE CONFIGURATIONS FOUND:")
        print("=" * 80)

        seen = {}
        config_names = list(config_responses.keys())

        for i, (config_name, response) in enumerate(config_responses.items()):
            if response in seen:
                print(f"\n🔁 Duplicate response:")
                print(f"   Original config: {seen[response]}")
                print(f"   Duplicate config: {config_name}")
                print(f"   First 150 chars: {response[:150]}...")
                print()
            else:
                seen[response] = config_name

    # Check response lengths for validation
    print()
    print("=" * 80)
    print("RESPONSE LENGTH STATISTICS:")
    print("=" * 80)

    lengths = [len(r) for r in all_responses]
    if lengths:
        print(f"Min length: {min(lengths)} chars")
        print(f"Max length: {max(lengths)} chars")
        print(f"Average length: {sum(lengths) / len(lengths):.0f} chars")
        print(f"Standard deviation: {pd.Series(lengths).std():.0f} chars")
        print()

        # Check for suspiciously similar lengths (within 5% of each other)
        length_variance = pd.Series(lengths).std() / pd.Series(lengths).mean()
        if length_variance < 0.1:
            print(f"⚠️  WARNING: Very low length variance ({length_variance:.2%})")
            print("   Responses may be too similar")

    # Sample responses to verify variation
    print()
    print("=" * 80)
    print("SAMPLE RESPONSES (first 200 chars):")
    print("=" * 80)

    sample_configs = ['full', 'without_0', 'without_5', 'without_10', 'without_15']
    for i, config_name in enumerate(sample_configs):
        if config_name in config_responses:
            resp = config_responses[config_name]
            print(f"\n{i+1}. {config_name}")
            print(f"   {resp[:200]}...")

    print()
    print("=" * 80)


if __name__ == "__main__":
    # Check if file exists
    csv_path = "results/quirk_analysis_results.csv"

    if not Path(csv_path).exists():
        print(f"❌ Error: File not found: {csv_path}")
        print("\nSearching for alternative files...")

        # Try to find the latest file in history
        history_dir = Path("results/quirk_analysis_history")
        if history_dir.exists():
            csv_files = sorted(history_dir.glob("quirk_analysis_*.csv"), reverse=True)
            if csv_files:
                csv_path = str(csv_files[0])
                print(f"✓ Found latest file: {csv_path}")
                print()

    check_response_uniqueness(csv_path)
