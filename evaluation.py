"""
Batch Evaluation Logic for Prompt Testing - FIXED VERSION

This module handles the systematic evaluation of prompt combinations
to understand which sections drive specific AI behaviors.

MAJOR FIX: Now evaluates all dimensions on the SAME response instead of making
separate API calls for each dimension, reducing API calls by ~83%.
"""
import asyncio
import re
import uuid
from typing import List, Dict, Any, Tuple
from itertools import combinations
from datetime import datetime

import pandas as pd
from loguru import logger
import textstat

from utils.latteries.caller import llm_call
from utils.question_asking_analyzer import analyze_question_asking
from utils.rate_limiter import openrouter_limiter
from config import (
    SCORE_YES, SCORE_NO, SCORE_AMBIGUOUS, SCORE_DEFAULT,
    SCORE_MIN, SCORE_MAX,
    EVALUATION_HISTORY_DIR, BATCH_EVALUATION_FILE,
    LOG_ROTATION_SIZE, LOG_RETENTION_DAYS, LOG_FORMAT,
    EVALUATION_LOG_FILE, DEFAULT_MAX_CONCURRENT, FALLBACK_MODEL
)
import os

# Configure logging for evaluation runs - remove default stderr handler
logger.remove()  # Remove default handler that prints to stderr
logger.add(EVALUATION_LOG_FILE, rotation=LOG_ROTATION_SIZE, retention=LOG_RETENTION_DAYS, format=LOG_FORMAT)


def calculate_response_metrics(response: str) -> Dict[str, Any]:
    """Calculate text metrics for a response, including question-asking behavior"""
    # Basic readability metrics
    basic_metrics = {
        "word_count": textstat.lexicon_count(response),
        "char_count": len(response),
        "sentence_count": textstat.sentence_count(response),
        "readability_score": textstat.flesch_reading_ease(response),
        "grade_level": textstat.flesch_kincaid_grade(response)
    }

    # Question-asking behavior metrics
    qa_metrics = analyze_question_asking(response)

    # Combine all metrics
    return {
        **basic_metrics,
        "question_marks": qa_metrics["question_marks"],
        "clarification_phrases": qa_metrics["clarification_phrases"],
        "assumption_phrases": qa_metrics["assumption_phrases"],
        "question_sentences": qa_metrics["question_sentences"],
        "asks_vs_assumes": qa_metrics["asks_vs_assumes"],
        "question_asking_score": qa_metrics["question_asking_score"]
    }


