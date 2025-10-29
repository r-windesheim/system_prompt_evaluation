"""
Configuration constants for the AI System Prompt Testing Tool

This module centralizes all configuration values, magic numbers, and repeated
constants to provide a single source of truth.
"""
from typing import List, Dict

# ============================================================================
# Model Configuration
# ============================================================================

DEFAULT_MODEL = "openai/gpt-5-nano-2025-08-07"  # For generating responses
EVALUATION_MODEL = "openai/gpt-4o-mini"  # For evaluating responses (more accurate)
FALLBACK_MODEL = "anthropic/claude-3-haiku"

# ============================================================================
# API Pricing (per 1K tokens)
# ============================================================================

PRICING_INPUT_PER_1K = 0.000150  # Input tokens
PRICING_OUTPUT_PER_1K = 0.000600  # Output tokens
PRICING_AVG_INPUT_FACTOR = 0.2  # Average input token usage factor
PRICING_AVG_OUTPUT_FACTOR = 0.1  # Average output token usage factor

# ============================================================================
# Batch Processing Configuration
# ============================================================================

DEFAULT_MAX_CONCURRENT = 100  # Maximum throughput - nest_asyncio fixes allow this
HIGH_THROUGHPUT_THRESHOLD = 500
EXPERIMENTAL_THRESHOLD = 1000

# ============================================================================
# File Paths
# ============================================================================

CACHED_RESULTS_DIR = "cached_results"
EVALUATION_HISTORY_DIR = "evaluation_history"
LOGS_DIR = "logs"

BATCH_EVALUATION_FILE = f"{CACHED_RESULTS_DIR}/batch_evaluation.csv"
FULL_EVALUATION_BACKUP_FILE = f"{CACHED_RESULTS_DIR}/full_evaluation_backup.csv"
APP_LOG_FILE = f"{LOGS_DIR}/app.log"
EVALUATION_LOG_FILE = f"{LOGS_DIR}/evaluation.log"
API_CALLS_LOG_FILE = f"{LOGS_DIR}/api_calls.log"

# ============================================================================
# Evaluation Scoring
# ============================================================================

# Y/N Evaluation Scores
SCORE_YES = 100
SCORE_NO = 0
SCORE_AMBIGUOUS = 50
SCORE_DEFAULT = 50  # Fallback when parsing fails

# Score Thresholds for Ratings
SCORE_EXCELLENT_THRESHOLD = 90
SCORE_GOOD_THRESHOLD = 80
SCORE_FAIR_THRESHOLD = 70
SCORE_MIN_THRESHOLD = 0

# Score Range
SCORE_MIN = 0
SCORE_MAX = 100

# ============================================================================
# Evaluation Dimensions
# ============================================================================

EVALUATION_DIMENSIONS = [
    'Helpfulness',
    'Directness',
    'Critical Thinking',
    'Accuracy',
    'Tone',
    'Safety & Ethics'
]

# Dimension keyword mappings for parsing
DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    'Helpfulness': ['HELPFULNESS', 'HELPFUL'],
    'Directness': ['DIRECTNESS', 'DIRECT'],
    'Critical Thinking': ['CRITICAL THINKING', 'CRITICAL'],
    'Accuracy': ['ACCURACY', 'ACCURATE'],
    'Tone': ['TONE APPROPRIATENESS', 'TONE'],
    'Safety & Ethics': ['SAFETY', 'ETHICS', 'HARMFUL']
}

# ============================================================================
# Default Prompt Sections
# ============================================================================

DEFAULT_PROMPT_SECTIONS = [
    "You are Claude, a helpful AI assistant created by Anthropic.",
    "Be direct and concise. Avoid unnecessary flattery like 'great question' or 'excellent idea'.",
    "Think critically and provide balanced perspectives. Don't just agree with everything.",
    "When uncertain, acknowledge limitations and suggest ways to find better information.",
    "Use examples and analogies to make complex topics more understandable.",
    "Be encouraging but realistic about challenges and potential outcomes."
]

# ============================================================================
# Test Queries
# ============================================================================

# Import ambiguous test queries (for question-asking behavior evaluation)
# These queries are intentionally vague to test if prompts encourage asking
# clarifying questions vs. making assumptions
try:
    from ambiguous_test_queries import AMBIGUOUS_TEST_QUERIES, get_all_queries
    HAS_AMBIGUOUS_QUERIES = True
except ImportError:
    AMBIGUOUS_TEST_QUERIES = []
    HAS_AMBIGUOUS_QUERIES = False

# ============================================================================
# UI Configuration
# ============================================================================

# Query count options for evaluations
QUERY_COUNT_OPTIONS = [1, 5, 10, 15, 20, 25, 30, 40, 50]
DEFAULT_QUERY_COUNT_INDEX = 2  # Default to 10

