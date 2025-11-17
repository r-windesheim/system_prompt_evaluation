# v0.dev Prompt: AI Prompt Quirk Analyzer

Copy and paste this into https://v0.dev

---

Create a modern web application for analyzing how different sections of AI system prompts affect behavioral quirks in responses. The app should have a clean, professional design with smooth interactions.

## Page Structure

### 1. Header
- App title: "Prompt Quirk Analyzer"
- Subtitle: "Discover how each section of your prompt shapes AI behavior"
- Clean gradient background (purple to indigo)

### 2. Main Content Area (3-step wizard)

#### STEP 1: Input & Decomposition
**Layout:**
- Large textarea for pasting system prompt
- Placeholder text: "Paste your system prompt here..."
- Primary button: "Analyze Prompt" (gradient purple, large, rounded)
- After clicking, show animated loading state
- Display decomposed sections as editable cards:
  - Each card shows section number, title (editable), and text preview
  - Checkbox to include/exclude from analysis
  - All checked by default
  - Edit and delete buttons
- "Continue to Analysis" button at bottom

**Card Design:**
- White background
- Subtle border and shadow
- Rounded corners (12px)
- Hover effect (slight lift)

#### STEP 2: Configuration
**Layout:**
- Show selected sections as colored pills/chips (5 colors: blue, green, orange, red, purple)
- Test query input field
- Dropdown to select from 5 predefined queries:
  - "Should I do this?"
  - "What do you think?"
  - "This seems wrong"
  - "Can you fix it?"
  - "I don't understand"
- Checkbox: "Include semantic quirks"
- Number input: "Number of responses" (default 60)
- "Start Analysis" button (large, gradient)
- Progress indicator when running:
  - Animated progress bar
  - Status text: "Generating 60 responses..." / "Analyzing quirks..." / "Computing statistics..."
  - Percentage counter

#### STEP 3: Results (THE WOW MOMENT)

**Hero Section:**
- Large circular gauge showing Impact Score (0-100)
  - Animated on load
  - Purple gradient ring filling to the score percentage
  - Large number in center
  - "IMPACT SCORE" label below
- One-line summary below gauge:
  - Example: "This section makes responses 2.3× more formal, 1.8× more cautious, and adds 40% more structure"
- 3 stat cards in a row:
  - "18 Quirks Detected"
  - "12 Statistically Significant"
  - "5 Sections Analyzed"
  - Each with gradient background, white text, rounded

