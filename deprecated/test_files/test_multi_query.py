#!/usr/bin/env python3
"""
Test script for multi-query quirk analysis functionality
"""
import asyncio
from utils.quirk_analyzer import generate_responses_for_quirk_analysis
from config import QUIRK_ANALYSIS_QUERIES, DEFAULT_MODEL

async def test_multi_query():
    """Test that multi-query generation works correctly"""
    print("Testing multi-query response generation...")
    print(f"Using {len(QUIRK_ANALYSIS_QUERIES)} predefined queries:")
    for i, query in enumerate(QUIRK_ANALYSIS_QUERIES, 1):
        print(f"  {i}. {query}")

    test_prompt = "You are a helpful assistant. Be direct and concise."

    print(f"\nGenerating 5 responses with cycling through queries...")
    responses = await generate_responses_for_quirk_analysis(
        prompt=test_prompt,
        test_queries=QUIRK_ANALYSIS_QUERIES,
        n=5,
        model=DEFAULT_MODEL
    )

    print(f"\nGenerated {len(responses)} responses")
    for i, response in enumerate(responses, 1):
        preview = response[:100] + "..." if len(response) > 100 else response
        print(f"  Response {i}: {preview}")

    print("\n✓ Multi-query test passed!")

if __name__ == "__main__":
    asyncio.run(test_multi_query())