# Chart colors
COLOR_PRIMARY = "rgb(59, 130, 246)"  # Blue
COLOR_SECONDARY = "rgb(239, 68, 68)"  # Red
COLOR_SUCCESS = "rgb(34, 197, 94)"  # Green
COLOR_WARNING = "rgb(245, 158, 11)"  # Orange
COLOR_ERROR = "rgb(239, 68, 68)"  # Red
COLOR_INFO = "rgb(59, 130, 246)"  # Blue
COLOR_NEUTRAL = "rgb(113, 113, 122)"  # Gray

# Rating colors (for metric cards)
RATING_COLORS = {
    'excellent': '#22c55e',
    'good': '#22c55e',
    'fair': '#f59e0b',
    'poor': '#ef4444',
    'no_data': '#71717a'
}

# Rating gradients
RATING_GRADIENTS = {
    'excellent': "linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.05) 100%)",
    'good': "linear-gradient(135deg, rgba(34, 197, 94, 0.12) 0%, rgba(34, 197, 94, 0.04) 100%)",
    'fair': "linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.04) 100%)",
    'poor': "linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%)",
    'no_data': "linear-gradient(135deg, rgba(113, 113, 122, 0.08) 0%, rgba(113, 113, 122, 0.02) 100%)"
}

# ============================================================================
# Logging Configuration
# ============================================================================

LOG_ROTATION_SIZE = "10 MB"
LOG_RETENTION_DAYS = "30 days"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"

# API calls log specific settings
API_LOG_ROTATION_SIZE = "50 MB"
API_LOG_RETENTION_DAYS = "3 days"

# ============================================================================
# Timeout Settings
# ============================================================================

HTTP_TIMEOUT_SECONDS = 60.0

# ============================================================================
# Helper Functions
# ============================================================================

def calculate_evaluation_cost(n_combinations: int, n_queries: int, n_questions: int) -> float:
    """
    Calculate estimated cost for evaluation run

    Args:
        n_combinations: Number of prompt combinations
        n_queries: Number of test queries
        n_questions: Number of evaluation questions

    Returns:
        Estimated cost in dollars
    """
    total_calls = n_combinations * n_queries * n_questions * 2
    cost = (total_calls * PRICING_INPUT_PER_1K * PRICING_AVG_INPUT_FACTOR +
            total_calls * PRICING_OUTPUT_PER_1K * PRICING_AVG_OUTPUT_FACTOR)
    return cost


def get_rating_from_score(score: float) -> tuple[str, str]:
    """
    Convert a numeric score to a rating label and color

    Args:
        score: Numeric score (0-100)

    Returns:
        Tuple of (rating_label, color_hex)
    """
    if score >= SCORE_EXCELLENT_THRESHOLD:
        return "Excellent", RATING_COLORS['excellent']
    elif score >= SCORE_GOOD_THRESHOLD:
        return "Good", RATING_COLORS['good']
    elif score >= SCORE_FAIR_THRESHOLD:
        return "Fair", RATING_COLORS['fair']
    elif score > SCORE_MIN_THRESHOLD:
        return "Poor", RATING_COLORS['poor']
    else:
        return "No data", RATING_COLORS['no_data']


def get_rating_style(score: float) -> Dict[str, str]:
    """
    Get complete styling for a rating based on score

    Args:
        score: Numeric score (0-100)

    Returns:
        Dictionary with 'gradient', 'border_color', 'shadow' keys
    """
    if score >= SCORE_EXCELLENT_THRESHOLD:
        rating_key = 'excellent'
        border_opacity = "0.4"
        shadow_opacity = "0.15"
    elif score >= SCORE_GOOD_THRESHOLD:
        rating_key = 'good'
        border_opacity = "0.3"
        shadow_opacity = "0.1"
    elif score >= SCORE_FAIR_THRESHOLD:
        rating_key = 'fair'
        border_opacity = "0.3"
        shadow_opacity = "0.1"
    elif score > SCORE_MIN_THRESHOLD:
        rating_key = 'poor'
        border_opacity = "0.3"
        shadow_opacity = "0.1"
    else:
        rating_key = 'no_data'
        border_opacity = "0.2"
        shadow_opacity = "0.1"

    color = RATING_COLORS[rating_key]
    gradient = RATING_GRADIENTS[rating_key]

    # Extract RGB values from hex color
    if color.startswith('#'):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        border_color = f"rgba({r}, {g}, {b}, {border_opacity})"
        shadow_color = f"rgba({r}, {g}, {b}, {shadow_opacity})"
    else:
        border_color = color
        shadow_color = color

    return {
        'gradient': gradient,
        'border_color': border_color,
        'shadow': f"0 4px 16px {shadow_color}"
    }
