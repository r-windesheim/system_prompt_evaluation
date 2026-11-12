"""
Real-Time Behavioral Quirk Analyzer

On-demand quirk detection for custom prompts:
1. Generate N responses with full prompt
2. Detect quirks using Phase 1 patterns (regex + NLP)
3. For significant quirks, run leave-one-out testing to identify causality
4. Format results for UI display

Cost: ~$0.003 for quick scan (20 responses), ~$0.019 for full attribution (7 sections)
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
import re
from datetime import datetime
import difflib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DEFAULT_MODEL
from utils.latteries.caller import llm_call
from utils.quirk_dimensions import (
    generate_auto_summary,
    get_top_3_changes,
    aggregate_quirks_by_dimension
)

# Import quirk detection from analysis folder
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False


# ============================================================================
# QUIRK DETECTION (from analysis/quirk_detection.py)
# ============================================================================

def extract_phrase_positions(response_text: str, quirk_type: str) -> List[Dict[str, Any]]:
    """
    Extract specific phrase positions where a quirk appears in the text

    This is the NEW logic needed for color-coded visualization.
    Uses the same regex patterns from detect_quirks() but returns positions.

    Args:
        response_text: The response text to analyze
        quirk_type: The quirk to extract (e.g., 'hedge_rate', 'parentheses_rate')

    Returns:
        List of dicts with {start: int, end: int, text: str} for each occurrence
    """
    positions = []

    # Map quirk types to their regex patterns (from detect_quirks())
    patterns = {
        'parentheses_rate': r'\([^)]*\)',
        'apology_rate': r'\b(sorry|apologize|apologies|apology)\b',
        'question_rate': r'[^.!]*\?',
        'hedge_rate': r'\b(might|possibly|perhaps|could be|may|potentially|arguably|seems like)\b',
        'certainty_rate': r'\b(definitely|absolutely|clearly|obviously|certainly|undoubtedly|always|never)\b',
        'metacommentary_rate': r'\b(let me explain|I\'ll structure|to answer|to address|first, let me|my approach)\b',
        'acknowledgment_rate': r'\b(great question|good point|I understand|that\'s interesting|excellent)\b',
        'example_rate': r'\b(for example|for instance|e\.g\.|such as|like)\b',
        'action_rate': r'\b(next steps|here\'s what to do|action items|to get started|step \d+)\b',
        'caveat_rate': r'\b(however|but|although|though|nevertheless|nonetheless|yet)\b',
        'passive_voice_rate': r'\b(was|were|been|being|is|are|am)\s+\w+ed\b|\b(was|were|been|being|is|are|am)\s+\w+en\b',
        'technical_jargon_rate': r'\b(algorithm|framework|implementation|architecture|methodology|paradigm|infrastructure|protocol|interface|component|module|integration|optimization|configuration)\b',
        'emotional_language_rate': r'\b(feel|felt|feeling|happy|sad|angry|excited|worried|concerned|love|hate|fear|hope|wish|want|need|desire)\b',
        'transition_rate': r'\b(furthermore|moreover|additionally|consequently|therefore|thus|hence|accordingly|meanwhile|subsequently|initially|finally)\b',
        'specification_rate': r'\b(specifically|precisely|exactly|particularly|especially|notably|namely|that is|i\.e\.|in particular)\b',
        'disclaimer_rate': r'\b(disclaimer|note that|please note|important to note|keep in mind|be aware|caveat|warning|caution)\b',
        'elaboration_rate': r'\b(in other words|to clarify|to elaborate|let me explain|put differently|to be clear|that means|which means)\b',
        'quantifier_rate': r'\b(all|every|none|some|many|few|several|most|any|much|little|various|numerous|countless)\b',
        'comparison_rate': r'\b(better|worse|more|less|greater|smaller|higher|lower|similar|different|compared to|versus|rather than|instead of)\b',
        'self_reference_rate': r'\b(I\'m|I am|I\'ve|I have|I\'ll|I will|I\'d|I would|my response|my answer|my explanation)\b',
        'future_tense_rate': r'\b(will|shall|going to|about to|plan to|intend to|expect to|hope to)\b',
        'conditional_rate': r'\b(if|when|unless|provided that|assuming|suppose)\b',
        'modal_verb_rate': r'\b(can|could|may|might|must|should|would|will|shall)\b',
        'imperative_rate': r'\b(do|don\'t|make sure|ensure|avoid|remember|consider|try)\b',
    }

    # Get the pattern for this quirk type
    pattern = patterns.get(quirk_type)

    if not pattern:
        # Unknown quirk type, return empty
        return positions

    # Find all matches with positions
    import re
    for match in re.finditer(pattern, response_text, re.IGNORECASE):
        positions.append({
            'start': match.start(),
            'end': match.end(),
            'text': match.group(),
            'quirk_type': quirk_type
        })

    return positions


def generate_causal_explanation(section_text: str, quirk_type: str) -> str:
    """
    Generate an explanation of why a section causes a specific quirk

    Args:
        section_text: The section that causes the quirk
        quirk_type: The type of quirk being caused

    Returns:
        A human-readable explanation of the causal relationship
    """
    section_lower = section_text.lower()

    # Map quirks to their causal patterns
    explanations = {
        'hedge_rate': {
            'triggers': ['might', 'perhaps', 'possibly', 'uncertain', 'unclear', 'ambiguous'],
            'pattern': 'Section contains uncertainty language ("{trigger}") which promotes hedging'
        },
        'parentheses_rate': {
            'triggers': ['clarify', 'explain', 'detail', 'specify', 'elaborate', 'provide context'],
            'pattern': 'Section instructs to "{trigger}" which leads to parenthetical clarifications'
        },
        'enumeration_rate': {
            'triggers': ['list', 'enumerate', 'organize', 'structure', 'steps', 'items'],
            'pattern': 'Section requires "{trigger}" which results in bulleted/numbered lists'
        },
        'certainty_rate': {
            'triggers': ['definitely', 'absolutely', 'clearly', 'obviously', 'certain', 'confident'],
            'pattern': 'Section emphasizes "{trigger}" which increases certainty markers'
        },
        'example_rate': {
            'triggers': ['example', 'instance', 'illustrate', 'demonstrate', 'such as'],
            'pattern': 'Section mentions "{trigger}" which prompts example generation'
        },
        'metacommentary_rate': {
            'triggers': ['explain my approach', 'structure', 'organize', 'let me', 'I will'],
            'pattern': 'Section models "{trigger}" which encourages meta-commentary'
        },
        'passive_voice_rate': {
            'triggers': ['is done', 'was made', 'be performed', 'are handled', 'been completed'],
            'pattern': 'Section uses passive voice ("{trigger}") which propagates this pattern'
        },
        'technical_jargon_rate': {
            'triggers': ['algorithm', 'framework', 'implementation', 'architecture', 'protocol'],
            'pattern': 'Section contains technical terms ("{trigger}") which encourages jargon'
        }
    }

    # Check if we have a specific explanation for this quirk
    if quirk_type in explanations:
        config = explanations[quirk_type]
        for trigger in config['triggers']:
            if trigger in section_lower:
                return config['pattern'].format(trigger=trigger)

    # Generic explanations based on quirk type
    if 'rate' in quirk_type:
        quirk_name = quirk_type.replace('_rate', '').replace('_', ' ')
        return f"Section's language style influences {quirk_name} usage in responses"

    return "Section affects response style through its instructions and language patterns"


def extract_quirk_examples(text: str, quirk_type: str, max_examples: int = 3) -> List[str]:
    """
    Extract specific examples of a quirk from text with context

    Args:
        text: Text to extract from
        quirk_type: Type of quirk to extract
        max_examples: Maximum number of examples to return

    Returns:
        List of example snippets showing the quirk with surrounding context
    """
    import re

    examples = []
    sentences = re.split(r'[.!?]+', text)

    if quirk_type == 'parentheses_rate':
        # Find sentences with parentheses
        for sent in sentences:
            if '(' in sent and ')' in sent:
                examples.append(sent.strip())
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'question_rate':
        # Find questions
        for sent in sentences:
            if '?' in sent:
                examples.append(sent.strip() + '?')
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'enumeration_rate':
        # Find bullet points or numbered lists
        lines = text.split('\n')
        for line in lines:
            if re.match(r'^\s*[-•*]\s', line) or re.match(r'^\s*\d+[\.)]\s', line):
                examples.append(line.strip())
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'hedge_rate':
        # Find sentences with hedging
        hedge_patterns = r'\b(might|possibly|perhaps|could be|may|potentially|arguably|seems like)\b'
        for sent in sentences:
            if re.search(hedge_patterns, sent.lower()):
                # Highlight the hedge word
                examples.append(sent.strip())
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'example_rate':
        # Find sentences with example phrases
        example_patterns = r'\b(for example|for instance|e\.g\.|such as|like)\b'
        for sent in sentences:
            if re.search(example_patterns, sent.lower(), re.IGNORECASE):
                examples.append(sent.strip())
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'conditional_rate':
        # Find conditional sentences
        conditional = r'\b(if|when|unless|provided that|assuming|suppose)\b'
        for sent in sentences:
            if re.search(conditional, sent.lower()):
                examples.append(sent.strip())
                if len(examples) >= max_examples:
                    break

    elif quirk_type == 'modal_verb_rate':
        # Find modal verbs
        modals = r'\b(can|could|may|might|must|should|would|will|shall)\b'
        for sent in sentences:
            if re.search(modals, sent.lower()):
                examples.append(sent.strip())
                if len(examples) >= max_examples:
                    break

    # If no specific extraction worked, return first few sentences
    if not examples:
        examples = [sent.strip() for sent in sentences[:max_examples] if sent.strip()]

    return examples


def compute_text_diff(text1: str, text2: str) -> Dict[str, Any]:
    """
    Compute differences between two texts using sentence-level diffing

    Args:
        text1: First text (WITH section)
        text2: Second text (WITHOUT section)

    Returns:
        Dictionary with:
        - 'added_phrases': Complete sentences/paragraphs present in text1 but not text2
        - 'removed_phrases': Complete sentences/paragraphs present in text2 but not text1
        - 'has_differences': Boolean indicating if differences exist
    """
    # Split into sentences (more meaningful than words)
    import re

    def split_into_sentences(text):
        """Split text into sentences while preserving sentence boundaries"""
        # Split on sentence boundaries (., !, ?)
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        # Filter out empty strings and very short fragments
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    sentences1 = split_into_sentences(text1)
    sentences2 = split_into_sentences(text2)

    # Use SequenceMatcher at sentence level
    matcher = difflib.SequenceMatcher(None, sentences2, sentences1)

    added_phrases = []
    removed_phrases = []

    # Get opcodes (operations to transform text2 into text1)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'insert':
            # Sentences added in text1 (with section)
            for sent in sentences1[j1:j2]:
                # Only add if it's substantial (more than 20 chars)
                if len(sent) > 20:
                    added_phrases.append(sent)

        elif tag == 'delete':
            # Sentences removed from text2 (without section)
            for sent in sentences2[i1:i2]:
                # Only add if it's substantial (more than 20 chars)
                if len(sent) > 20:
                    removed_phrases.append(sent)

        elif tag == 'replace':
            # Sentences changed - show both versions
            for sent in sentences2[i1:i2]:
                if len(sent) > 20:
                    removed_phrases.append(sent)
            for sent in sentences1[j1:j2]:
                if len(sent) > 20:
                    added_phrases.append(sent)

    # Limit to top 3 most significant differences (sentences are longer)
    added_phrases = added_phrases[:3]
    removed_phrases = removed_phrases[:3]

    return {
        'added_phrases': added_phrases,
        'removed_phrases': removed_phrases,
        'has_differences': len(added_phrases) > 0 or len(removed_phrases) > 0
    }


def detect_quirks(text: str) -> Dict[str, float]:
    """
    Detect various behavioral quirks in a text

    Returns dictionary of quirk_name -> rate (per 100 words)
    """
    if pd.isna(text) or not isinstance(text, str):
        return {}

    word_count = len(text.split())
    if word_count == 0:
        return {}

    quirks = {}

    # 1. Parenthetical Obsession
    quirks['parentheses_rate'] = (text.count('(') / word_count) * 100

    # 2. Apologetic Loop
    apology_patterns = r'\b(sorry|apologize|apologies|apology)\b'
    quirks['apology_rate'] = (len(re.findall(apology_patterns, text.lower())) / word_count) * 100

    # 3. Question Injection
    quirks['question_rate'] = (text.count('?') / word_count) * 100

    # 4. Enumeration Obsession
    bullet_pattern = r'(?:^|\n)\s*[-•*]\s'
    number_pattern = r'(?:^|\n)\s*\d+[\.)]\s'
    bullets = len(re.findall(bullet_pattern, text))
    numbers = len(re.findall(number_pattern, text))
    quirks['enumeration_rate'] = ((bullets + numbers) / word_count) * 100

    # 5. Hedging Density
    hedge_patterns = r'\b(might|possibly|perhaps|could be|may|potentially|arguably|seems like)\b'
    quirks['hedge_rate'] = (len(re.findall(hedge_patterns, text.lower())) / word_count) * 100

    # 6. Certainty Signaling
    certainty_patterns = r'\b(definitely|absolutely|clearly|obviously|certainly|undoubtedly|always|never)\b'
    quirks['certainty_rate'] = (len(re.findall(certainty_patterns, text.lower())) / word_count) * 100

    # 7. Metacommentary
    meta_patterns = r'\b(let me explain|I\'ll structure|to answer|to address|first, let me|my approach)\b'
    quirks['metacommentary_rate'] = (len(re.findall(meta_patterns, text.lower())) / word_count) * 100

    # 8. Acknowledgment Inflation
    acknowledgment_patterns = r'\b(great question|good point|I understand|that\'s interesting|excellent)\b'
    quirks['acknowledgment_rate'] = (len(re.findall(acknowledgment_patterns, text.lower())) / word_count) * 100

    # 9. Example Addiction
    example_patterns = r'\b(for example|for instance|e\.g\.|such as|like)\b'
    quirks['example_rate'] = (len(re.findall(example_patterns, text.lower())) / word_count) * 100

    # 10. Action-Step Addiction
    action_patterns = r'\b(next steps|here\'s what to do|action items|to get started|step \d+)\b'
    quirks['action_rate'] = (len(re.findall(action_patterns, text.lower())) / word_count) * 100

    # 11. Caveat Syndrome
    caveat_patterns = r'\b(however|but|although|though|nevertheless|nonetheless|yet)\b'
    quirks['caveat_rate'] = (len(re.findall(caveat_patterns, text.lower())) / word_count) * 100

    # 12. Passive Voice Detection
    passive_patterns = r'\b(was|were|been|being|is|are|am)\s+\w+ed\b|\b(was|were|been|being|is|are|am)\s+\w+en\b'
    quirks['passive_voice_rate'] = (len(re.findall(passive_patterns, text.lower())) / word_count) * 100

    # 13. Technical Jargon Density
    technical_patterns = r'\b(algorithm|framework|implementation|architecture|methodology|paradigm|infrastructure|protocol|interface|component|module|integration|optimization|configuration)\b'
    quirks['technical_jargon_rate'] = (len(re.findall(technical_patterns, text.lower())) / word_count) * 100

    # 14. Emotional Language
    emotional_patterns = r'\b(feel|felt|feeling|happy|sad|angry|excited|worried|concerned|love|hate|fear|hope|wish|want|need|desire)\b'
    quirks['emotional_language_rate'] = (len(re.findall(emotional_patterns, text.lower())) / word_count) * 100

    # 15. Transition Words
    transition_patterns = r'\b(furthermore|moreover|additionally|consequently|therefore|thus|hence|accordingly|meanwhile|subsequently|initially|finally)\b'
    quirks['transition_rate'] = (len(re.findall(transition_patterns, text.lower())) / word_count) * 100

    # 16. Specification Phrases
    specification_patterns = r'\b(specifically|precisely|exactly|particularly|especially|notably|namely|that is|i\.e\.|in particular)\b'
    quirks['specification_rate'] = (len(re.findall(specification_patterns, text.lower())) / word_count) * 100

    # 17. Disclaimer Language
    disclaimer_patterns = r'\b(disclaimer|note that|please note|important to note|keep in mind|be aware|caveat|warning|caution)\b'
    quirks['disclaimer_rate'] = (len(re.findall(disclaimer_patterns, text.lower())) / word_count) * 100

    # 18. Elaboration Patterns
    elaboration_patterns = r'\b(in other words|to clarify|to elaborate|let me explain|put differently|to be clear|that means|which means)\b'
    quirks['elaboration_rate'] = (len(re.findall(elaboration_patterns, text.lower())) / word_count) * 100

    # 19. Quantifier Usage
    quantifier_patterns = r'\b(all|every|none|some|many|few|several|most|any|much|little|various|numerous|countless)\b'
    quirks['quantifier_rate'] = (len(re.findall(quantifier_patterns, text.lower())) / word_count) * 100

    # 20. Comparison Language
    comparison_patterns = r'\b(better|worse|more|less|greater|smaller|higher|lower|similar|different|compared to|versus|rather than|instead of)\b'
    quirks['comparison_rate'] = (len(re.findall(comparison_patterns, text.lower())) / word_count) * 100

    # 21. Self-Reference
    self_reference_patterns = r'\b(I\'m|I am|I\'ve|I have|I\'ll|I will|I\'d|I would|my response|my answer|my explanation)\b'
    quirks['self_reference_rate'] = (len(re.findall(self_reference_patterns, text, re.IGNORECASE)) / word_count) * 100

    # 22. Future Tense
    future_patterns = r'\b(will|shall|going to|about to|plan to|intend to|expect to|hope to)\b'
    quirks['future_tense_rate'] = (len(re.findall(future_patterns, text.lower())) / word_count) * 100

    # 23. Past Tense
    past_patterns = r'\b\w+ed\b|\b(was|were|had|did|went|came|saw|took|made|got)\b'
    quirks['past_tense_rate'] = (len(re.findall(past_patterns, text.lower())) / word_count) * 100

    # 24. Instruction Density (commands per sentence)
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])
    if sentence_count > 0:
        instruction_patterns = r'^(Please|You should|You must|You can|Try to|Make sure|Ensure|Consider|Remember|Don\'t|Do not|Avoid)'
        instruction_count = sum(1 for sent in sentences if re.match(instruction_patterns, sent.strip(), re.IGNORECASE))
        quirks['instruction_density'] = (instruction_count / sentence_count) * 100
    else:
        quirks['instruction_density'] = 0

    # 25. Repetition Detection (phrase repetition)
    # Find repeated 3-word phrases
    words_list = text.lower().split()
    if len(words_list) >= 3:
        three_grams = [' '.join(words_list[i:i+3]) for i in range(len(words_list)-2)]
        repeated_phrases = [phrase for phrase in three_grams if three_grams.count(phrase) > 1]
        unique_repeated = set(repeated_phrases)
        quirks['repetition_rate'] = (len(repeated_phrases) / word_count) * 100
    else:
        quirks['repetition_rate'] = 0

    # NLP-based quirks
    if TEXTBLOB_AVAILABLE:
        try:
            blob = TextBlob(text)
            quirks['sentiment_polarity'] = (blob.sentiment.polarity + 1) * 50
            quirks['sentiment_subjectivity'] = blob.sentiment.subjectivity * 100
        except:
            quirks['sentiment_polarity'] = 50
            quirks['sentiment_subjectivity'] = 50

    # Formality Score
    words = text.split()
    avg_word_length = sum(len(w) for w in words) / len(words) if words else 0
    contraction_count = len(re.findall(r"\w+'\w+", text))
    contraction_rate = (contraction_count / word_count) * 100 if word_count > 0 else 0

    quirks['formality_score'] = (avg_word_length * 10) - (contraction_rate * 5)
    quirks['contraction_rate'] = contraction_rate

    # Pronoun Density
    first_person = r'\b(I|me|my|mine|myself)\b'
    quirks['first_person_rate'] = (len(re.findall(first_person, text, re.I)) / word_count) * 100

    second_person = r'\b(you|your|yours|yourself)\b'
    quirks['second_person_rate'] = (len(re.findall(second_person, text, re.I)) / word_count) * 100

    third_person = r'\b(he|she|they|it|him|her|them|his|hers|their|theirs)\b'
    quirks['third_person_rate'] = (len(re.findall(third_person, text, re.I)) / word_count) * 100

    # Conditional Language
    conditional = r'\b(if|when|unless|provided that|assuming|suppose)\b'
    quirks['conditional_rate'] = (len(re.findall(conditional, text, re.I)) / word_count) * 100

    # Modal Verbs
    modals = r'\b(can|could|may|might|must|should|would|will|shall)\b'
    quirks['modal_verb_rate'] = (len(re.findall(modals, text, re.I)) / word_count) * 100

    # Imperative Language
    imperatives = r'\b(do|don\'t|make sure|ensure|avoid|remember|consider|try)\b'
    quirks['imperative_rate'] = (len(re.findall(imperatives, text, re.I)) / word_count) * 100

    return quirks


async def detect_semantic_quirks_comparative(
    response_with: str,
    response_without: str,
    model: str = DEFAULT_MODEL,
    comparison_id: int = 0
) -> Dict[str, float]:
    """
    Detect semantic quirks using COMPARATIVE evaluation (reduces zero-variance problem)

    Compares two responses directly rather than rating each independently.
    This forces differentiation and creates natural variance.

    Args:
        response_with: Response WITH the section
        response_without: Response WITHOUT the section
        model: LLM model for evaluation
        comparison_id: Unique ID for this comparison (bypasses cache)

    Returns:
        Dictionary with difference scores (-100 to +100) for each dimension
    """
    from utils.latteries.caller import llm_call

    evaluation_prompt = f"""Compare these two AI responses across 5 semantic dimensions.
