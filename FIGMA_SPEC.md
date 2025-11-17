# Figma Design Specification: Quirk Analysis Feature

## Overview
Design a 3-screen flow for analyzing how system prompt sections affect AI behavior, culminating in a color-coded response visualization.

---

## Screen 1: Prompt Decomposition

### Layout
```
┌─────────────────────────────────────────┐
│  Quirk Analysis Tool                    │
├─────────────────────────────────────────┤
│                                         │
│  Paste Your System Prompt:              │
│  ┌───────────────────────────────────┐  │
│  │                                   │  │
│  │  [Large textarea, 400px height]   │  │
│  │                                   │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [Decompose Prompt] button              │
│                                         │
│  ─────────────────────────────────────  │
│                                         │
│  Detected Sections:                     │
│  ┌───────────────────────────────────┐  │
│  │ □ Section 1: Be direct           │  │
│  │   "Be direct and concise..."      │  │
│  │   [Edit] [Remove]                 │  │
│  ├───────────────────────────────────┤  │
│  │ □ Section 2: Think critically    │  │
│  │   "Consider multiple..."          │  │
│  │   [Edit] [Remove]                 │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [Continue to Analysis] button          │
│                                         │
└─────────────────────────────────────────┘
```

### Components Needed
- **Text input**: Large textarea (rounded corners, subtle border)
- **Primary button**: "Decompose Prompt" (gradient purple, large)
- **Section cards**:
  - Checkbox (enabled by default)
  - Section name (editable inline)
  - Section text (truncated, expandable)
  - Edit/Remove actions
- **Secondary button**: "Continue to Analysis"

