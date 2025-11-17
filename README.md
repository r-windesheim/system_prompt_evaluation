# AI Prompt Quirk Analyzer

> Systematically discover which sections of your system prompts drive specific AI behaviors

A powerful tool for understanding how different parts of your AI system prompts affect behavioral quirks, with beautiful color-coded visualization showing exactly which prompt sections cause which phrases in responses.

## 🚀 Quick Start

### Setup (First Time)

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..

# Set up API key
echo "OPENROUTER_API_KEY=your_key_here" > .env
```

### Run the Application

**Option 1: Automated (Recommended)**
```bash
./start.sh
```

**Option 2: Manual (Two Terminals)**

Terminal 1 - Backend:
```bash
python3 api.py
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

Then open: **http://localhost:3000**

## ✨ Features

### 🎯 Color-Coded Showcase Response
See exactly which phrases in AI responses are caused by which prompt sections - visually highlighted with interactive hover effects.

### 📊 Statistical Analysis
- Leave-one-out testing methodology
- P-values and effect sizes
- Impact scores (with/without each section)
- 30+ behavioral quirk types detected

### 🔬 Comprehensive Metrics
- Syntactic quirks (hedging, parentheses, examples, etc.)
- Response metrics (readability, word count, formality)
- Question-asking behavior analysis
- Section interaction detection

### 💎 Beautiful Modern UI
- React + Next.js + TypeScript
- Tailwind CSS styling
- Smooth animations and transitions
- Interactive visualizations
- Export results as JSON

## 📖 How It Works

1. **Paste Your Prompt** - Input your system prompt
2. **Decompose** - GPT-4o intelligently splits it into testable sections
3. **Configure** - Select test query and number of responses
4. **Analyze** - Leave-one-out testing with 30+ responses per configuration
5. **Results** - Color-coded showcase showing which sections cause which behaviors

## 🏗️ Architecture

```
React Frontend (localhost:3000)
        ↓ HTTP/JSON
FastAPI Backend (localhost:8000)
        ↓ Python
Existing Quirk Analysis Code
        ↓ LLM Calls
OpenRouter API (GPT-4o, GPT-4o-mini)
```

**Key Components:**
- `api.py` - FastAPI backend (HTTP wrapper)
- `frontend/` - Next.js React application
- `utils/quirk_analyzer.py` - Core quirk detection
- `evaluation.py` - Evaluation engine
- `config.py` - Central configuration

## 📚 Documentation

- **[REACT_SETUP.md](REACT_SETUP.md)** - Complete setup guide
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical details
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - File organization
- **[CLAUDE.md](CLAUDE.md)** - Claude Code instructions

## 🔧 Tech Stack

### Frontend
- Next.js 14 (Pages Router)
- TypeScript
- Tailwind CSS
- React Hooks

### Backend
- FastAPI (Python 3.9+)
- Pydantic for validation
- Asyncio for concurrency
- NumPy/Pandas for analysis

### Analysis
- Latteries LLM framework
- OpenRouter API
- Statistical testing (scipy)
- Regex pattern matching

## 💰 Cost

Typical analysis (5 sections, 30 responses):
- **Configurations**: 6 (1 full + 5 leave-one-out)
- **Total responses**: 180
- **Estimated cost**: ~$0.05-0.10
- **Time**: 1-3 minutes

The UI shows cost estimates before running.

## 🗂️ Project Structure

```
/                           # Root
├── api.py                 # FastAPI backend
├── frontend/              # React UI
├── utils/                 # Python utilities
├── cached_results/        # Results cache
├── logs/                  # Application logs
├── deprecated/            # Old Streamlit UI (archived)
└── [docs]                 # Documentation
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for details.

## ⚙️ Configuration

Edit `config.py` to customize:
- Default model (`DEFAULT_MODEL`)
- Concurrency limits (`DEFAULT_MAX_CONCURRENT`)
- Evaluation dimensions
- Color schemes
- File paths

## 🐛 Troubleshooting

### Backend won't start
```bash
# Install dependencies
pip3 install -r requirements.txt

# Check Python version (need 3.9+)
python3 --version
```

### Frontend won't start
```bash
cd frontend
npm install
npm run dev
```

### API connection fails
- Ensure backend is running: `curl http://localhost:8000`
- Check CORS is enabled (already configured)

### Analysis fails
- Check `.env` has valid `OPENROUTER_API_KEY`
- Review `logs/api_calls.log` and `logs/evaluation.log`

## 📝 Development

### Backend
```bash
# Edit API endpoints
vim api.py

# Edit analysis logic
vim utils/quirk_analyzer.py

# Both auto-reload during development
```

### Frontend
```bash
cd frontend

# Edit pages
vim pages/index.tsx

# Edit components
vim components/ShowcaseResponse.tsx

# Auto-reloads on save
npm run dev
```

## 📜 License

MIT

## 🙋 Support

- **Setup help**: See [REACT_SETUP.md](REACT_SETUP.md)
- **Technical details**: See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **File organization**: See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 🎉 What's New

**v2.0 - React UI Release**
- ✨ Complete UI rewrite in React/Next.js
- 🎨 Color-coded phrase attribution (new feature!)
- 📊 Interactive visualizations
- ⚡ Faster, more responsive interface
- 🗂️ Streamlit UI deprecated (see `deprecated/streamlit/`)

**CLI Tool Still Available**
```bash
python run_evaluation.py  # Interactive command-line evaluation
```

---

Built with ❤️ using React, FastAPI, and advanced prompt analysis techniques.
