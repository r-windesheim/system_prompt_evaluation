"""
FastAPI Backend for Quirk Analysis React UI

Thin wrapper around existing quirk_analyzer.py functions.
Exposes HTTP endpoints for the React frontend.

Run with: uvicorn api:app --reload --port 8000
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np

# Import existing analysis functions
from utils.prompt_analyzer import decompose_system_prompt
from utils.quirk_analyzer import (
    analyze_prompt_quirks,
    format_quirk_results_for_ui,
    save_quirk_analysis_results,
    estimate_quirk_analysis_cost,
    extract_phrase_positions
)
from config import (
    QUIRK_ANALYSIS_QUERIES,
    DEFAULT_MODEL,
    BATCH_EVALUATION_FILE,
    EVALUATION_HISTORY_DIR
)

# ============================================================================
# FastAPI App Setup
# ============================================================================

app = FastAPI(
    title="Quirk Analysis API",
    description="Backend for AI prompt behavioral quirk analysis",
    version="1.0.0"
)

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Request/Response Models
# ============================================================================

class DecomposePromptRequest(BaseModel):
    prompt: str
    exclude_factual: bool = True

class DecomposePromptResponse(BaseModel):
    sections: List[str]
    validation_passed: bool
    validation_message: Optional[str] = None

class AnalyzeQuirksRequest(BaseModel):
    sections: List[str]
    test_queries: Optional[List[str]] = None
    n_responses: int = 30
    model: Optional[str] = None
    include_semantic: bool = False

class AnalyzeQuirksResponse(BaseModel):
    analysis_id: str
    quirks: List[Dict[str, Any]]
    total_quirks_detected: int
    full_prompt_rates: Dict[str, float]
    top_3_changes: List[Dict[str, Any]]
    auto_summary: str
    dimensions: Dict[str, Any]
    failed_configs: List[str]
    xml_only_sections: List[int]
    test_queries_used: List[str]

class CostEstimateRequest(BaseModel):
    n_sections: int
    n_responses_per_config: int = 30

class CostEstimateResponse(BaseModel):
    total_cost: float
    total_responses: int
    total_configs: int
    responses_per_config: int
    cost_per_response: float

class Attribution(BaseModel):
    text: str
    start: int
    end: int
    section_id: int
    section_name: str
    quirk_type: str
    color: str

class GenerateAttributionsRequest(BaseModel):
    response_text: str
    quirks: List[Dict[str, Any]]
    sections: List[str]

class GenerateAttributionsResponse(BaseModel):
    response_text: str
    attributions: List[Attribution]

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Quirk Analysis API",
        "version": "1.0.0"
    }

@app.post("/api/decompose-prompt", response_model=DecomposePromptResponse)
async def decompose_prompt(request: DecomposePromptRequest):
    """
    Decompose a system prompt into logical sections

    Uses GPT-4o to intelligently split the prompt into testable sections.
    """
    try:
        # Call existing function (returns dict with 'sections' key)
        result = await decompose_system_prompt(
            system_prompt=request.prompt,
            exclude_factual=request.exclude_factual
        )

        sections = result.get('sections', [])

        # Simple validation
        is_valid = len(sections) > 0
        message = None if is_valid else "No sections detected"

        return DecomposePromptResponse(
            sections=sections,
            validation_passed=is_valid,
            validation_message=message
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decomposition failed: {str(e)}")

@app.post("/api/analyze-quirks", response_model=AnalyzeQuirksResponse)
async def analyze_quirks(request: AnalyzeQuirksRequest):
    """
    Run full quirk analysis with leave-one-out testing

    This is the main endpoint that:
    1. Generates responses with full prompt and leave-one-out variants
    2. Detects quirks in each configuration
    3. Identifies which sections cause which quirks
    4. Returns formatted results for UI display
    """
    try:
        # Use default queries if none provided
        test_queries = request.test_queries or QUIRK_ANALYSIS_QUERIES
        model = request.model or DEFAULT_MODEL

        # Run analysis using existing function
        analysis_results = await analyze_prompt_quirks(
            sections=request.sections,
            test_queries=test_queries,
            n=request.n_responses,
            model=model,
            spike_threshold=1.5,
            min_impact=1.0,
            include_semantic=request.include_semantic
        )

        # Format for UI
        formatted_results = format_quirk_results_for_ui(analysis_results)

        # Save results
        save_paths = save_quirk_analysis_results(
            analysis_results=analysis_results,
            sections=request.sections,
            test_queries=test_queries,
            model=model
        )

        # Generate unique ID for this analysis
        analysis_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Convert numpy types to Python native types for JSON serialization
        def convert_numpy_types(obj):
            """Recursively convert numpy types to Python native types"""
            if isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            return obj

        # Clean the results
        clean_results = convert_numpy_types({
            'quirks': formatted_results['quirks'],
            'total_quirks_detected': formatted_results['total_quirks_detected'],
            'full_prompt_rates': formatted_results['full_prompt_rates'],
            'top_3_changes': formatted_results['top_3_changes'],
            'auto_summary': formatted_results['auto_summary'],
            'dimensions': formatted_results['dimensions'],
            'failed_configs': analysis_results.get('failed_configs', []),
            'xml_only_sections': analysis_results.get('xml_only_sections', []),
        })

        return AnalyzeQuirksResponse(
            analysis_id=analysis_id,
            quirks=clean_results['quirks'],
            total_quirks_detected=clean_results['total_quirks_detected'],
            full_prompt_rates=clean_results['full_prompt_rates'],
            top_3_changes=clean_results['top_3_changes'],
            auto_summary=clean_results['auto_summary'],
            dimensions=clean_results['dimensions'],
            failed_configs=clean_results['failed_configs'],
            xml_only_sections=clean_results['xml_only_sections'],
            test_queries_used=test_queries
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/estimate-cost", response_model=CostEstimateResponse)
async def estimate_cost(request: CostEstimateRequest):
    """
    Estimate the API cost for running quirk analysis

    Helps users understand cost before running full analysis.
    """
    try:
        cost_breakdown = estimate_quirk_analysis_cost(
            n_sections=request.n_sections,
            n_responses_per_config=request.n_responses_per_config
        )

        return CostEstimateResponse(**cost_breakdown)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cost estimation failed: {str(e)}")

@app.get("/api/evaluations")
async def list_evaluations():
    """
    List all saved evaluations from history

    Returns metadata for all quirk analysis runs.
    """
    try:
        history_dir = Path(EVALUATION_HISTORY_DIR)

        if not history_dir.exists():
            return {"evaluations": []}

        evaluations = []
        for file_path in sorted(history_dir.glob("quirk_analysis_*.csv"), reverse=True):
            # Extract timestamp from filename
            timestamp_str = file_path.stem.replace("quirk_analysis_", "")

            # Read first row to get metadata
            df = pd.read_csv(file_path, nrows=1)

            evaluations.append({
                "id": timestamp_str,
                "filename": file_path.name,
                "timestamp": df['timestamp'].iloc[0] if 'timestamp' in df.columns else timestamp_str,
                "model": df['model'].iloc[0] if 'model' in df.columns else "unknown",
                "n_sections": df['n_sections'].iloc[0] if 'n_sections' in df.columns else 0,
            })

        return {"evaluations": evaluations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list evaluations: {str(e)}")

@app.get("/api/evaluation/{evaluation_id}")
async def get_evaluation(evaluation_id: str):
    """
    Get detailed results for a specific evaluation

    Returns full quirk analysis results from saved CSV.
    """
    try:
        # Find the file
        history_dir = Path(EVALUATION_HISTORY_DIR)
        file_path = history_dir / f"quirk_analysis_{evaluation_id}.csv"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")

        # Read the CSV
        df = pd.read_csv(file_path)

        # Convert to list of dicts
        results = df.to_dict(orient='records')

        return {
            "evaluation_id": evaluation_id,
            "results": results,
            "total_quirks": len(results)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load evaluation: {str(e)}")

@app.post("/api/generate-attributions", response_model=GenerateAttributionsResponse)
async def generate_attributions(request: GenerateAttributionsRequest):
    """
    Generate phrase attributions for color-coded visualization

    Takes a response and quirk results, extracts phrase positions,
    and maps them to sections based on impact scores.
    """
    try:
        # Color scheme for sections (from FIGMA_SPEC.md)
        SECTION_COLORS = [
            "#3b82f6",  # Blue
            "#10b981",  # Green
            "#f59e0b",  # Orange
            "#ef4444",  # Red
            "#8b5cf6",  # Purple
            "#06b6d4",  # Cyan
            "#ec4899",  # Pink
            "#84cc16",  # Lime
        ]

        attributions = []

        # For each quirk, extract phrase positions and attribute to section
        for quirk in request.quirks:
            quirk_type = quirk.get('technical_name') or quirk.get('quirk_type')
            section_id = quirk.get('attribution', {}).get('section_index', 0)

            # Extract positions where this quirk appears
            positions = extract_phrase_positions(request.response_text, quirk_type)

            # Map each position to this section
            for pos in positions:
                # Get section name (truncated)
                section_text = request.sections[section_id] if section_id < len(request.sections) else "Unknown"
                section_name = section_text[:50] + "..." if len(section_text) > 50 else section_text

                attributions.append(Attribution(
                    text=pos['text'],
                    start=pos['start'],
                    end=pos['end'],
                    section_id=section_id,
                    section_name=section_name,
                    quirk_type=quirk_type,
                    color=SECTION_COLORS[section_id % len(SECTION_COLORS)]
                ))

        # Sort by start position
        attributions.sort(key=lambda a: a.start)

        return GenerateAttributionsResponse(
            response_text=request.response_text,
            attributions=attributions
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attribution generation failed: {str(e)}")

@app.get("/api/config")
async def get_config():
    """
    Get API configuration and available options

    Returns predefined queries, models, etc.
    """
    return {
        "quirk_analysis_queries": QUIRK_ANALYSIS_QUERIES,
        "default_model": DEFAULT_MODEL,
        "default_n_responses": 30
    }

# ============================================================================
# Run with: uvicorn api:app --reload --port 8000
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
