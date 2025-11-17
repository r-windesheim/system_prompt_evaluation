# React UI Setup Guide

This guide explains how to run the new React-based Quirk Analysis UI.

## Architecture

```
┌──────────────────┐         ┌──────────────────┐
│   React Frontend │  HTTP   │   FastAPI Backend│
│   (localhost:3000)├────────>│  (localhost:8000)│
└──────────────────┘         └─────────┬────────┘
                                       │
                                       ▼
                            ┌──────────────────────┐
                            │  Existing Python     │
                            │  quirk_analyzer.py   │
                            │  prompt_analyzer.py  │
                            └──────────────────────┘
```

The React frontend calls the FastAPI backend, which is a thin wrapper around the existing Python analysis code.

## Prerequisites

1. **Python 3.10+** with existing dependencies
2. **Node.js 18+** and npm

## Setup Steps

### 1. Install Backend Dependencies

```bash
# In project root
pip install -r requirements.txt
```

New dependencies added:
- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start the Backend API

```bash
# From project root
python api.py
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Test it works:
```bash
curl http://localhost:8000
# Should return: {"status":"ok","service":"Quirk Analysis API","version":"1.0.0"}
```

### 4. Start the Frontend

```bash
# From frontend/ directory
npm run dev
```

You should see:
```
ready - started server on 0.0.0.0:3000, url: http://localhost:3000
```

### 5. Open in Browser

Navigate to: **http://localhost:3000**

## Usage Flow

### Screen 1: Prompt Decomposition
1. Paste your system prompt
2. Click "Analyze Prompt"
3. Review detected sections
4. Edit/enable/disable sections as needed
5. Click "Continue to Analysis"

### Screen 2: Configuration
1. Review selected sections (shown as colored chips)
2. Select a test query from dropdown
3. Set number of responses (default: 30)
4. Review cost estimate
5. Click "Start Analysis"
6. Wait for progress bar to complete (1-5 minutes)

### Screen 3: Results
1. View impact score gauge
2. Read auto-generated summary
3. See stats cards (quirks detected, significant, sections)
4. **Explore color-coded showcase response** ← THE WOW FACTOR
5. Hover over legend items to highlight corresponding phrases
6. View detailed quirk table with statistical analysis
7. Export results as JSON

## Key Features

### Color-Coded Showcase Response
- Each phrase is highlighted with the color of the section that caused it
- Hover over phrases to see section name and quirk type
- Hover over legend items to highlight all phrases from that section
- Visual proof of which prompt sections drive which behaviors

### Statistical Analysis
- P-values showing statistical significance
- Effect sizes (Cohen's d)
- Impact scores (with section rate - without section rate)
- Filters for significant results only

### Export & Share
- Download full analysis as JSON
- All results saved to backend (evaluation history)
- Can review past analyses via API

## API Endpoints

The backend exposes these endpoints:

```
POST /api/decompose-prompt       # Decompose prompt into sections
POST /api/analyze-quirks          # Run full quirk analysis
POST /api/generate-attributions   # Generate color-coded response data
POST /api/estimate-cost           # Estimate API cost
GET  /api/config                  # Get available queries and settings
GET  /api/evaluations             # List past evaluations
GET  /api/evaluation/{id}         # Get specific evaluation
```

## Troubleshooting

### Backend won't start
- **Error**: `ModuleNotFoundError: No module named 'fastapi'`
- **Fix**: `pip install -r requirements.txt`

### Frontend won't start
- **Error**: `Cannot find module 'next'`
- **Fix**: `cd frontend && npm install`

### API connection fails
- **Error**: `Failed to fetch` in browser console
- **Fix**: Ensure backend is running on port 8000
- **Check**: `curl http://localhost:8000` should return OK

### CORS errors
- **Error**: `CORS policy` in browser console
- **Fix**: Check `api.py` allows `http://localhost:3000`
- **Already configured** in our setup

### Prompt decomposition fails
- **Error**: `Decomposition failed`
- **Cause**: OPENROUTER_API_KEY not set or invalid
- **Fix**: Check `.env` file has valid `OPENROUTER_API_KEY`

### Analysis gets stuck
- **Error**: Progress bar stops at X%
- **Cause**: Backend timeout or API rate limit
- **Fix**: Check `logs/api_calls.log` and `logs/evaluation.log`
- **Reduce**: Lower `nResponses` in configure screen

## Development Tips

### Hot Reload
Both frontend and backend support hot reload:
- **Frontend**: Edit React files → auto-refresh
- **Backend**: Edit Python files → uvicorn auto-restarts

### Debugging
- **Frontend logs**: Browser DevTools console
- **Backend logs**: Terminal where `python api.py` runs
- **API call logs**: `logs/api_calls.log`
- **Evaluation logs**: `logs/evaluation.log`

### Testing with Sample Prompt

Paste this prompt to test the full flow:

```
You are a helpful assistant. Be direct and concise.

Think critically about the user's request. Consider multiple perspectives.

When uncertain, acknowledge your limitations clearly.

Use examples to illustrate complex concepts.

Be encouraging but realistic about challenges.
```

Expected result:
- 5 sections detected
- Multiple quirks found (hedge_rate, example_rate, metacommentary_rate, etc.)
- Color-coded response showing attribution
- Statistical significance for key quirks

## Production Deployment

### Option 1: Separate Deployment
- **Frontend**: Deploy to Vercel (auto-detects Next.js)
- **Backend**: Deploy to Railway, Render, or any Python host
- Update `API_BASE_URL` in `frontend/lib/api.ts`

### Option 2: Single Server
- Build frontend: `cd frontend && npm run build`
- Serve static files from FastAPI
- Use reverse proxy (nginx) for routing

## Migration from Streamlit

The React UI **replaces** the Streamlit app (`app.py`) with:
- ✅ All existing functionality
- ✅ Better UX and performance
- ✅ Color-coded showcase (NEW feature)
- ✅ Modern, responsive design

To fully migrate:
1. Run and test the React UI
2. Once stable, deprecate `app.py`
3. Update README to point to React setup
4. Archive Streamlit code for reference

## Cost Considerations

Quirk analysis cost depends on:
- **Number of sections**: N sections = N+1 configs
- **Responses per config**: Default 30 (recommended)
- **Model**: Default `openai/gpt-5-nano-2025-08-07` (~$0.0003/response)

Example:
- 5 sections × 30 responses × 6 configs = 900 responses
- Cost: ~$0.27 per analysis

Use the cost estimator in the UI before running!

## Next Steps

1. **Test the full flow** with a real prompt
2. **Verify color-coded showcase** works correctly
3. **Export results** and check JSON format
4. **Try different queries** to see behavior variations
5. **Adjust parameters** (more/fewer responses)

## Questions?

Check:
- `frontend/README.md` for frontend-specific details
- `CLAUDE.md` for backend architecture
- GitHub issues for known problems
