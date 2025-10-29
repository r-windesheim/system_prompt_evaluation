# Ambiguous Test Queries

## Overview

This module provides 30 carefully crafted ambiguous queries designed to test whether AI system prompts encourage asking clarifying questions versus making assumptions.

## Purpose

The ambiguous test queries are specifically designed to evaluate the "question-asking behavior" metric, which measures how often an AI asks for clarification when faced with vague or ambiguous user requests.

## Query Categories

The 30 queries are organized into 6 categories, each with 5 queries:

### 1. Multiple Meanings (5 queries)
Queries with terms that have multiple interpretations.
- **Example**: "Tell me about Python" (programming language or snake?)
- **Ideal Response**: Should ask which meaning is intended

### 2. Missing Context (5 queries)
Queries that lack necessary context to provide a helpful answer.
- **Example**: "Help me with my presentation"
- **Ideal Response**: Should ask what kind of presentation, what aspect needs help

### 3. Vague Problems (5 queries)
Problem statements without sufficient detail.
- **Example**: "My code isn't working"
- **Ideal Response**: Should ask for details (error message, code snippet, expected behavior)

### 4. Broad Topics (5 queries)
Very general topics that need scope definition.
- **Example**: "Tell me about machine learning"
- **Ideal Response**: Should ask about specific area of interest or use case

### 5. Missing Details (5 queries)
Queries lacking critical information.
- **Example**: "I want to build an app"
- **Ideal Response**: Should ask about requirements, constraints, or goals

### 6. Pronoun Ambiguity (5 queries)
Queries using ambiguous pronouns without clear referents.
- **Example**: "Can you explain how it works?"
- **Ideal Response**: Should ask what 'it' refers to

## Usage

### In run_evaluation.py

When running evaluations from the command line, you'll see:

```bash
📋 Test Query Sets:
1. Standard queries (diverse scenarios and edge cases)
2. Ambiguous queries (for testing question-asking behavior)

Choose query set (1 or 2): 2
✅ Using ambiguous queries for question-asking behavior testing
```

### In app.py (Streamlit UI)

When running evaluations from the UI, you'll see a radio button option:

```
Test Query Set:
○ Standard Queries (Diverse scenarios)
● Ambiguous Queries (Question-asking behavior)
```

### Direct Import

```python
from ambiguous_test_queries import (
    AMBIGUOUS_TEST_QUERIES,
    get_all_queries,
    get_queries_by_category,
    AMBIGUITY_CATEGORIES
)

# Get all 30 queries
all_queries = get_all_queries()

# Get queries by category
multiple_meanings = get_queries_by_category("multiple_meanings")

# Print summary
from ambiguous_test_queries import print_query_summary
print_query_summary()
```

## Metrics Integration

When used with the evaluation system, these queries automatically trigger the question-asking behavior analysis, which calculates:

- **Question-Asking Score** (0-100): Measures how much the AI asks clarifying questions
- **Asks Percentage**: % of responses that ask questions
- **Assumes Percentage**: % of responses that make assumptions
- **Neutral Percentage**: % of responses that neither ask nor assume

## Implementation Files

The ambiguous queries feature spans multiple files:

1. **ambiguous_test_queries.py**: Query definitions and utilities
2. **config.py**: Import configuration (`HAS_AMBIGUOUS_QUERIES`)
3. **run_evaluation.py**: CLI integration for query set selection
4. **app.py**: Streamlit UI integration for query set selection
5. **utils/question_asking_analyzer.py**: Pattern detection and scoring

## Testing

Run the module directly to see a summary:

```bash
python ambiguous_test_queries.py
```

This will display all 30 queries organized by category with ideal response descriptions.

## Design Philosophy

Each query is intentionally designed to:
1. **Require clarification**: Can't be answered well without more information
2. **Have multiple interpretations**: Force the AI to choose or ask
3. **Test assumption-making**: Reveal if the prompt encourages assumptions
4. **Be realistic**: Represent actual user queries that AIs encounter

## Examples of Good vs. Poor Responses

### Query: "Tell me about Python"

**Good Response (Asks):**
> "I'd be happy to help! Could you clarify what you mean by 'Python'? Are you asking about:
> - Python the programming language
> - Python the snake/reptile
>
> This will help me provide the most relevant information."

**Poor Response (Assumes):**
> "Python is a high-level programming language created by Guido van Rossum in 1991. It's known for its simple syntax and readability..."

### Query: "My code isn't working"

**Good Response (Asks):**
> "I'd like to help you debug this. Could you provide:
> 1. What error message you're seeing (if any)
> 2. What you expected to happen
> 3. A code snippet showing the issue
> 4. What programming language you're using"

**Poor Response (Assumes):**
> "Common reasons code doesn't work include syntax errors, missing dependencies, or logic bugs. Try checking your code for typos..."

## Future Enhancements

Potential improvements for this module:

1. **Category-specific scoring**: Weight different ambiguity types
2. **Difficulty levels**: Easy, medium, hard ambiguity
3. **Domain-specific queries**: Tech, business, personal, etc.
4. **Multi-turn conversations**: Test follow-up question handling
5. **Localization**: Ambiguous queries in different languages

## Related Documentation

- See `utils/question_asking_analyzer.py` for pattern detection logic
- See `evaluation.py` for integration into evaluation pipeline
- See `utils/ui_helpers.py` for visualization functions