### Colors
- Background: Light gray (#F9FAFB)
- Cards: White with subtle shadow
- Primary button: Purple gradient (#667eea → #764ba2)
- Text: Dark gray (#1F2937)

---

## Screen 2: Quirk Analysis Configuration

### Layout
```
┌─────────────────────────────────────────┐
│  Configure Analysis                     │
├─────────────────────────────────────────┤
│                                         │
│  Selected Sections (5):                 │
│  [Section 1] [Section 2] [Section 3]    │
│  [Section 4] [Section 5]                │
│                                         │
│  Test Query:                            │
│  ┌───────────────────────────────────┐  │
│  │ Should I do this?                 │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Options:                               │
│  ☑ Include semantic quirks              │
│  ☑ Color-code showcase response         │
│                                         │
│  [Start Analysis] button                │
│                                         │
│  ─────────────────────────────────────  │
│                                         │
│  Analysis Progress:                     │
│  ████████████░░░░░░░░ 60%               │
│  Generating 60 responses...             │
│                                         │
└─────────────────────────────────────────┘
```

### Components Needed
- **Chip/Tag**: Selected sections (small rounded pills with X to remove)
- **Text input**: Test query (single line, medium height)
- **Checkboxes**: Options
- **Progress bar**: Animated, gradient fill
- **Status text**: Dynamic (changes during analysis)

---

## Screen 3: Showcase Results ⭐

### Layout (Main Hero)
```
┌────────────────────────────────────────────────────┐
│                                                    │
│              ┌──────────────┐                      │
│              │      73      │  ← Circular gauge    │
│              │   Impact     │                      │
│              └──────────────┘                      │
│                                                    │
│  This section makes responses 2.3× more formal,   │
│  1.8× more cautious, and adds 40% more structure  │
│                                                    │
│  [18 Quirks] [12 Significant] [5 Sections]        │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Layout (Showcase Response)
```
┌────────────────────────────────────────────────────┐
│  🎯 Showcase Response                              │
├────────────────────────────────────────────────────┤
│                                                    │
│  Legend:                                           │
│  [■ Section 1] [■ Section 2] [■ Section 3]        │
│  [■ Section 4] [■ Section 5]                       │
│                                                    │
│  ┌──────────────────────────────────────────────┐ │
│  │                                              │ │
│  │  I think it's worth considering both sides  │ │
│  │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔   │ │
│  │  (green background = Section 2)              │ │
│  │                                              │ │
│  │  While I'm not entirely certain, here are   │ │
│  │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔            │ │
│  │  (red bg = Sec 4)  (blue bg = Sec 1)        │ │
│  │  the key points:                             │ │
│  │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔                             │ │
│  │                                              │ │
│  │  For example, if you're working with Python,│ │
│  │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔  │ │
│  │  (orange background = Section 3)             │ │
│  │                                              │ │
│  │  You're on the right track!                 │ │
│  │  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔                 │ │
│  │  (purple background = Section 5)             │ │
│  │                                              │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  [Show Detailed Analysis] button                   │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Color Scheme for Highlights
- **Section 1 (Blue)**: `rgba(59, 130, 246, 0.2)` with `#1e40af` text
- **Section 2 (Green)**: `rgba(16, 185, 129, 0.2)` with `#065f46` text
- **Section 3 (Orange)**: `rgba(245, 158, 11, 0.2)` with `#92400e` text
- **Section 4 (Red)**: `rgba(239, 68, 68, 0.2)` with `#991b1b` text
- **Section 5 (Purple)**: `rgba(139, 92, 246, 0.2)` with `#5b21b6` text

### Interactive Behaviors
1. **Hover on legend item** → corresponding highlights pulse/brighten
2. **Click legend item** → scroll to first occurrence in response
3. **Hover on highlight** → show tooltip with section name + impact stats
4. **Click "Show Detailed Analysis"** → expand drawer with full quirk list

---

## Typography

### Font Recommendations
- **Headings**: Inter Bold (or SF Pro Display on Mac)
- **Body**: Inter Regular
- **Code/Data**: JetBrains Mono

### Sizes
- H1 (Screen title): 28px, bold
- H2 (Section title): 20px, semibold
- Body: 16px, regular
- Small: 14px, regular
- Tiny: 12px, regular

---

## Spacing System
Use **8px grid**:
- xs: 8px
- sm: 16px
- md: 24px
- lg: 32px
- xl: 48px

---

## Component Specifications

### Impact Score Circle
- **Size**: 180px × 180px
- **Ring**: 8px thick, conic gradient (purple) showing percentage
- **Inner circle**: White background
- **Number**: 48px, bold, gradient text
- **Label**: 12px, uppercase, gray

### Legend Item
- **Padding**: 8px 16px
- **Background**: White
- **Border-radius**: 12px
- **Color square**: 24px × 24px, rounded 6px
- **Shadow**: Subtle on hover

### Highlight Span
- **Padding**: 2px 4px
- **Border-radius**: 4px
- **Background**: Semi-transparent color
- **Text color**: Darker shade of background color
- **Transition**: 200ms ease on hover
- **Hover**: Scale 1.02, stronger shadow

---

## Design Principles

1. **Progressive Disclosure**: Start simple, reveal complexity on demand
2. **Visual Hierarchy**: Impact score is largest, details are collapsible
3. **Color as Information**: Colors meaningfully encode section attribution
4. **Responsive**: Works on desktop (primary) and tablet (secondary)
5. **Accessibility**:
   - Color is not the only indicator (also show section numbers)
   - High contrast ratios (WCAG AA minimum)
   - Keyboard navigable

---

## Data Format

### Example JSON structure for color-coded response:
```json
{
  "response_text": "Full response string...",
  "attributions": [
    {
      "text": "I think it's worth considering both sides",
      "start_idx": 0,
      "end_idx": 42,
      "section_id": 2,
      "section_name": "Think critically",
      "confidence": 0.87,
      "spike_ratio": 2.3
    },
    {
      "text": "While I'm not entirely certain",
      "start_idx": 43,
      "end_idx": 73,
      "section_id": 4,
      "section_name": "Acknowledge uncertainty",
      "confidence": 0.93,
      "spike_ratio": 4.1
    }
  ]
}
```

---

## Technical Implementation Notes

### For Streamlit
- Use `st.markdown()` with custom HTML/CSS for highlights
- `st.components.v1.html()` for interactive JavaScript parts
- Store color mappings in session state

### For React
- Use `react-highlight-words` or custom span wrapper
- Framer Motion for animations
- Recharts or D3 for impact gauge

---

## Next Steps

1. **Create Figma file** with these 3 screens
2. **Design variations** for different states:
   - Empty state (no analysis yet)
   - Loading state (progress bar)
   - Success state (full results)
   - Error state (API failure)
3. **Add micro-interactions**:
   - Hover states
   - Transition animations
   - Tooltip designs
4. **Export specs** for development

---

## Questions to Answer in Design

1. What happens if 20+ sections are detected?
2. How to handle overlapping attributions (multiple sections cause same phrase)?
3. Mobile responsiveness strategy?
4. Dark mode support?
5. Export/share functionality?