class PromptEvaluator:
    """
    Handles batch evaluation of prompt combinations

    Core workflow:
    1. Take a system prompt as List[str] (each string is a section)
    2. Generate all relevant combinations of sections
    3. Test each combination against a set of test queries
    4. Evaluate responses using Y/N questions to LLMs
    5. Cache results for instant UI access
    6. Automatically backup each evaluation run with timestamp
    """

    def __init__(self, model_name: str = FALLBACK_MODEL, eval_model: str = None, max_concurrent: int = DEFAULT_MAX_CONCURRENT):
        self.model_name = model_name  # Model for generating responses
        self.eval_model = eval_model or model_name  # Model for evaluating responses (can be different/better)
        self.results_cache = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        # Ensure backup directory exists
        os.makedirs(EVALUATION_HISTORY_DIR, exist_ok=True)

    def generate_prompt_combinations(self, prompt_sections: List[str]) -> List[Tuple[int, ...]]:
        """
        Generate all relevant combinations of prompt sections

        Args:
            prompt_sections: List of prompt section strings

        Returns:
            List of tuples, where each tuple contains indices of sections to include
        """
        n_sections = len(prompt_sections)
        combinations_to_test = []

        # Generate all possible combinations
        for r in range(1, n_sections + 1):
            for combo in combinations(range(n_sections), r):
                combinations_to_test.append(combo)

        logger.info(f"Generated {len(combinations_to_test)} combinations from {n_sections} sections")
        return combinations_to_test

    def combine_sections(self, prompt_sections: List[str], section_indices: Tuple[int, ...]) -> str:
        """
        Combine selected prompt sections into a single system prompt

        Args:
            prompt_sections: List of all available sections
            section_indices: Tuple of indices to include

        Returns:
            Combined system prompt string
        """
        selected_sections = [prompt_sections[i] for i in section_indices]
        return "\n\n".join(selected_sections)

    def create_evaluation_backup(self, df: pd.DataFrame, run_type: str = "batch_eval") -> str:
        """
        Create a timestamped backup of the evaluation results

        Args:
            df: DataFrame containing evaluation results
            run_type: Type of evaluation run (e.g., "batch_eval", "custom_prompt", "stress_test")

        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{run_type}_{timestamp}.csv"
        backup_path = os.path.join(EVALUATION_HISTORY_DIR, backup_filename)

        # Save the backup
        df.to_csv(backup_path, index=False)
        logger.info(f"Created evaluation backup: {backup_path} ({len(df)} results)")

        return backup_path

    def _parse_yn_score(self, result_clean: str) -> int:
        """
        Parse Y/N response into a score

        Args:
            result_clean: Cleaned (stripped, uppercased) evaluation result

        Returns:
            Score (100 for Yes, 0 for No, 50 for ambiguous)
        """
        if result_clean in ['Y', 'YES']:
            return SCORE_YES
        elif result_clean in ['N', 'NO']:
            return SCORE_NO
        elif 'Y' in result_clean and 'N' not in result_clean:
            return SCORE_YES
        elif 'N' in result_clean and 'Y' not in result_clean:
            return SCORE_NO
        else:
            return SCORE_AMBIGUOUS

    def _parse_numeric_score(self, result: str) -> int:
        """
        Parse numeric (0-100) response into a score

        Args:
            result: Evaluation result string

        Returns:
            Score (0-100), or SCORE_DEFAULT if parsing fails
        """
        try:
            score = int(result.strip().upper())
            return max(SCORE_MIN, min(SCORE_MAX, score))
        except ValueError:
            # Try to extract first number found
            numbers = re.findall(r'\b(\d{1,3})\b', result)
            if numbers:
                return max(SCORE_MIN, min(SCORE_MAX, int(numbers[0])))
            return SCORE_DEFAULT

    def _create_error_result(self, error: Exception) -> Dict[str, Any]:
        """
        Create standardized error result structure

        Args:
            error: Exception that occurred

        Returns:
            Dictionary with error information
        """
        return {
            "result": f"ERROR: {str(error)}",
            "score": None,
            "success": False
        }

    def _create_result_dict(
        self,
        system_prompt: str,
        test_query: str,
        response: str,
        eval_question: str,
        eval_result: Dict[str, Any],
        metrics: Dict[str, Any],
        error: str = None,
        section_indices: str = None,
        section_names: str = None,
        config_name: str = None
    ) -> Dict[str, Any]:
        """
        Create standardized result dictionary

        Args:
            system_prompt: The system prompt used
            test_query: The test query used
            response: The AI response
            eval_question: The evaluation question
            eval_result: Result from evaluation
            metrics: Text metrics
            error: Optional error message

        Returns:
            Standardized result dictionary
        """
        result = {
            "system_prompt": system_prompt,
            "test_query": test_query,
            "response": response,
            "evaluation_question": eval_question,
            "evaluation_result": eval_result["result"],
            "evaluation_score": eval_result["score"],
            "word_count": metrics.get("word_count", 0),
            "char_count": metrics.get("char_count", 0),
            "sentence_count": metrics.get("sentence_count", 0),
            "readability_score": metrics.get("readability_score", 0),
            "grade_level": metrics.get("grade_level", 0),
            "question_marks": metrics.get("question_marks", 0),
            "clarification_phrases": metrics.get("clarification_phrases", 0),
            "assumption_phrases": metrics.get("assumption_phrases", 0),
            "question_sentences": metrics.get("question_sentences", 0),
            "asks_vs_assumes": metrics.get("asks_vs_assumes", "neutral"),
            "question_asking_score": metrics.get("question_asking_score", 0),
            "success": eval_result["success"],
            "section_indices": section_indices if section_indices is not None else "",
            "section_names": section_names if section_names is not None else "",
            "config_name": config_name if config_name is not None else ""
        }
        if error:
            result["error"] = error
        return result

    async def _evaluate_response(
        self,
        response: str,
        evaluation_question: str,
        eval_id: str,
        test_query: str = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single response against one evaluation question

        Args:
            response: The AI response to evaluate
            evaluation_question: The evaluation question to apply
            eval_id: Unique ID for logging
            test_query: The original user query (for context)

        Returns:
            Dictionary with evaluation result and score
        """
        try:
            # Construct evaluation prompt with context
            is_yn_question = "Answer only Y or N" in evaluation_question

            # Build context-aware evaluation prompt
            if test_query:
                # Add context for both Y/N and 0-100 scoring
                eval_prompt = f"""ORIGINAL USER QUERY:
{test_query}

AI RESPONSE TO EVALUATE:
{response}

{evaluation_question}"""
            else:
                # Fallback to original format if no query context
                if is_yn_question:
                    eval_prompt = f"Response to evaluate: {response}\n\n{evaluation_question}"
                else:
                    eval_prompt = f"Response to evaluate: {response}\n\n{evaluation_question}\n\nRespond with ONLY a number between 0-100. No explanation, just the score."

            eval_messages = [{"role": "user", "content": eval_prompt}]

            # Get evaluation from LLM (using potentially better eval model)
            # Apply rate limiting to prevent API overload
            await openrouter_limiter.acquire()
            evaluation_result = await llm_call(self.eval_model, eval_messages, call_type="evaluation")
            evaluation_result_clean = evaluation_result.strip().upper()

            # Parse score based on question type
            if is_yn_question:
                evaluation_score = self._parse_yn_score(evaluation_result_clean)
            else:
                evaluation_score = self._parse_numeric_score(evaluation_result)

            logger.info(f"EVAL_DIMENSION | ID: {eval_id} | Question: {evaluation_question[:50]}... | Score: {evaluation_score}")

            return {
                "result": evaluation_result,
                "score": evaluation_score,
                "success": True
            }

        except Exception as e:
            logger.error(f"EVAL_DIMENSION_ERROR | ID: {eval_id} | Question: {evaluation_question[:50]}... | Error: {e}")
            return self._create_error_result(e)

    async def _evaluate_with_semaphore(
        self,
        system_prompt: str,
        test_query: str,
        evaluation_questions: List[str],
        section_indices: str = None,
        section_names: str = None,
        config_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Wrapper that uses semaphore to limit concurrent API calls
        """
        async with self.semaphore:
            return await self.evaluate_prompt_query_combination(
                system_prompt, test_query, evaluation_questions,
                section_indices, section_names, config_name
            )

    async def evaluate_prompt_query_combination(
        self,
        system_prompt: str,
        test_query: str,
        evaluation_questions: List[str],
        section_indices: str = None,
        section_names: str = None,
        config_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate one prompt-query combination across all evaluation dimensions

        This is the new efficient approach:
        1. Generate ONE response for the prompt-query pair
        2. Evaluate that SAME response across all dimensions
        3. Return results for all dimensions

        Args:
            system_prompt: The combined system prompt to test
            test_query: User query to test the prompt with
            evaluation_questions: List of evaluation questions (all dimensions)

        Returns:
            List of dictionaries with evaluation results for each dimension
        """
        # Generate unique evaluation ID for tracking
        eval_id = str(uuid.uuid4())[:8]
        logger.info(f"=== COMBINATION START | ID: {eval_id} ===")
        logger.info(f"SYSTEM_PROMPT | ID: {eval_id} | {system_prompt}")
        logger.info(f"TEST_QUERY | ID: {eval_id} | {test_query}")

        try:
            # Step 1: Generate ONE response for this prompt-query combination
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": test_query}
            ]

            # Apply rate limiting to prevent API overload
            await openrouter_limiter.acquire()
            response = await llm_call(self.model_name, messages, call_type="main_response")
            logger.info(f"MAIN_RESPONSE | ID: {eval_id} | {response}")

            # Step 2: Calculate text metrics once
            metrics = calculate_response_metrics(response)
            logger.info(f"TEXT_METRICS | ID: {eval_id} | Words: {metrics['word_count']} | Readability: {metrics['readability_score']:.1f} | Grade: {metrics['grade_level']:.1f}")

            # Step 3: Evaluate this SAME response across all dimensions
            results = []
            for i, eval_question in enumerate(evaluation_questions):
                eval_result = await self._evaluate_response(
                    response,
                    eval_question,
                    f"{eval_id}-{i+1}",
                    test_query=test_query
                )
                result = self._create_result_dict(
                    system_prompt, test_query, response, eval_question, eval_result, metrics,
                    section_indices=section_indices, section_names=section_names, config_name=config_name
                )
                results.append(result)

            successful_evals = len([r for r in results if r["success"]])
            logger.info(f"=== COMBINATION END | ID: {eval_id} | Dimensions: {successful_evals}/{len(evaluation_questions)} successful ===")
            return results

        except Exception as e:
            logger.error(f"COMBINATION_ERROR | ID: {eval_id} | Error: {e}")
            logger.info(f"=== COMBINATION END | ID: {eval_id} | Status: FAILED ===")

            # Return failed results for all dimensions
            error_metrics = {"word_count": 0, "char_count": 0, "sentence_count": 0, "readability_score": 0, "grade_level": 0}
            error_result = self._create_error_result(e)

            failed_results = []
            for eval_question in evaluation_questions:
                result = self._create_result_dict(
                    system_prompt, test_query, "ERROR: Failed to get response",
                    eval_question, error_result, error_metrics, error=str(e),
                    section_indices=section_indices, section_names=section_names, config_name=config_name
                )
                failed_results.append(result)
            return failed_results

    async def run_batch_evaluation(
        self,
        prompt_sections: List[str],
        test_queries: List[str],
        evaluation_questions: List[str],
        section_names: Dict[int, str] = None
    ) -> pd.DataFrame:
        """
        Run complete batch evaluation of all combinations

        Args:
            prompt_sections: List of prompt section strings
            test_queries: List of test queries to evaluate
            evaluation_questions: List of Y/N evaluation questions

        Returns:
            DataFrame with all evaluation results
        """
        logger.info("Starting batch evaluation...")

        # Generate combinations
        combinations = self.generate_prompt_combinations(prompt_sections)

        # Prepare all evaluation tasks (NEW EFFICIENT APPROACH)
        # Instead of evaluating each dimension separately, we evaluate each prompt-query combination once
        # and get all dimension scores for the same response
        tasks = []
        for combo_indices in combinations:
            system_prompt = self.combine_sections(prompt_sections, combo_indices)

            # Generate metadata for this combination
            if section_names:
                # Create section metadata strings
                indices_str = ",".join(str(i) for i in combo_indices)
                names_list = [section_names.get(i, f"section_{i}") for i in combo_indices]
                names_str = ",".join(names_list)

                # Create human-readable config name using section numbers (1-indexed)
                # Note: combo_indices is never empty since we start at r=1 in generate_prompt_combinations
                display_indices = [str(i + 1) for i in combo_indices]
                config_name = "+".join(display_indices)
            else:
                indices_str = None
                names_str = None
                config_name = None

            for test_query in test_queries:
                # Create one task per prompt-query combination (not per dimension!)
                # Use semaphore wrapper to limit concurrent API calls
                task = self._evaluate_with_semaphore(
                    system_prompt, test_query, evaluation_questions,
                    indices_str, names_str, config_name
                )
                tasks.append(task)

        total_combinations = len(combinations) * len(test_queries)
        total_api_calls = total_combinations * (1 + len(evaluation_questions))  # 1 main response + N evaluations
        old_api_calls = total_combinations * len(evaluation_questions) * 2  # Old approach: 2 calls per dimension

        logger.info(f"Running {len(tasks)} combination tasks ({total_combinations} combinations × {len(evaluation_questions)} dimensions = {total_combinations * len(evaluation_questions)} total evaluations)")
        logger.info("NEW EFFICIENT APPROACH:")
        logger.info(f"  API calls: {total_api_calls}")
        logger.info(f"  Old approach would have used: {old_api_calls}")
        logger.info(f"  Savings: {old_api_calls - total_api_calls} calls ({((old_api_calls - total_api_calls) / old_api_calls * 100):.1f}% reduction)")
        logger.info(f"  Concurrent limit: {self.semaphore._value} simultaneous requests")

        # Execute all tasks with semaphore controlling concurrency
        all_results = []

        logger.info(f"Starting concurrent execution with semaphore (max {self.semaphore._value} concurrent)")
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results since each task returns a list of dimension results
        for result_list in batch_results:
            if isinstance(result_list, list):
                all_results.extend(result_list)
            elif isinstance(result_list, Exception):
                logger.error(f"Task failed: {result_list}")

        # Convert to DataFrame
        df = pd.DataFrame(all_results)

        # Save to cache
        df.to_csv(BATCH_EVALUATION_FILE, index=False)
        logger.info(f"Saved {len(df)} results to {BATCH_EVALUATION_FILE}")

        # Create timestamped backup
        backup_path = self.create_evaluation_backup(df, "batch_eval")

        return df

    def load_cached_results(self, cache_file: str = BATCH_EVALUATION_FILE) -> pd.DataFrame:
        """
        Load previously computed evaluation results
        """
        try:
            return pd.read_csv(cache_file)
        except FileNotFoundError:
            logger.warning(f"Cache file {cache_file} not found, returning empty DataFrame")
            return pd.DataFrame()


# Example usage and testing
async def example_evaluation():
    """Example of how to use the PromptEvaluator"""

    # Example prompt sections
    prompt_sections = [
        "You are a helpful AI assistant.",
        "Always be polite and respectful.",
        "Provide detailed explanations when possible.",
        "If you're unsure, say so clearly."
    ]

    # Example test queries
    test_queries = [
        "What is the capital of France?",
        "Explain quantum computing in simple terms."
    ]

    # Example evaluation questions
    evaluation_questions = [
        "Does the response show politeness? Answer only Y or N.",
        "Does the response provide detailed explanations? Answer only Y or N."
    ]

    evaluator = PromptEvaluator()
    results = await evaluator.run_batch_evaluation(
        prompt_sections, test_queries, evaluation_questions
    )

    print(f"Completed evaluation with {len(results)} results")
    return results


if __name__ == "__main__":
    # Run example evaluation
    asyncio.run(example_evaluation())
