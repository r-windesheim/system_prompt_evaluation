# Prompt Analyzer Frontend

Modern, beautiful UI for analyzing AI system prompts and understanding behavioral quirks.

## Features

- 🎨 **Modern Design**: Clean, professional interface with smooth animations
- 🎯 **Color-Coded Attribution**: See which prompt sections cause which phrases
- 📊 **Statistical Rigor**: P-values, effect sizes, and confidence intervals
- 🚀 **Fast & Responsive**: Built with Next.js and optimized for performance
- 📱 **Mobile Friendly**: Responsive design that works on all devices

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python backend running (see root README)

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.local.example .env.local

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build for Production

```bash
# Create optimized production build
npm run build

# Start production server
npm start
```

## Project Structure

```
frontend/
├── components/          # Reusable React components
│   ├── Badge.tsx       # Status badges
│   ├── Button.tsx      # Button component
│   ├── Card.tsx        # Card container
│   ├── ImpactGauge.tsx # Circular progress gauge
│   ├── Input.tsx       # Form inputs
│   ├── Layout.tsx      # Page layout wrapper
│   ├── ProgressBar.tsx # Progress indicator
│   └── ShowcaseResponse.tsx # Color-coded response display
├── pages/              # Next.js pages (routes)
│   ├── _app.tsx        # App wrapper
│   ├── index.tsx       # Landing page
│   ├── analyze.tsx     # Analysis workflow
│   └── results.tsx     # Results display
├── lib/                # Utilities and API
│   ├── api.ts          # Backend API client
│   └── types.ts        # TypeScript types
├── styles/             # Global styles
│   └── globals.css     # CSS variables and utilities
└── public/             # Static assets
```

## Design System

### Colors

- **Primary**: Purple gradient (brand)
- **Secondary**: Blue (trust, reliability)
- **Accent**: Pink (highlights, CTAs)
- **Success**: Green (positive outcomes)
- **Warning**: Orange (caution)
- **Error**: Red (errors, decreases)

### Section Attribution Colors

Each prompt section is assigned a distinct color for visual attribution:

1. Blue - Direct communication
2. Green - Critical thinking
3. Amber - Examples and analogies
4. Red - Uncertainty acknowledgment
5. Purple - Encouragement
6. Teal - Additional sections

### Typography

- **Font**: Inter (clean, modern)
- **Headings**: Bold, clear hierarchy
- **Body**: Regular, comfortable reading
- **Code**: Monospace for data

### Spacing

- Based on 8px grid system
- Consistent padding and margins
- Generous whitespace for clarity

## Key Components

### ShowcaseResponse

The centerpiece component that displays color-coded text with interactive highlights.

```tsx
<ShowcaseResponse
  response="Full response text..."
  highlights={[...]}
  sections={[...]}
/>
```

### ImpactGauge

Animated circular gauge showing overall impact score.

```tsx
<ImpactGauge score={73} />
```

### Button

Versatile button with variants and sizes.

```tsx
<Button variant="primary" size="lg">
  Start Analysis
</Button>
```

## API Integration

The frontend communicates with the Python backend via REST API:

- `POST /api/decompose` - Decompose prompt into sections
- `POST /api/analyze` - Start analysis
- `GET /api/analyze/:id` - Check analysis status
- `GET /api/results/:id` - Fetch results

See `lib/api.ts` for full API client implementation.

## Development

### Adding New Components

1. Create component in `components/` directory
2. Export from component file
3. Import where needed

### Adding New Pages

1. Create file in `pages/` directory
2. Export default React component
3. Next.js automatically creates route

### Styling

- Use Tailwind CSS utility classes
- Custom colors via CSS variables
- Responsive with `sm:`, `md:`, `lg:` prefixes

## Deployment

### Vercel (Recommended)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### Docker

```bash
# Build image
docker build -t prompt-analyzer-frontend .

# Run container
docker run -p 3000:3000 prompt-analyzer-frontend
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## Performance

- **First Paint**: < 1s
- **Interactive**: < 2s
- **Bundle Size**: < 500KB
- **Lighthouse Score**: 95+

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test thoroughly
5. Submit pull request

## License

MIT

## Support

For issues or questions:
- Open GitHub issue
- Check documentation
- Contact support

---

Built with ❤️ using Next.js, TypeScript, and Tailwind CSS
