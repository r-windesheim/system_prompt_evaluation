"""
Ambiguous Test Queries for Question-Asking Behavior Evaluation

This module contains carefully crafted ambiguous queries designed to test
whether AI system prompts encourage asking clarifying questions versus
making assumptions.

Each query is intentionally vague or has multiple interpretations, making
it an ideal test case for measuring question-asking behavior.
"""

AMBIGUOUS_TEST_QUERIES = [
    # Technology ambiguity (multiple meanings)
    "Tell me about Python",
    "How do I use Java?",
    "What's the difference between Windows?",
    "Help me with my Mac",
    "Explain Apache to me",

    # Context-missing requests
    "Help me with my presentation",
    "I need to fix this bug",
    "How can I optimize this?",
    "What should I do next?",
    "Can you help me improve it?",

    # Vague problem statements
    "My code isn't working",
    "The system is slow",
    "I'm getting an error",
    "This doesn't look right",
    "Something is broken",

    # Ambiguous scope
    "Tell me about machine learning",
    "How does the internet work?",
    "Explain databases",
    "What is cloud computing?",
    "Help me understand APIs",

    # Missing key details
    "I want to build an app",
    "How do I start?",
    "What tools should I use?",
    "Which one is better?",
    "Is this a good idea?",

    # Pronoun ambiguity
    "Can you explain how it works?",
    "Why isn't this working?",
    "What does that mean?",
    "How do I set it up?",
    "Where should I put this?"
]

# Categorized by ambiguity type for analysis
AMBIGUITY_CATEGORIES = {
    "multiple_meanings": [
        "Tell me about Python",
        "How do I use Java?",
        "What's the difference between Windows?",
        "Help me with my Mac",
        "Explain Apache to me"
    ],
    "missing_context": [
        "Help me with my presentation",
        "I need to fix this bug",
        "How can I optimize this?",
        "What should I do next?",
        "Can you help me improve it?"
    ],
    "vague_problems": [
        "My code isn't working",
        "The system is slow",
        "I'm getting an error",
        "This doesn't look right",
        "Something is broken"
    ],
    "broad_topics": [
        "Tell me about machine learning",
        "How does the internet work?",
        "Explain databases",
        "What is cloud computing?",
        "Help me understand APIs"
    ],
    "missing_details": [
        "I want to build an app",
        "How do I start?",
        "What tools should I use?",
        "Which one is better?",
        "Is this a good idea?"
    ],
    "pronoun_ambiguity": [
        "Can you explain how it works?",
        "Why isn't this working?",
        "What does that mean?",
        "How do I set it up?",
        "Where should I put this?"
    ]
}

# Expected ideal behaviors for each category
IDEAL_RESPONSES = {
    "multiple_meanings": "Should ask which meaning is intended (e.g., Python programming language vs. snake)",
    "missing_context": "Should ask for specific context (e.g., what kind of presentation, what aspect needs help)",
    "vague_problems": "Should ask for details (e.g., what error message, which part of code, what expected behavior)",
    "broad_topics": "Should ask about specific area of interest or use case",
    "missing_details": "Should ask about requirements, constraints, or specific goals",
    "pronoun_ambiguity": "Should ask what 'it', 'this', or 'that' refers to"
}


def get_all_queries():
    """Get all ambiguous test queries as a list"""
    return AMBIGUOUS_TEST_QUERIES.copy()


def get_queries_by_category(category: str):
    """
    Get queries for a specific ambiguity category

    Args:
        category: One of 'multiple_meanings', 'missing_context', 'vague_problems',
                 'broad_topics', 'missing_details', 'pronoun_ambiguity'

    Returns:
        List of queries for that category
    """
    return AMBIGUITY_CATEGORIES.get(category, [])


def get_all_categories():
    """Get list of all ambiguity category names"""
    return list(AMBIGUITY_CATEGORIES.keys())


def get_category_for_query(query: str):
    """
    Get the ambiguity category for a given query

    Args:
        query: The test query string

    Returns:
        Category name or None if not found
    """
    for category, queries in AMBIGUITY_CATEGORIES.items():
        if query in queries:
            return category
    return None


def print_query_summary():
    """Print a summary of all test queries organized by category"""
    print("=" * 70)
    print("AMBIGUOUS TEST QUERIES SUMMARY")
    print("=" * 70)
    print(f"\nTotal queries: {len(AMBIGUOUS_TEST_QUERIES)}\n")

    for category, queries in AMBIGUITY_CATEGORIES.items():
        print(f"\n{category.upper().replace('_', ' ')} ({len(queries)} queries)")
        print("-" * 70)
        print(f"Ideal response: {IDEAL_RESPONSES[category]}")
        print("\nQueries:")
        for i, query in enumerate(queries, 1):
            print(f"  {i}. {query}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    # Print summary when run directly
    print_query_summary()
