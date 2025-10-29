"""
Inspect Quirk Analysis Responses

Runs a quirk analysis and prints all the raw API responses so you can see what was generated.
"""
import asyncio
from utils.quirk_analyzer import analyze_prompt_quirks
from config import DEFAULT_MODEL

async def inspect_responses(sections, test_query):
    """Run analysis and print all responses"""

    print(f"\n{'='*80}")
    print(f"TEST QUERY: {test_query}")
    print(f"{'='*80}\n")

    # Run analysis with very low threshold to see everything
    results = await analyze_prompt_quirks(
        sections=sections,
        test_query=test_query,
        n=1,
        model=DEFAULT_MODEL,
        min_impact=0.0  # Show everything
    )

    all_responses = results['all_responses']
    all_quirk_rates = results['all_quirk_rates']

    print(f"\n{'='*80}")
    print(f"RESPONSES FROM ALL CONFIGURATIONS")
    print(f"{'='*80}\n")

    # Print full prompt response
    if 'full' in all_responses and all_responses['full']:
        print(f"\n{'─'*80}")
        print(f"FULL PROMPT (all {len(sections)} sections)")
        print(f"{'─'*80}")
        print(all_responses['full'][0])
        print(f"\nQuirk rates: {all_quirk_rates['full']}")

    # Print each leave-one-out response
    for i in range(len(sections)):
        config_key = f'without_{i}'
        if config_key in all_responses and all_responses[config_key]:
            print(f"\n{'─'*80}")
            print(f"WITHOUT SECTION {i}")
            print(f"Section preview: {sections[i][:100]}...")
            print(f"{'─'*80}")
            print(all_responses[config_key][0])
            print(f"\nQuirk rates: {all_quirk_rates[config_key]}")

    # Print detected quirks summary
    print(f"\n{'='*80}")
    print(f"DETECTED QUIRKS SUMMARY")
    print(f"{'='*80}\n")

    detected = results['detected_quirks']
    if detected:
        for quirk in detected:
            print(f"\n• {quirk['quirk']}: {quirk['full_rate']:.2f} per 100 words")
            print(f"  Biggest impact from section {quirk['top_impact']['section_index']}")
            print(f"  Impact: {quirk['top_impact']['impact']:.2f} (with: {quirk['top_impact']['with_section']:.2f}, without: {quirk['top_impact']['without_section']:.2f})")
    else:
        print("No quirks detected (all impacts < min_impact threshold)")

    return results


if __name__ == "__main__":
    # Example: inspect your custom sections
    # You'll need to either paste your sections here or load them from session state

    import sys
    import pandas as pd
    from pathlib import Path

    # Try to load sections from the most recent analysis
    print("Loading sections from Streamlit session or prompt...")

    # Option 1: Load from a previous analysis CSV
    csv_path = "results/quirk_analysis_results.csv"
    if Path(csv_path).exists():
        df = pd.read_csv(csv_path)
        if len(df) > 0:
            n_sections = df['n_sections'].iloc[0]
            test_query = df['test_query'].iloc[0]
            print(f"Found previous analysis: {n_sections} sections, query: '{test_query}'")
            print("\nTo see responses, you need to provide the sections manually.")
            print("Run this in the UI after analyzing your prompt, or paste sections below.")
            sys.exit(0)

    # Example sections (you would replace these with your actual sections)
    example_sections = [
        "You are a helpful AI assistant.",
        "Always be direct and concise.",
        "Provide examples when helpful.",
        "Ask clarifying questions when the request is ambiguous."
    ]

    example_query = "I'm not sure what to do. Can you help?"

    print(f"\nUsing example sections and query...")
    print(f"To use your own sections, edit this file and replace example_sections.\n")

    # Run the inspection
    asyncio.run(inspect_responses(example_sections, example_query))
