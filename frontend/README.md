# Quirk Analysis Frontend

Beautiful React UI for analyzing how system prompt sections affect AI behavior.

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Start Backend API

In the parent directory:

```bash
python api.py
```

The API will run on `http://localhost:8000`

### 3. Start Frontend

```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## Usage

1. **Paste Prompt** - Paste your system prompt on the home page
2. **Review Sections** - Edit/enable/disable detected sections
3. **Configure** - Select test query and number of responses
4. **Analyze** - Wait for analysis to complete (~1-5 minutes)
5. **Results** - View color-coded showcase response and detailed quirk table

## Features

- ✨ **Color-coded showcase** - See which prompt sections cause which phrases
- 📊 **Impact gauge** - Visual representation of overall prompt impact
- 📈 **Statistical analysis** - P-values, effect sizes, significance testing
- 🎨 **Beautiful UI** - Modern design with smooth animations
- 💾 **Export results** - Download analysis as JSON

## Tech Stack

- **Framework**: Next.js 14 (Pages Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Recharts
- **API Client**: Fetch API

## Project Structure

```
frontend/
├── pages/
│   ├── index.tsx         # Screen 1: Prompt decomposer
│   ├── configure.tsx     # Screen 2: Configuration
│   └── results.tsx       # Screen 3: Showcase results
├── components/
│   ├── SectionCard.tsx   # Editable section card
│   ├── ImpactGauge.tsx   # Circular impact score gauge
│   ├── ShowcaseResponse.tsx  # Color-coded text display
│   └── QuirkTable.tsx    # Detailed quirk analysis table
├── lib/
│   ├── api.ts            # Backend API client
│   └── types.ts          # TypeScript interfaces
└── styles/
    └── globals.css       # Global styles + Tailwind
```

## Development

### Build for Production

```bash
npm run build
npm run start
```

### Linting

```bash
npm run lint
```

## Environment Variables

None required - API URL is hardcoded to `http://localhost:8000` for development.

For production, update `API_BASE_URL` in `lib/api.ts`.

## License

MIT