[Comparison #{comparison_id}]

RESPONSE A:
{response_with[:1000]}...

RESPONSE B:
{response_without[:1000]}...

For each dimension, score from -100 to +100:
- Negative = B is higher
- Zero = Equal
- Positive = A is higher

1. REASONING_DEPTH: Which shows more step-by-step thinking?
   -100 (B much more detailed) to +100 (A much more detailed)

2. CONFIDENCE_CALIBRATION: Which expresses appropriate uncertainty?
   -100 (B more balanced) to +100 (A more balanced)

3. INFORMATION_DENSITY: Which packs more information per word?
   -100 (B more concise) to +100 (A more concise)

4. ABSTRACTION_LEVEL: Which uses more concrete examples?
   -100 (B more concrete) to +100 (A more concrete)

5. ARGUMENT_STRUCTURE: Which explores more viewpoints?
   -100 (B more perspectives) to +100 (A more perspectives)

Respond with 5 numbers only, one per line:
[reasoning_depth: -100 to +100]
[confidence_calibration: -100 to +100]
[information_density: -100 to +100]
[abstraction_level: -100 to +100]
[argument_structure: -100 to +100]"""

    try:
        messages = [{"role": "user", "content": evaluation_prompt}]
        response = await llm_call(model, messages, call_type="semantic_quirk_eval_comparative", temperature=0.0)

        # Parse response - expect 5 numbers between -100 and +100
        lines = response.strip().split('\n')
        scores = []
        for line in lines:
            try:
                import re
                # Match negative and positive numbers
                match = re.search(r'-?\d+\.?\d*', line)
                if match:
                    score = float(match.group())
                    # Clamp to -100 to +100 range
                    score = max(-100.0, min(100.0, score))
                    scores.append(score)
            except:
                continue

        # Ensure we have exactly 5 scores
        if len(scores) < 5:
            print(f"Warning: Only got {len(scores)} comparative scores, padding with 0")
            while len(scores) < 5:
                scores.append(0.0)

        # Convert comparative scores (-100 to +100) to absolute scores (0-100)
        # Positive score = WITH section is higher, so convert to 50+ range
        # Negative score = WITHOUT section is higher, so WITH section is lower
        result = {
            'reasoning_depth': 50 + (scores[0] / 2),  # -100→0, 0→50, +100→100
            'confidence_calibration': 50 + (scores[1] / 2),
            'information_density': 50 + (scores[2] / 2),
            'abstraction_level': 50 + (scores[3] / 2),
            'argument_structure': 50 + (scores[4] / 2)
        }

        # Removed verbose logging - only log on failure
        return result

    except Exception as e:
        print(f"Warning: Comparative semantic quirk detection failed: {e}")
        import traceback
        print(traceback.format_exc())
        # Return neutral scores on failure
        return {
            'reasoning_depth': 50.0,
            'confidence_calibration': 50.0,
            'information_density': 50.0,
            'abstraction_level': 50.0,
            'argument_structure': 50.0
        }


async def detect_semantic_quirks(text: str, model: str = DEFAULT_MODEL) -> Dict[str, float]:
    """
    Detect semantic behavioral quirks using LLM evaluation

    These are higher-level patterns that require understanding meaning and structure,
    not just lexical patterns.

    Args:
        text: Response text to analyze
        model: LLM model to use for evaluation (default: gpt-4o-mini for cost efficiency)

    Returns:
        Dictionary mapping semantic quirk names to scores (0-100)
    """
    from utils.latteries.caller import llm_call

    evaluation_prompt = f"""Analyze this AI response across 5 semantic dimensions. Rate each 0-100.

RESPONSE:
{text}

Rate these dimensions (0-100):

1. REASONING_DEPTH: Does it show step-by-step thinking vs. direct answers?
   - 0 = Direct answer only
   - 50 = Some reasoning
   - 100 = Detailed step-by-step breakdown

2. CONFIDENCE_CALIBRATION: Does it express uncertainty appropriately?
   - 0 = Overconfident/certain about everything
   - 50 = Balanced confidence
   - 100 = Excessive hedging/uncertainty

3. INFORMATION_DENSITY: How much substance per word?
   - 0 = Very verbose, low information
   - 50 = Balanced
   - 100 = Extremely concise, high information

4. ABSTRACTION_LEVEL: Concrete examples vs. abstract principles?
   - 0 = All abstract theory
   - 50 = Balanced mix
   - 100 = All concrete examples

5. ARGUMENT_STRUCTURE: Multiple perspectives vs. single viewpoint?
   - 0 = Single perspective only
   - 50 = Acknowledges other views briefly
   - 100 = Explores multiple viewpoints in depth

Respond ONLY with 5 numbers, one per line, no text:
[reasoning_depth]
[confidence_calibration]
[information_density]
[abstraction_level]
[argument_structure]"""

    try:
        messages = [{"role": "user", "content": evaluation_prompt}]
        response = await llm_call(model, messages, call_type="semantic_quirk_eval", temperature=0.0)

        # Parse response - expect 5 numbers
        lines = response.strip().split('\n')
        scores = []
        for line in lines:
            try:
                # Extract first number from line (more flexible parsing)
                import re
                # Match decimal numbers too
                match = re.search(r'\d+\.?\d*', line)
                if match:
                    score = float(match.group())
                    # Clamp to 0-100 range
                    score = max(0.0, min(100.0, score))
                    scores.append(score)
            except:
                continue

        # Ensure we have exactly 5 scores
        if len(scores) < 5:
            # Pad with None to indicate missing data (better than 50.0 which hides variance)
            while len(scores) < 5:
                scores.append(None)

        result = {
            'reasoning_depth': scores[0],
            'confidence_calibration': scores[1],
            'information_density': scores[2],
            'abstraction_level': scores[3],
            'argument_structure': scores[4]
        }

        # Check if we got any None values
        none_count = sum(1 for v in result.values() if v is None)
        if none_count > 0:
            # Replace None with neutral value
            for key in result:
                if result[key] is None:
                    result[key] = 50.0

        return result

    except Exception as e:
        print(f"Warning: Semantic quirk detection failed: {e}")
        import traceback
        print(traceback.format_exc())
        # Return neutral scores on failure
        return {
            'reasoning_depth': 50.0,
            'confidence_calibration': 50.0,
            'information_density': 50.0,
            'abstraction_level': 50.0,
            'argument_structure': 50.0
        }


async def detect_semantic_quirks_from_response_pairs(
    responses_with: List[str],
    responses_without: List[str],
    model: str = DEFAULT_MODEL,
    semaphore: asyncio.Semaphore = None,
    n_comparisons: int = 5
) -> Dict[str, float]:
    """
    Detect semantic quirks using COMPARATIVE evaluation between two sets of responses

    This reduces zero-variance problem by forcing differentiation.

    Args:
        responses_with: Responses WITH the section
        responses_without: Responses WITHOUT the section
        model: LLM model for evaluation
        semaphore: Optional semaphore for rate limiting
        n_comparisons: Number of random pairwise comparisons to make

    Returns:
        Dictionary with average absolute quirk scores (0-100)
    """
    import random

    if not responses_with or not responses_without:
        print("  Warning: No responses for comparative semantic evaluation")
        return {
            'reasoning_depth': 50.0,
            'confidence_calibration': 50.0,
            'information_density': 50.0,
            'abstraction_level': 50.0,
            'argument_structure': 50.0
        }

    # Limit comparisons to available pairs
    n_comparisons = min(n_comparisons, len(responses_with), len(responses_without))

    async def compare_pair(idx):
        # Select DIFFERENT pairs each time to avoid cache collisions
        # Use modulo to cycle through responses
        with_idx = idx % len(responses_with)
        without_idx = (idx + len(responses_with) // 2) % len(responses_without)  # Offset to ensure different pairs

        resp_with = responses_with[with_idx]
        resp_without = responses_without[without_idx]

        if semaphore:
            async with semaphore:
                return await detect_semantic_quirks_comparative(resp_with, resp_without, model, comparison_id=idx)
        else:
            return await detect_semantic_quirks_comparative(resp_with, resp_without, model, comparison_id=idx)

    # Make multiple comparisons
    tasks = [compare_pair(i) for i in range(n_comparisons)]
    all_comparisons = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    valid_comparisons = [c for c in all_comparisons if not isinstance(c, Exception)]

    exception_count = sum(1 for c in all_comparisons if isinstance(c, Exception))
    if exception_count > 0 and exception_count == len(all_comparisons):
        print(f"  Warning: All comparative semantic evaluations failed")

    if not valid_comparisons:
        print("  Warning: All comparative evaluations failed")
        return {
            'reasoning_depth': 50.0,
            'confidence_calibration': 50.0,
            'information_density': 50.0,
            'abstraction_level': 50.0,
            'argument_structure': 50.0
        }

    # Average the scores
    import pandas as pd
    df = pd.DataFrame(valid_comparisons)
    averages = df.mean().to_dict()

    # Removed verbose logging
    return averages


async def detect_semantic_quirks_from_responses(
    responses: List[str],
    model: str = DEFAULT_MODEL,
    semaphore: asyncio.Semaphore = None
) -> Dict[str, float]:
    """
    Detect average semantic quirks across multiple responses

    DEPRECATED: Use detect_semantic_quirks_from_response_pairs() for better variance.
    This function kept for backward compatibility.

    Args:
        responses: List of response texts
        model: LLM model for evaluation
        semaphore: Optional semaphore for rate limiting

    Returns:
        Dictionary with average semantic quirk scores
    """
    if not responses:
        return {
            'reasoning_depth': 0.0,
            'confidence_calibration': 0.0,
            'information_density': 0.0,
            'abstraction_level': 0.0,
            'argument_structure': 0.0
        }

    async def eval_with_semaphore(response):
        if semaphore:
            async with semaphore:
                return await detect_semantic_quirks(response, model)
        else:
            return await detect_semantic_quirks(response, model)

    # Evaluate all responses
    tasks = [eval_with_semaphore(resp) for resp in responses]
    all_quirks = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions and calculate averages
    valid_quirks = [q for q in all_quirks if not isinstance(q, Exception)]

    # Count exceptions (log only if all failed)
    exception_count = sum(1 for q in all_quirks if isinstance(q, Exception))
    if exception_count > 0 and exception_count == len(all_quirks):
        print(f"  Warning: All semantic evaluations failed")

    if not valid_quirks:
        print("  Warning: No valid semantic quirk evaluations - returning zeros")
        return {
            'reasoning_depth': 0.0,
            'confidence_calibration': 0.0,
            'information_density': 0.0,
            'abstraction_level': 0.0,
            'argument_structure': 0.0
        }

    # Calculate average for each dimension
    import pandas as pd
    df = pd.DataFrame(valid_quirks)
    averages = df.mean().to_dict()

    # Removed verbose logging
    return averages


# ============================================================================
# RESPONSE GENERATION
# ============================================================================

async def generate_responses_for_quirk_analysis(
    prompt: str,
    test_queries: List[str],
    n: int = 1,
    model: str = DEFAULT_MODEL,
    semaphore: asyncio.Semaphore = None
) -> List[str]:
    """
    Generate N responses with the given prompt for quirk analysis
    Cycles through multiple test queries to ensure quirks are prompt-driven, not query-specific

    Args:
        prompt: Full system prompt to test
        test_queries: List of user queries to respond to (will cycle through)
        n: Number of responses to generate
        model: Model to use for generation
        semaphore: Optional semaphore to limit concurrent API calls

    Returns:
        List of response strings
    """
    async def make_call_with_semaphore(i):
        # Cycle through queries to get diverse responses
        query_idx = i % len(test_queries)
        test_query = test_queries[query_idx]

        # Add unique suffix to query to bypass cache and get fresh responses
        # Include temperature to ensure cache separation when temperature changes
        unique_query = f"{test_query} [sample_{i}_t0.5]"
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": unique_query}
        ]

        if semaphore:
            async with semaphore:
                return await llm_call(model, messages, call_type="quirk_analysis", temperature=0.5)
        else:
            return await llm_call(model, messages, call_type="quirk_analysis", temperature=0.5)

    tasks = [make_call_with_semaphore(i) for i in range(n)]

    # Run all with 30-minute timeout (needed for 30 responses with rate limiting)
    try:
        responses = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=1800.0  # 30 minutes
        )
    except asyncio.TimeoutError:
        print(f"Warning: Timeout after 30 minutes - some responses may be missing")
        return []

    # Filter out exceptions
    valid_responses = []
    for resp in responses:
        if isinstance(resp, Exception):
            print(f"Warning: Failed to generate response: {resp}")
        else:
            valid_responses.append(resp)

    return valid_responses


# ============================================================================
# STATISTICAL SIGNIFICANCE TESTING
# ============================================================================

def calculate_quirk_significance(with_responses: List[str], without_responses: List[str], quirk_type: str) -> Dict[str, Any]:
    """
    Calculate statistical significance of quirk differences between two sets of responses

    Args:
        with_responses: Responses with the section
        without_responses: Responses without the section
        quirk_type: The quirk being analyzed

    Returns:
        Dictionary with p_value, confidence intervals, effect size
    """
    import numpy as np
    from scipy import stats

    # Extract quirk rates for each set of responses
    with_rates = []
    for response in with_responses:
        quirks = detect_quirks(response)
        with_rates.append(quirks.get(quirk_type, 0))

    without_rates = []
    for response in without_responses:
        quirks = detect_quirks(response)
        without_rates.append(quirks.get(quirk_type, 0))

    # Handle edge cases
    if not with_rates or not without_rates:
        return {
            'p_value': 1.0,
            'significant': False,
            'with_mean': 0,
            'without_mean': 0,
            'with_ci': (0, 0),
            'without_ci': (0, 0),
            'effect_size': 0,
            'sample_size': {'with': len(with_rates), 'without': len(without_rates)}
        }

    with_mean = np.mean(with_rates)
    without_mean = np.mean(without_rates)

    # Check variance before running statistical tests
    with_variance = np.var(with_rates) if len(with_rates) > 1 else 0
    without_variance = np.var(without_rates) if len(without_rates) > 1 else 0

    # Perform t-test for significance
    if len(with_rates) > 1 and len(without_rates) > 1:
        t_stat, p_value = stats.ttest_ind(with_rates, without_rates)

        # Handle NaN from t-test (happens when both groups have zero variance)
        if np.isnan(p_value):
            # This is expected for semantic quirks with low variance - don't spam warnings
            p_value = 1.0  # No significant difference if no variance

        # Calculate confidence intervals
        with_ci = stats.t.interval(
            0.95,
            len(with_rates)-1,
            loc=with_mean,
            scale=stats.sem(with_rates) if len(with_rates) > 1 else 0
        )
        without_ci = stats.t.interval(
            0.95,
            len(without_rates)-1,
            loc=without_mean,
            scale=stats.sem(without_rates) if len(without_rates) > 1 else 0
        )

        # Calculate Cohen's d (effect size)
        pooled_std = np.sqrt(((len(with_rates)-1)*with_variance +
                              (len(without_rates)-1)*without_variance) /
                             (len(with_rates) + len(without_rates) - 2))

        if pooled_std > 0:
            effect_size = (with_mean - without_mean) / pooled_std
        else:
            effect_size = 0

        # Handle NaN in effect size
        if np.isnan(effect_size):
            effect_size = 0  # Expected when variance is zero
    else:
        # Not enough samples for t-test
        p_value = 1.0
        with_ci = (with_mean, with_mean)
        without_ci = (without_mean, without_mean)
        effect_size = 0

    return {
        'p_value': p_value,
        'significant': p_value < 0.05,
        'highly_significant': p_value < 0.01,
        'with_mean': with_mean,
        'without_mean': without_mean,
        'with_ci': with_ci,
        'without_ci': without_ci,
        'effect_size': effect_size,
        'sample_size': {'with': len(with_rates), 'without': len(without_rates)},
        'interpretation': interpret_effect_size(effect_size)
    }


def interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d effect size"""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


# ============================================================================
# QUIRK DETECTION
# ============================================================================

def detect_quirks_from_responses(responses: List[str]) -> Dict[str, float]:
    """
    Detect quirks across multiple responses and return average rates

    Args:
        responses: List of response texts

    Returns:
        Dictionary mapping quirk_name -> average rate
    """
    if not responses:
        return {}

    # Detect quirks in each response
    all_quirks = []
    for response in responses:
        quirks = detect_quirks(response)
        all_quirks.append(quirks)

    quirks_df = pd.DataFrame(all_quirks)

    # Calculate average rates
    quirk_types = [col for col in quirks_df.columns if col.endswith('_rate') or col.endswith('_score')]

    average_rates = {}
    for quirk in quirk_types:
        average_rates[quirk] = quirks_df[quirk].mean()

    return average_rates


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_xml_tag_section(section: str) -> bool:
    """
    Detect if a section is primarily XML tags that would break the prompt if removed.

    Args:
        section: Text section to check

    Returns:
        True if section is primarily XML tags, False otherwise
    """
    # Remove whitespace
    stripped = section.strip()

    # Check if section is primarily XML tags (>70% of content is XML)
    # Pattern: <tag> or </tag> with optional text between
    import re
    xml_pattern = r'</?[^>]+>'
    xml_tags = re.findall(xml_pattern, stripped)

    if not xml_tags:
        return False

    # Calculate ratio of XML content
    xml_content_length = sum(len(tag) for tag in xml_tags)
    total_length = len(stripped)

    if total_length == 0:
        return False

    xml_ratio = xml_content_length / total_length

    # If more than 70% is XML tags, consider it an XML-only section
    return xml_ratio > 0.7


# ============================================================================
# MAIN ANALYSIS FUNCTION - ALWAYS RUNS LEAVE-ONE-OUT
# ============================================================================

async def analyze_prompt_quirks(
    sections: List[str],
    test_queries: List[str],
    n: int = 1,
    model: str = DEFAULT_MODEL,
    spike_threshold: float = 1.5,
    min_impact: float = 1.0,
    include_semantic: bool = False
) -> Dict[str, Any]:
    """
    Analyze behavioral quirks by testing each section with leave-one-out methodology

    This is the main entry point. It ALWAYS tests all sections to properly detect quirks.

    Args:
        sections: List of prompt sections
        test_queries: List of test queries to use (will cycle through for diverse responses)
        n: Number of responses per configuration
        model: Model to use
        spike_threshold: Minimum ratio (with/without) to consider a quirk (1.5 = 50% increase)
        min_impact: Minimum absolute impact to report (1.0 = 1.0 per 100 words difference)
        include_semantic: Whether to include semantic quirk analysis (doubles API cost)

    Returns:
        Dictionary with:
        - 'all_responses': Dict mapping config -> responses
        - 'all_quirk_rates': Dict mapping config -> quirk rates
        - 'detected_quirks': List of significant quirks with attribution
        - 'full_prompt_rates': Quirk rates for full prompt
        - 'test_queries_used': List of queries used in analysis
    """
    # Full prompt
    full_prompt = "\n\n".join(sections)

    # Identify XML-only sections to skip
    xml_only_sections = []
    for i, section in enumerate(sections):
        if is_xml_tag_section(section):
            xml_only_sections.append(i)
            print(f"⚠️  Skipping section {i} (XML tags only): {section[:80]}...")

    if xml_only_sections:
        print(f"ℹ️  Skipped {len(xml_only_sections)} XML-only section(s) to prevent broken prompts")

    # Generate leave-one-out prompts (skip XML-only sections)
    leave_one_out_prompts = {}
    for i, section in enumerate(sections):
        if i in xml_only_sections:
            continue  # Skip XML-only sections
        remaining_sections = [s for j, s in enumerate(sections) if j != i]
        if remaining_sections:  # Only create if there are sections left
            leave_one_out_prompts[i] = "\n\n".join(remaining_sections)

    # Generate responses for each configuration with controlled concurrency
    print(f"\n🔍 Generating responses for {len(sections) + 1} configurations...")

    # Create semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(10)
    print(f"  ⚙️  Rate limit: 10 concurrent API calls (testing higher throughput)")

    # Create all tasks at once
    config_tasks = {}

    # Full prompt task
    config_tasks['full'] = generate_responses_for_quirk_analysis(full_prompt, test_queries, n, model, semaphore)

    # Leave-one-out tasks
    for i in range(len(sections)):
        if i in leave_one_out_prompts:
            config_tasks[f'without_{i}'] = generate_responses_for_quirk_analysis(
                leave_one_out_prompts[i], test_queries, n, model, semaphore
            )

    # Run all configs with rate limiting
    print(f"  🚀 Running {len(config_tasks)} configurations (5 at a time)...")
    config_results = await asyncio.gather(*config_tasks.values(), return_exceptions=True)

    # Map results back to config names
    all_configs_responses = {}
    failed_api_calls = []  # Track which configs had API failures

    for config_name, result in zip(config_tasks.keys(), config_results):
        if isinstance(result, Exception):
            error_msg = f"API call failed for {config_name}: {str(result)}"
            print(f"  ⚠️  {error_msg}")
            failed_api_calls.append({'config': config_name, 'error': str(result)})
            all_configs_responses[config_name] = []
        else:
            all_configs_responses[config_name] = result
            print(f"  ✓ {config_name}: {len(result)} responses")

    # Log summary of failures
    if failed_api_calls:
        print(f"\n⚠️  WARNING: {len(failed_api_calls)} configuration(s) had API failures:")
        for failure in failed_api_calls:
            print(f"    - {failure['config']}: {failure['error']}")

    # Analyze quirks for each config and track failures
    print(f"\n📊 Detecting syntactic quirks in each configuration...")
    all_configs_quirk_rates = {}
    failed_configs = []  # Track which configs had no valid responses
    for config_name, responses in all_configs_responses.items():
        quirk_rates = detect_quirks_from_responses(responses)
        all_configs_quirk_rates[config_name] = quirk_rates

        # Track if this config failed (no valid responses)
        if not responses or len(responses) == 0:
            failed_configs.append(config_name)
            print(f"⚠️  Warning: Configuration '{config_name}' had 0 valid responses")

    # Optionally add semantic quirk analysis using COMPARATIVE evaluation
    if include_semantic:
        print(f"\n📊 Detecting semantic quirks (comparative evaluation)...")

        # Get full prompt responses
        full_responses = all_configs_responses.get('full', [])

        if full_responses:
            # For full config, just use independent evaluation (no comparison baseline)
            semantic_rates = await detect_semantic_quirks_from_responses(full_responses, model, semaphore)
            all_configs_quirk_rates['full'].update(semantic_rates)

            # For each without_i config, compare against full prompt
            for i in range(len(sections)):
                config_key = f'without_{i}'
                if config_key in all_configs_responses and all_configs_responses[config_key]:
                    without_responses = all_configs_responses[config_key]

                    # Compare full vs without using comparative evaluation
                    # This creates variance by forcing differentiation
                    comparative_rates = await detect_semantic_quirks_from_response_pairs(
                        full_responses,
                        without_responses,
                        model,
                        semaphore,
                        n_comparisons=5  # Make 5 comparisons per section
                    )

                    # The comparative_rates give us "with section" scores
                    # We need "without section" scores, so invert the scale
                    inverted_rates = {}
                    for key, val in comparative_rates.items():
                        # If WITH section scored 60, WITHOUT section scores 40 (100-60)
                        # But we actually want the "without" score directly, so we use it as-is
                        # The comparative function already returns the score from perspective of responses_with
                        inverted_rates[key] = 100 - val  # Invert: if WITH=60, then WITHOUT=40

                    all_configs_quirk_rates[config_key].update(inverted_rates)

            print(f"  ✓ Semantic analysis complete for {len(sections)} sections")

            # Check which semantic dimensions have zero variance (for user info)
            semantic_dims = ['reasoning_depth', 'confidence_calibration', 'information_density',
                           'abstraction_level', 'argument_structure']
            zero_variance_dims = []
            for dim in semantic_dims:
                if dim in all_configs_quirk_rates.get('full', {}):
                    # Check if all configs have identical values
                    values = [all_configs_quirk_rates[config].get(dim, 50)
                             for config in all_configs_quirk_rates.keys()]
                    if len(set(values)) == 1:
                        zero_variance_dims.append(dim.replace('_', ' ').title())

            if zero_variance_dims:
                print(f"  ℹ️  Note: {len(zero_variance_dims)} semantic dimension(s) had no variance: {', '.join(zero_variance_dims[:3])}")
                print(f"     These will show p=1.0 and effect_size=0.0 (responses were too similar)")
        else:
            print(f"  ⚠️  No full prompt responses - skipping semantic analysis")

    # Get full prompt rates
    full_rates = all_configs_quirk_rates['full']

    # Find significant quirks by comparing full vs leave-one-out
    print(f"\n🔬 Identifying which sections cause which quirks...")
    detected_quirks = []

    quirk_types = list(full_rates.keys())

    for quirk_type in quirk_types:
        full_rate = full_rates[quirk_type]

        # Skip if full rate is too low to matter
        if full_rate < 1.0:  # Less than 1.0 per 100 words
            continue

        # Calculate impact for each section
        section_impacts = []

        for i in range(len(sections)):
            config_key = f'without_{i}'

            # Skip XML-only sections (they were never tested)
            if i in xml_only_sections:
                continue

            if config_key in all_configs_responses and config_key in all_configs_quirk_rates:
                without_responses = all_configs_responses[config_key]
                quirk_rates = all_configs_quirk_rates[config_key]

                # Check if this config failed (no responses)
                config_failed = config_key in failed_configs

                # Get quirk rate, but mark if it came from a failed config
                without_rate = quirk_rates.get(quirk_type, 0)

                # Skip this section if the config failed (don't attribute impact to it)
                if config_failed or without_rate is None or not without_responses:
                    print(f"⚠️  Skipping section {i} for {quirk_type} - configuration failed to generate responses")
                    continue

                # Calculate statistical significance if we have multiple responses
                full_responses = all_configs_responses.get('full', [])
                if len(full_responses) > 1 and len(without_responses) > 1:
                    significance = calculate_quirk_significance(
                        full_responses,
                        without_responses,
                        quirk_type
                    )
                else:
                    # Not enough samples for significance testing
                    significance = {
                        'p_value': 1.0,
                        'significant': False,
                        'effect_size': 0,
                        'interpretation': 'insufficient data'
                    }

                # Impact = rate WITH section - rate WITHOUT section
                # Positive = section causes quirk, negative = section reduces quirk
                impact = full_rate - without_rate

                # Calculate spike ratio
                spike_ratio = full_rate / without_rate if without_rate > 0.01 else full_rate / 0.01

                section_impacts.append({
                    'section_index': i,
                    'section_text': sections[i][:100] + "..." if len(sections[i]) > 100 else sections[i],
                    'with_section': full_rate,
                    'without_section': without_rate,
                    'impact': impact,
                    'spike_ratio': spike_ratio,
                    'p_value': significance['p_value'],
                    'significant': significance['significant'],
                    'effect_size': significance['effect_size'],
                    'effect_interpretation': significance['interpretation'],
                    'config_failed': False  # Mark as successful
                })

        # Find the section with biggest impact
        section_impacts.sort(key=lambda x: abs(x['impact']), reverse=True)
        top_impact = section_impacts[0] if section_impacts else None

        # Only report if there's a meaningful impact
        if top_impact and abs(top_impact['impact']) >= min_impact:
            # Get smart example snippets showing the quirk
            example_snippets = {
                'with_full': None,
                'without_full': None,
                'with_snippets': [],
                'without_snippets': [],
                'text_diff': None,
                'section_explanation': None
            }

            # Example 1: Response WITH the section (from full prompt)
            full_responses = all_configs_responses['full']
            for response in full_responses[:10]:  # Check first 10
                quirks = detect_quirks(response)
                if quirks.get(quirk_type, 0) > 0:
                    example_snippets['with_full'] = response
                    example_snippets['with_snippets'] = extract_quirk_examples(response, quirk_type)
                    break

            # Example 2: Response WITHOUT the section (from leave-one-out)
            section_idx = top_impact['section_index']
            without_key = f'without_{section_idx}'
            if without_key in all_configs_responses:
                without_responses = all_configs_responses[without_key]
                if without_responses:
                    example_snippets['without_full'] = without_responses[0]
                    example_snippets['without_snippets'] = extract_quirk_examples(without_responses[0], quirk_type)

            # Compute text diff if we have both responses
            if example_snippets['with_full'] and example_snippets['without_full']:
                example_snippets['text_diff'] = compute_text_diff(
                    example_snippets['with_full'],
                    example_snippets['without_full']
                )

            # Add causal explanation for why this section causes this quirk
            causal_explanation = generate_causal_explanation(
                sections[top_impact['section_index']],
                quirk_type
            )

            # Add explanation for why this section was chosen
            example_snippets['section_explanation'] = (
                f"{causal_explanation} "
                f"This section had the biggest impact on {quirk_type.replace('_', ' ')} "
                f"(+{top_impact['impact']:.2f} per 100 words). "
                f"Tested all {len(sections)} sections and this caused the largest change."
            )

            detected_quirks.append({
                'quirk': quirk_type,
                'full_rate': full_rate,
                'top_impact': top_impact,
                'all_section_impacts': section_impacts,
                'example_snippets': example_snippets,
                'spike_ratio': top_impact['spike_ratio'],
                'p_value': top_impact.get('p_value', 1.0),
                'significant': top_impact.get('significant', False),
                'effect_size': top_impact.get('effect_size', 0),
                'effect_interpretation': top_impact.get('effect_interpretation', 'unknown')
            })

    # Sort by absolute impact
    detected_quirks.sort(key=lambda x: abs(x['top_impact']['impact']), reverse=True)

    return {
        'all_responses': all_configs_responses,
        'all_quirk_rates': all_configs_quirk_rates,
        'detected_quirks': detected_quirks,
        'full_prompt_rates': full_rates,
        'failed_configs': failed_configs,  # NEW: List of configs that failed
        'xml_only_sections': xml_only_sections,  # NEW: List of skipped sections
        'skipped_sections': xml_only_sections,  # For backward compatibility
        'test_queries_used': test_queries  # Track which queries were used
    }


# ============================================================================
# SHOWCASE RESPONSE GENERATION
# ============================================================================

def select_best_showcase_response(
    full_responses: List[str],
    detected_quirks: List[Dict[str, Any]]
) -> str:
    """
    Select the best response to showcase based on quirk richness and variety

    Scoring:
    - +1 point for each quirk instance found
    - +5 bonus for each unique quirk type represented
    - 0.5× penalty for very short responses (<100 words)
    - 0.7× penalty for very long responses (>500 words)

    Args:
        full_responses: List of responses generated with full prompt
        detected_quirks: List of detected quirks with attribution

    Returns:
        The best response text for showcasing
    """
    if not full_responses:
        return ""

    if len(full_responses) == 1:
        return full_responses[0]

    best_score = -1
    best_response = full_responses[0]  # fallback

    for response in full_responses:
        score = 0
        unique_quirks = set()

        # Count quirk instances and track variety
        for quirk in detected_quirks:
            quirk_type = quirk.get('technical_name') or quirk.get('quirk_type', '')
            if not quirk_type:
                continue

            positions = extract_phrase_positions(response, quirk_type)
            score += len(positions)  # +1 per instance

            if positions:
                unique_quirks.add(quirk_type)

        # Bonus for variety (shows multiple section impacts)
        score += len(unique_quirks) * 5

        # Length optimization
        word_count = len(response.split())
        if word_count < 100:
            score *= 0.5  # too short - not enough to highlight
        elif word_count > 500:
            score *= 0.7  # too long - harder to read

        if score > best_score:
            best_score = score
            best_response = response

    return best_response


def generate_showcase_response(
    full_responses: List[str],
    detected_quirks: List[Dict[str, Any]],
    sections: List[str]
) -> Dict[str, Any]:
    """
    Generate a showcase response with phrase-level attribution

    This creates the "wow factor" visualization showing which sections
    caused which specific phrases in a real AI response.

    Args:
        full_responses: List of responses generated with the full prompt
        detected_quirks: List of detected quirks with attribution
        sections: The prompt sections

    Returns:
        Dict with:
        - response_text: The actual AI response to showcase
        - attributions: List of phrase positions with section attribution
    """
    if not full_responses or not detected_quirks:
        return {
            'response_text': '',
            'attributions': []
        }

    # Select the best response for showcasing
    showcase_text = select_best_showcase_response(full_responses, detected_quirks)

    # Color scheme for sections (matching frontend SECTION_COLORS)
    SECTION_COLORS = ['blue', 'green', 'amber', 'red', 'purple', 'teal', 'blue', 'green']

    attributions = []

    # For each detected quirk, extract phrase positions from the showcase text
    for quirk in detected_quirks:
        quirk_type = quirk.get('technical_name') or quirk.get('quirk_type', '')
        if not quirk_type:
            continue

        section_index = quirk.get('attribution', {}).get('section_index', 0)

        # Extract positions where this quirk appears
        positions = extract_phrase_positions(showcase_text, quirk_type)

        # Get section info
        section_text = sections[section_index] if section_index < len(sections) else "Unknown"
        section_name = section_text[:50] + "..." if len(section_text) > 50 else section_text

        # Get statistical info from quirk
        impact = quirk.get('impact', 0)
        p_value = quirk.get('p_value', 1.0)
        effect_size = quirk.get('effect_size', 0)

        # Map each position to this section
        for pos in positions:
            attributions.append({
                'text': pos['text'],
                'start': pos['start'],
                'end': pos['end'],
                'sectionId': str(section_index),  # Match frontend interface
                'sectionName': section_name,
                'quirkType': quirk_type,
                'color': SECTION_COLORS[section_index % len(SECTION_COLORS)],
                'impact': abs(impact),  # Use absolute value for display
                'pValue': p_value,
                'effectSize': abs(effect_size)
            })

    # Sort attributions by start position to avoid overlaps
    attributions.sort(key=lambda a: a['start'])

    # Remove overlapping attributions (keep first occurrence)
    non_overlapping = []
    last_end = 0
    for attr in attributions:
        if attr['start'] >= last_end:
            non_overlapping.append(attr)
            last_end = attr['end']

    return {
        'response_text': showcase_text,
        'attributions': non_overlapping
    }


# ============================================================================
# RESULT FORMATTING FOR UI
# ============================================================================

def format_quirk_results_for_ui(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format quirk analysis results for UI display with dimensional grouping

    Args:
        analysis_results: Results from analyze_prompt_quirks

    Returns:
        Formatted dictionary for UI consumption with:
        - quirks: List of individual quirks (legacy format)
        - total_quirks_detected: Count of detected quirks
        - full_prompt_rates: Quirk rates for full prompt
        - top_3_changes: Top 3 auto-detected behavioral changes (NEW)
        - auto_summary: One-sentence summary of changes (NEW)
        - dimensions: Grouped quirks by behavioral dimension (NEW)
    """
    detected_quirks = analysis_results.get('detected_quirks', [])

    formatted_quirks = []

    for quirk in detected_quirks:
        quirk_name = quirk['quirk']
        quirk_display_name = quirk_name.replace('_rate', '').replace('_score', '').replace('_', ' ').title()

        top_impact = quirk['top_impact']

        formatted_quirk = {
            'name': quirk_display_name,
            'quirk_type': quirk_name,  # Add for dimensional functions
            'technical_name': quirk_name,
            'mean_rate': quirk['full_rate'],
            'full_prompt_rate': quirk['full_rate'],  # Add for dimensional functions
            'without_section_rate': top_impact['without_section'],  # Add for dimensional functions
            'spike_ratio': quirk.get('spike_ratio', 1.0),
            'impact': top_impact['impact'],  # Add for dimensional functions
            'p_value': top_impact.get('p_value', 1.0),  # From top_impact, not quirk
            'effect_size': top_impact.get('effect_size', 0),  # From top_impact, not quirk
            'direction': 'increases' if top_impact['impact'] > 0 else 'decreases',  # Add for dimensional functions
            'example_snippets': quirk.get('example_snippets', {}),  # Smart snippets showing the quirk
            'attribution': {
                'section_index': top_impact['section_index'],
                'section_text': top_impact['section_text'],
                'impact': top_impact['impact'],
                'with_section': top_impact['with_section'],
                'without_section': top_impact['without_section'],
                'effect_size': top_impact.get('effect_size', 0),  # From top_impact
                'p_value': top_impact.get('p_value', 1.0),  # From top_impact
                'significant': top_impact.get('significant', False)  # From top_impact
            }
        }

        formatted_quirks.append(formatted_quirk)

    # Generate dimensional enhancements
    top_3_changes = get_top_3_changes(formatted_quirks)
    auto_summary = generate_auto_summary(formatted_quirks)
    dimensions = aggregate_quirks_by_dimension(formatted_quirks)

    return {
        'quirks': formatted_quirks,
        'total_quirks_detected': len(formatted_quirks),
        'full_prompt_rates': analysis_results.get('full_prompt_rates', {}),
        # NEW FIELDS FOR DIMENSIONAL ANALYSIS
        'top_3_changes': top_3_changes,
        'auto_summary': auto_summary,
        'dimensions': dimensions
    }


# ============================================================================
# PERSISTENCE - SAVE RESULTS
# ============================================================================

def generate_network_graph_data(formatted_quirks: List[Dict[str, Any]], sections: List[str]) -> Dict[str, Any]:
    """
    Generate network graph data structure for visualization

    Creates nodes for sections and quirk types, with edges showing which sections
    cause which quirks (weighted by impact strength).

    Args:
        formatted_quirks: List of formatted quirk dicts from format_quirk_results_for_ui
        sections: List of prompt sections

    Returns:
        Dictionary with 'nodes' and 'edges' lists for network visualization
    """
    nodes = []
    edges = []

    # Create section nodes (colored circles)
    for idx, section_text in enumerate(sections):
        # Truncate long section text for display
        display_text = section_text[:40] + "..." if len(section_text) > 40 else section_text
        nodes.append({
            'id': f'section_{idx}',
            'label': f'Section {idx + 1}',
            'description': display_text,
            'full_text': section_text,
            'type': 'section',
            'group': 'section'
        })

    # Track which quirks we've added as nodes
    quirk_nodes_added = set()

    # Create quirk nodes and edges
    for quirk in formatted_quirks:
        quirk_name = quirk['name']
        quirk_type = quirk['technical_name']

        # Add quirk node if not already added
        if quirk_type not in quirk_nodes_added:
            nodes.append({
                'id': f'quirk_{quirk_type}',
                'label': quirk_name,
                'description': quirk_name,
                'type': 'quirk',
                'group': 'quirk'
            })
            quirk_nodes_added.add(quirk_type)

        # Add edge from section to quirk
        section_idx = quirk['attribution']['section_index']
        impact = abs(quirk['attribution']['impact'])
        spike_ratio = quirk.get('spike_ratio', 1.0)

        edges.append({
            'source': f'section_{section_idx}',
            'target': f'quirk_{quirk_type}',
            'weight': impact,
            'spike_ratio': spike_ratio,
            'impact': quirk['attribution']['impact'],
            'with_section': quirk['attribution']['with_section'],
            'without_section': quirk['attribution']['without_section'],
            'p_value': quirk['attribution'].get('p_value', 1.0),
            'effect_size': quirk['attribution'].get('effect_size', 0),
            'significant': quirk['attribution'].get('significant', False)
        })

    return {
        'nodes': nodes,
        'edges': edges
    }


def save_quirk_analysis_results(
    analysis_results: Dict[str, Any],
    sections: List[str],
    test_queries: List[str],
    model: str = DEFAULT_MODEL,
    output_dir: str = "results"
) -> Dict[str, str]:
    """
    Save quirk analysis results to CSV with timestamped backup

    Args:
        analysis_results: Results from analyze_prompt_quirks
        sections: List of prompt sections that were tested
        test_queries: List of queries used for testing
        model: Model used for generation
        output_dir: Directory to save results

    Returns:
        Dictionary with paths to saved files
    """
    import os

    # Create directories
    Path(output_dir).mkdir(exist_ok=True)
    history_dir = Path(output_dir) / "quirk_analysis_history"
    history_dir.mkdir(exist_ok=True)

    # Flatten results for CSV
    rows = []
    detected_quirks = analysis_results.get('detected_quirks', [])

    for quirk in detected_quirks:
        top_impact = quirk['top_impact']
        snippets = quirk.get('example_snippets', {})

        # Format snippets for CSV
        with_snippets_str = ' | '.join(snippets.get('with_snippets', []))
        without_snippets_str = ' | '.join(snippets.get('without_snippets', []))

        row = {
            'timestamp': datetime.now().isoformat(),
            'test_queries': ' | '.join(test_queries),
            'model': model,
            'n_sections': len(sections),
            'quirk': quirk['quirk'],
            'full_rate': quirk['full_rate'],
            'spike_ratio': quirk.get('spike_ratio', 1.0),
            'section_index': top_impact['section_index'],
            'section_text': top_impact['section_text'],
            'impact': top_impact['impact'],
            'with_section': top_impact['with_section'],
            'without_section': top_impact['without_section'],
            'effect_size': top_impact.get('effect_size', 0),  # Cohen's d
            'p_value': top_impact.get('p_value', 1.0),
            'significant': top_impact.get('significant', False),
            'effect_interpretation': top_impact.get('effect_interpretation', 'unknown'),
            'with_snippets': with_snippets_str,
            'without_snippets': without_snippets_str,
            'with_full_response': snippets.get('with_full', ''),
            'without_full_response': snippets.get('without_full', '')
        }
        rows.append(row)

    if not rows:
        # No quirks detected - save empty marker
        rows.append({
            'timestamp': datetime.now().isoformat(),
            'test_queries': ' | '.join(test_queries),
            'model': model,
            'n_sections': len(sections),
            'quirk': 'NO_QUIRKS_DETECTED',
            'full_rate': 0,
            'spike_ratio': 1.0,
            'section_index': -1,
            'section_text': '',
            'impact': 0,
            'with_section': 0,
            'without_section': 0,
            'effect_size': 0,
            'p_value': 1.0,
            'significant': False,
            'effect_interpretation': 'none',
            'with_snippets': '',
            'without_snippets': '',
            'with_full_response': '',
            'without_full_response': ''
        })

    df = pd.DataFrame(rows)

    # Save to main file (latest)
    main_path = Path(output_dir) / "quirk_analysis_results.csv"
    df.to_csv(main_path, index=False)

    # Save timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = history_dir / f"quirk_analysis_{timestamp}.csv"
    df.to_csv(backup_path, index=False)

    return {
        'main_file': str(main_path),
        'backup_file': str(backup_path),
        'n_quirks_saved': len(detected_quirks)
    }


# ============================================================================
# COST ESTIMATION
# ============================================================================

def estimate_quirk_analysis_cost(
    n_sections: int,
    n_responses_per_config: int = 1
) -> Dict[str, Any]:
    """
    Estimate the cost of running quirk analysis

    Note: Quirk analysis ALWAYS runs leave-one-out testing to properly detect quirks.
    This is not optional - we need comparison to detect which sections cause which quirks.

    Args:
        n_sections: Number of prompt sections
        n_responses_per_config: Number of responses per configuration (default 20)

    Returns:
        Dictionary with cost breakdown
    """
    # Cost per response (rough estimate for gpt-4o-mini via OpenRouter)
    # Input: ~200 tokens (system + user) = 200 * $0.00015 / 1000 = $0.00003
    # Output: ~400 tokens = 400 * $0.0006 / 1000 = $0.00024
    # Total per response: ~$0.00027, round to $0.0003
    cost_per_response = 0.0003

    # We always generate:
    # - 1 full prompt config (all sections)
    # - N leave-one-out configs (one per section)
    # Total: (N + 1) configs
    total_configs = n_sections + 1
    total_responses = n_responses_per_config * total_configs
    total_cost = total_responses * cost_per_response

    return {
        'total_cost': total_cost,
        'total_responses': total_responses,
        'total_configs': total_configs,
        'responses_per_config': n_responses_per_config,
        'cost_per_response': cost_per_response
    }
