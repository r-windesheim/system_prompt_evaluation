# AI System Prompt Testing Framework

## Overview

A systematic tool for evaluating which sections of AI system prompts drive specific behaviors. The framework decomposes prompts into components, tests all combinations against diverse queries, and provides interactive analysis of results.

## Core Architecture

### Data Flow
1. **Prompt Decomposition**: System prompts represented as `List[str]` where each string is a testable section
2. **Batch Evaluation**: Pre-compute all prompt combinations using async API calls
3. **Multi-dimensional Scoring**: Evaluate responses across 6 criteria (0-100 scale)
4. **Interactive Analysis**: Web interface for exploring results with real-time filtering

### Key Components

**`evaluation.py`** - Core evaluation engine
- `PromptEvaluator` class handles batch processing with retry logic
- Async API calls via OpenRouter for cost efficiency
- Comprehensive error handling and logging

**`utils/llm_call.py`** - API interface
- Async HTTP client using httpx
- Environment-based API key management
- Full request/response logging with loguru

**`app.py`** - Streamlit web interface
- Interactive prompt builder with section toggles
- Radar and bar chart visualizations using plotly
- Real-time filtering and comparison against full prompt baseline

## Evaluation Methodology

### Test Dimensions
- Helpfulness: Practical value and actionability
- Directness: Clarity and conciseness  
- Critical Thinking: Balanced analysis and nuanced reasoning
- Accuracy: Factual correctness and reliability
- Tone Appropriateness: Professional and contextually suitable communication
- Safety & Ethics: Responsible and ethical guidance

### Scoring System
Each response evaluated 0-100 with specific criteria and examples for consistency. Uses GPT-4o-mini for cost-effective evaluation at ~$0.002 per assessment.

## Technical Features

### Performance Optimizations
- Async batch processing for parallel API calls
- File-based caching system using pandas CSV
- Retry mechanism with exponential backoff
- Rate limiting protection

### Data Management
- Complete audit trail in `logs/api_calls.log`
- Cached results in `cached_results/batch_evaluation.csv`
- Error tracking and recovery via `retry_failed_evaluations.py`

### Cost Efficiency
- Strategic use of cheaper models (GPT-4o-mini vs GPT-4)
- Batch processing reduces API overhead
- One-time computation enables unlimited analysis

## Usage Workflow

1. **Setup**: Configure OpenRouter API key in `.env`
2. **Evaluation**: Run batch evaluation script (`run_evaluation.py`)
3. **Analysis**: Launch Streamlit app for interactive exploration
4. **Insights**: Toggle prompt sections to see impact on different behavioral dimensions

## Results

The framework successfully evaluated 1,890 prompt combinations across 6 dimensions, providing quantitative insights into which prompt components drive specific AI behaviors. Total evaluation cost: approximately $4 using GPT-4o-mini.

## Files Structure

```
├── evaluation.py           # Core evaluation engine
├── run_evaluation.py       # Main evaluation script
├── app.py                 # Streamlit web interface
├── retry_failed_evaluations.py # Error recovery tool
├── utils/
│   ├── llm_call.py        # API interface
│   └── ui_helpers.py      # UI helper functions
├── cached_results/        # Evaluation data
├── logs/                  # API call logs
└── requirements.txt       # Dependencies
```
