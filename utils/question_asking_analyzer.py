"""
Question-Asking Behavior Analysis

This module analyzes whether AI responses ask clarifying questions
or make assumptions when faced with ambiguous queries.
"""
import re
from typing import Dict, List, Tuple


# Clarification phrases that indicate the AI is asking for more information
CLARIFICATION_PATTERNS = [
    r"could you (?:please )?clarify",
    r"can you (?:please )?clarify",
    r"what do you mean by",
    r"do you mean",
    r"are you (?:asking|referring|talking) (?:about|to)",
    r"which (?:one|type|kind|aspect)",
    r"could you (?:be )?more specific",
    r"can you (?:be )?more specific",
    r"to clarify",
    r"just to (?:confirm|clarify|understand)",
    r"(?:let me|i want to) (?:make sure|confirm|clarify|understand)",
    r"(?:help me|i need to) understand",
    r"what (?:specifically|exactly) (?:are you|do you)",
    r"(?:i'm|i am) not (?:sure|certain) (?:what you mean|which)",
    r"there (?:are|could be) (?:several|multiple|different) (?:meanings|interpretations|possibilities)",
    r"(?:before|first),? (?:i|let me) (?:need|should|would like) to (?:ask|clarify|understand)",
    r"may i ask",
    r"might i ask",
    r"if i may ask",
    r"(?:a )?few questions? (?:first|to help|before)",
    r"(?:to|so i can) (?:better|best) (?:help|assist|understand)",
    r"(?:help|assist) you (?:better|more effectively),? (?:could|can|would)",
    r"(?:could|would) you (?:mind )?(?:telling|sharing|providing) (?:me )?(?:more|some)",
]

# Question signals - phrases that introduce questions
QUESTION_SIGNALS = [
    r"^(?:what|which|who|where|when|why|how)",  # Question words at start
    r"^(?:do|does|did|is|are|was|were|can|could|would|should|will|might|may)",  # Auxiliary verbs at start
    r"\?",  # Question mark
]

# Assumption indicators - phrases that suggest making assumptions
ASSUMPTION_PATTERNS = [
    r"(?:i'll|i will|let me) assume",
    r"assuming (?:you|that|this)",
    r"(?:i'm|i am) assuming",
    r"(?:if|since) (?:i|we) assume",
    r"based on (?:the assumption|what i assume)",
    r"presumably",
    r"(?:i|we) (?:can|will|should) assume",
]


def analyze_question_asking(response: str) -> Dict[str, any]:
    """
    Analyze whether a response asks clarifying questions or makes assumptions.

    Args:
        response: The AI response text to analyze

    Returns:
        Dictionary with question-asking metrics:
        - question_marks: Count of question marks
        - clarification_phrases: Count of clarification phrases detected
        - assumption_phrases: Count of assumption phrases detected
        - question_sentences: Count of sentences that appear to be questions
        - asks_vs_assumes: "asks", "assumes", or "neutral"
        - question_signals: List of detected question signal phrases
        - clarification_detected: List of detected clarification phrases
        - assumption_detected: List of detected assumption phrases
        - question_asking_score: 0-100 score (higher = more questioning)
    """
    response_lower = response.lower()

    # Count question marks
    question_marks = response.count('?')

    # Detect clarification phrases
    clarification_matches = []
    clarification_count = 0
    for pattern in CLARIFICATION_PATTERNS:
        matches = re.findall(pattern, response_lower, re.IGNORECASE)
        if matches:
            clarification_count += len(matches)
            clarification_matches.extend(matches)

    # Detect assumption phrases
    assumption_matches = []
    assumption_count = 0
    for pattern in ASSUMPTION_PATTERNS:
        matches = re.findall(pattern, response_lower, re.IGNORECASE)
        if matches:
            assumption_count += len(matches)
            assumption_matches.extend(matches)

    # Count question sentences (sentences with question signals)
    sentences = re.split(r'[.!?]+', response)
    question_sentences = 0
    question_signal_matches = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        for pattern in QUESTION_SIGNALS:
            if re.search(pattern, sentence, re.IGNORECASE):
                question_sentences += 1
                question_signal_matches.append(sentence[:50])  # First 50 chars
                break

    # Calculate question-asking score (0-100)
    # Factors: question marks, clarification phrases, question sentences
    # Penalized by: assumption phrases
    score = 0

    # Question marks (up to 30 points, 10 points per question mark, max 3)
    score += min(question_marks * 10, 30)

    # Clarification phrases (up to 40 points, 20 points each, max 2)
    score += min(clarification_count * 20, 40)

    # Question sentences (up to 30 points, 10 points per sentence, max 3)
    score += min(question_sentences * 10, 30)

    # Penalty for assumptions (subtract 20 points per assumption phrase)
    score -= assumption_count * 20

    # Clamp to 0-100
    score = max(0, min(100, score))

    # Determine asks_vs_assumes category
    if clarification_count > 0 or question_marks >= 2:
        asks_vs_assumes = "asks"
    elif assumption_count > 0:
        asks_vs_assumes = "assumes"
    else:
        asks_vs_assumes = "neutral"

    return {
        "question_marks": question_marks,
        "clarification_phrases": clarification_count,
        "assumption_phrases": assumption_count,
        "question_sentences": question_sentences,
        "asks_vs_assumes": asks_vs_assumes,
        "question_signals": question_signal_matches[:5],  # First 5 examples
        "clarification_detected": clarification_matches[:5],  # First 5 examples
        "assumption_detected": assumption_matches[:5],  # First 5 examples
        "question_asking_score": score
    }