**Showcase Response Section:**
- Section title: "🎯 Showcase Response" (large, bold)
- Legend showing the 5 sections:
  - Horizontal row of cards
  - Each with colored square + section name
  - Section 1: Blue (#3b82f6) - "Be direct and concise"
  - Section 2: Green (#10b981) - "Think critically"
  - Section 3: Orange (#f59e0b) - "Use examples"
  - Section 4: Red (#ef4444) - "Acknowledge uncertainty"
  - Section 5: Purple (#8b5cf6) - "Be encouraging"
  - Hover effect: card lifts slightly

- Response container:
  - Large white box with border and shadow
  - Sample response text with inline highlights:
    - Each phrase has colored background matching its section
    - 20% opacity background, darker text color
    - Smooth transitions
    - Example phrases:
      * "I think it's worth considering both sides of this issue." (Section 2: green)
      * "While I'm not entirely certain," (Section 4: red)
      * "here are the key points:" (Section 1: blue)
      * "For example, if you're working with Python," (Section 3: orange)
      * "you could use a dictionary to store the data." (Section 1: blue)
      * "Consider this simple illustration:" (Section 3: orange)
      * "However, there are some trade-offs to consider." (Section 2: green)
      * "It's possible that" (Section 4: red)
      * "performance could be an issue with large datasets." (Section 1: blue)
      * "You're on the right track!" (Section 5: purple)
      * "Keep experimenting and you'll figure it out." (Section 5: purple)

**Interactive Behavior:**
- When hovering over a legend card, the corresponding highlights in the text should:
  - Increase opacity slightly
  - Add a subtle glow/shadow
  - Slightly scale up
- When hovering over a highlight, show a tooltip with:
  - Section name
  - Impact: "1.8× more frequent"
  - Effect size: "0.7 std devs"
  - Significance: "p < 0.01"

**Detailed Analysis Section (Collapsible):**
- "Show Detailed Quirk Analysis" button
- When clicked, expands to show table with:
  - Columns: Quirk Name | Impact | Effect Size | Significance | Section
  - Sortable columns
  - Color-coded significance badges (green = significant, gray = not significant)
  - Alternating row colors for readability

## Design System

**Colors:**
- Primary: Purple gradient (#667eea → #764ba2)
- Section 1 (Blue): Background rgba(59, 130, 246, 0.2), Text #1e40af
- Section 2 (Green): Background rgba(16, 185, 129, 0.2), Text #065f46
- Section 3 (Orange): Background rgba(245, 158, 11, 0.2), Text #92400e
- Section 4 (Red): Background rgba(239, 68, 68, 0.2), Text #991b1b
- Section 5 (Purple): Background rgba(139, 92, 246, 0.2), Text #5b21b6
- Background: Light gray (#f9fafb)
- Text: Dark gray (#1f2937)
- Borders: Light gray (#e5e7eb)

**Typography:**
- Font family: Inter
- Headings: Bold, larger sizes
- Body: Regular, 16px
- Small text: 14px
- Labels: 12px uppercase

**Spacing:**
- Use consistent 8px grid
- Generous padding in containers (32-48px)
- Card padding: 24px
- Button padding: 12px 24px
- Gap between elements: 16-24px

**Components:**
- All buttons: Rounded corners (8-12px)
- Cards: Rounded (12-16px), subtle shadow
- Inputs: Border, rounded, focus state with purple ring
- Smooth transitions on all interactive elements (200ms ease)

**Animations:**
- Fade in on load
- Progress bar fills smoothly
- Gauge animates from 0 to score
- Hover states scale slightly (1.02)
- Loading spinner or skeleton screens during processing

## Mock Data Structure

Use this sample data for the initial build:

```json
{
  "impact_score": 73,
  "summary": "This section makes responses 2.3× more formal, 1.8× more cautious, and adds 40% more structure",
  "stats": {
    "total_quirks": 18,
    "significant_quirks": 12,
    "sections_analyzed": 5
  },
  "sections": [
    { "id": 1, "name": "Be direct and concise", "color": "blue", "text": "Be direct and concise. Avoid unnecessary flattery..." },
    { "id": 2, "name": "Think critically", "color": "green", "text": "Think critically and provide balanced perspectives..." },
    { "id": 3, "name": "Use examples", "color": "orange", "text": "Use examples and analogies to make complex topics..." },
    { "id": 4, "name": "Acknowledge uncertainty", "color": "red", "text": "When uncertain, acknowledge limitations..." },
    { "id": 5, "name": "Be encouraging", "color": "purple", "text": "Be encouraging but realistic about challenges..." }
  ],
  "showcase_response": {
    "text": "Full response text...",
    "highlights": [
      { "text": "I think it's worth considering both sides of this issue.", "section_id": 2, "start": 0, "end": 56 },
      { "text": "While I'm not entirely certain,", "section_id": 4, "start": 57, "end": 88 },
      { "text": "here are the key points:", "section_id": 1, "start": 89, "end": 113 }
    ]
  },
  "detailed_quirks": [
    { "name": "Hedge Rate", "impact": 1.1, "effect_size": 0.7, "p_value": 0.003, "section_id": 4, "section_name": "Acknowledge uncertainty" },
    { "name": "Formality Score", "impact": 6.9, "effect_size": 0.9, "p_value": 0.001, "section_id": 1, "section_name": "Be direct and concise" },
    { "name": "Example Rate", "impact": 2.3, "effect_size": 1.2, "p_value": 0.0001, "section_id": 3, "section_name": "Use examples" }
  ]
}
```

## Requirements

- Use TypeScript and React
- Use Tailwind CSS for styling
- Use shadcn/ui components where applicable
- Make it responsive (desktop first, but works on tablet)
- Add smooth page transitions between steps
- Include loading states and error handling
- Use Recharts or similar for the circular gauge
- Make the code clean and well-organized

## Additional Features

- "Export Results" button (downloads JSON)
- "Share Analysis" button (copies link)
- Dark mode toggle (optional but nice to have)
- Keyboard navigation support
- Accessible (ARIA labels, focus states)

Create a beautiful, polished, production-ready interface that feels like a modern SaaS product. The wow factor should come from the showcase response section with the color-coded highlights.
