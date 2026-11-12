"""
Prompt Analysis Utilities
Decompose system prompts into logical sections using LLM analysis
"""
from typing import List, Dict, Any
try:
    from .latteries.caller import llm_call
except ImportError:
    from latteries.caller import llm_call
from loguru import logger

async def decompose_system_prompt(system_prompt: str, model_name: str = "openai/gpt-4o", exclude_factual: bool = True) -> Dict[str, Any]:
    """
    Use a powerful LLM to decompose a system prompt into logical sections

    Args:
        system_prompt: The full system prompt to analyze
        model_name: Model to use for analysis (default: GPT-4o for better analysis)
        exclude_factual: If True, exclude factual content and keep only behavioral instructions.
                        If False, decompose ALL content into logical sections.
        
    Returns:
        Dict with 'sections' (List[str]) and 'analysis' (str)
    """
    
    if exclude_factual:
        analysis_prompt = f"""Extract ONLY the behavioral instructions from this system prompt. Your goal is to extract EVERY distinct behavioral instruction - long prompts may have 20-50+ instructions, that's expected and desired. Return the EXACT original text, do not paraphrase or interpret.

SYSTEM PROMPT TO ANALYZE:
{system_prompt}

CRITICAL RULES:
1. ONLY extract sentences that tell the AI HOW to behave, act, or respond
2. NEVER include factual statements about WHAT is true (facts, data, assertions)
3. Return the EXACT original wording - do not rephrase, summarize, or interpret
4. Skip any sentence that states facts, provides information, or asserts what is true
5. Focus on verbs like: "be", "think", "acknowledge", "use", "avoid", "respond", etc.
6. Be THOROUGH - extract EVERY behavioral instruction, even if the list is very long
7. DO NOT skip or combine instructions to keep the list short

BEHAVIORAL INSTRUCTIONS (include these types):
✅ "Be direct and concise in your responses"
✅ "Think critically and provide balanced perspectives" 
✅ "Acknowledge uncertainty when appropriate"
✅ "Use examples to explain complex topics"
✅ "You are Claude, a helpful AI assistant"

FACTUAL ASSERTIONS (exclude these types):
❌ "The current date is October 2024"
❌ "Climate change is real and caused by humans"
❌ "The population is 330 million"
❌ "Paris is the capital of France"
❌ Any statement about what IS true vs how to ACT

RESPOND IN THIS EXACT FORMAT:

SECTIONS:
1. [Exact original text of first behavioral instruction]
2. [Exact original text of second behavioral instruction]
3. [Exact original text of third behavioral instruction]
..."""
    else:
        analysis_prompt = f"""Decompose this system prompt into ALL logical sections. Group related sentences together into coherent sections. Return the EXACT original text, do not paraphrase or interpret.

SYSTEM PROMPT TO ANALYZE:
{system_prompt}

CRITICAL RULES:
1. Split the prompt into distinct logical sections - each section should be ONE coherent topic or theme
2. Keep content within XML tags together as a single section (e.g., everything inside <election_info> is one section)
3. Include ALL content - behavioral instructions, facts, context, dates, everything
4. Return the EXACT original wording - do not rephrase, summarize, or interpret
5. Target section counts based on prompt size:
   - Very long prompts (20+ paragraphs): Aim for 25-40 sections
   - Long prompts (10-20 paragraphs): Aim for 15-25 sections
   - Medium prompts (5-10 paragraphs): Aim for 10-15 sections
   - Short prompts (1-5 paragraphs): Aim for 5-10 sections
6. Each section should be 1-5 related sentences that form a complete testable idea
7. When in doubt, split into separate sections rather than combining - we need granularity for testing
8. DO NOT create overly broad sections that combine unrelated topics

INCLUDE EVERYTHING:
✅ Behavioral instructions: "Be direct and concise"
✅ Identity statements: "You are Claude, an AI assistant"
✅ Factual information: "The current date is October 2024"
✅ Context: "Climate change is real and caused by humans"
✅ Guidelines: "Always cite your sources"
✅ Constraints: "Never provide medical advice"

RESPOND IN THIS EXACT FORMAT:

SECTIONS:
1. [Exact original text of first section]
2. [Exact original text of second section]
3. [Exact original text of third section]
..."""

    messages = [
        {"role": "user", "content": analysis_prompt}
    ]
    
    try:
        response = await llm_call(model_name, messages, call_type="prompt_analysis")
        
        # Parse the response
        sections = []
        
        lines = response.split('\n')

        for line in lines:
            line = line.strip()

            # Look for numbered lines (whether or not there's a SECTIONS: header)
            # Handle both single-digit (1. ) and multi-digit (10. ) numbers
            if line and line[0].isdigit():
                # Find the position of the first ". " after the number
                dot_pos = line.find('. ')
                if dot_pos > 0 and line[:dot_pos].isdigit():
                    section_text = line[dot_pos + 2:].strip()  # Remove "XX. "
                    if section_text:
                        sections.append(section_text)
        
        logger.info(f"Decomposed prompt into {len(sections)} sections")
        
        mode_text = "behavioral instructions" if exclude_factual else "sections"
        return {
            "sections": sections,
            "analysis": f"Extracted {len(sections)} {mode_text}",
            "original_prompt": system_prompt,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Failed to decompose prompt: {e}")
        return {
            "sections": [],
            "analysis": f"Error: {str(e)}",
            "original_prompt": system_prompt,
            "success": False
        }

