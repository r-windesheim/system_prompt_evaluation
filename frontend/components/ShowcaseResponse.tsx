import React, { useState } from 'react';
import { Badge } from './Badge';

interface Highlight {
  text: string;
  start: number;
  end: number;
  sectionId: string;
  sectionName: string;
  color: string;
  impact: number;
  pValue: number;
  effectSize: number;
  spikeRatio?: number; // NEW: For visual intensity indicators
}

interface ShowcaseResponseProps {
  response: string;
  highlights: Highlight[];
  sections: Array<{ id: string; name: string; color: string; text?: string }>;
  selectedSections?: Set<string>;
  onSectionToggle?: (sectionId: string) => void;
  onClearFilters?: () => void;
}

const SECTION_COLOR_MAP: Record<string, { bg: string; text: string; border: string }> = {
  blue: {
    bg: 'rgb(239 246 255)',
    text: 'rgb(29 78 216)',
    border: 'rgb(147 197 253)',
  },
  green: {
    bg: 'rgb(236 253 245)',
    text: 'rgb(5 150 105)',
    border: 'rgb(110 231 183)',
  },
  amber: {
    bg: 'rgb(254 243 199)',
    text: 'rgb(180 83 9)',
    border: 'rgb(252 211 77)',
  },
  red: {
    bg: 'rgb(254 242 242)',
    text: 'rgb(185 28 28)',
    border: 'rgb(252 165 165)',
  },
  purple: {
    bg: 'rgb(243 232 255)',
    text: 'rgb(107 33 168)',
    border: 'rgb(196 181 253)',
  },
  teal: {
    bg: 'rgb(240 253 250)',
    text: 'rgb(17 94 89)',
    border: 'rgb(153 246 228)',
  },
};

export const ShowcaseResponse: React.FC<ShowcaseResponseProps> = ({
  response,
  highlights,
  sections,
  selectedSections = new Set(),
  onSectionToggle,
  onClearFilters,
}) => {
  const [hoveredSection, setHoveredSection] = useState<string | null>(null);
  const [hoveredHighlight, setHoveredHighlight] = useState<Highlight | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

  // Filter highlights based on selected sections
  const isFilterActive = selectedSections.size > 0;
  const filteredHighlights = isFilterActive
    ? highlights.filter(h => selectedSections.has(h.sectionId))
    : highlights;

  const handleHighlightHover = (
    highlight: Highlight | null,
    event?: React.MouseEvent
  ) => {
    setHoveredHighlight(highlight);
    if (event && highlight) {
      setTooltipPosition({ x: event.clientX, y: event.clientY });
    }
  };

  // Sort filtered highlights by start position
  const sortedHighlights = [...filteredHighlights].sort((a, b) => a.start - b.start);

  // Build the highlighted text
  const buildHighlightedText = () => {
    const elements: JSX.Element[] = [];
    let lastIndex = 0;

    sortedHighlights.forEach((highlight, idx) => {
      // Add unhighlighted text before this highlight
      if (highlight.start > lastIndex) {
        elements.push(
          <span key={`text-${idx}`}>
            {response.substring(lastIndex, highlight.start)}
          </span>
        );
      }

      // Add highlighted text with unique color and intensity-based styling
      const colors = sectionColorMap[highlight.sectionId];
      const isHovered =
        hoveredSection === highlight.sectionId ||
        hoveredHighlight?.sectionId === highlight.sectionId;

      // Calculate visual intensity based on spike ratio
      const spikeRatio = highlight.spikeRatio || highlight.impact || 1.0;

      // Border thickness: 2px base + 1px per spike ratio unit (cap at 6px)
      const borderWidth = Math.min(2 + Math.floor(spikeRatio * 1), 6);

      // Opacity boost for background: 0.25 base + 0.05 per spike ratio (cap at 0.5)
      const opacityBoost = Math.min(0.25 + (spikeRatio * 0.05), 0.5);

      // Enhanced colors with intensity
      const intensifiedColors = {
        ...colors,
        bg: `hsla(${colors.base.match(/\d+/)?.[0]}, 85%, 55%, ${opacityBoost})`,
        bgHover: `hsla(${colors.base.match(/\d+/)?.[0]}, 85%, 55%, ${Math.min(opacityBoost + 0.15, 0.65)})`,
      };

      // Determine badge emoji based on spike ratio
      let badge = '';
      if (spikeRatio >= 5) {
        badge = '🔥🔥'; // Very high impact
      } else if (spikeRatio >= 3) {
        badge = '🔥'; // High impact
      }

      elements.push(
        <span
          key={`highlight-${idx}`}
          className="inline-block transition-all duration-200 cursor-pointer relative font-medium"
          style={{
            backgroundColor: isHovered ? intensifiedColors.bgHover : intensifiedColors.bg,
            color: 'inherit',
            padding: '2px 10px',
            margin: '0 2px',
            borderRadius: '8px',
            border: `${borderWidth}px solid ${colors.base}`,
            boxShadow: isHovered
              ? `0 2px 8px ${colors.bg}, 0 0 0 2px ${colors.base}30`
              : `0 1px 3px ${colors.bg}`,
            transform: isHovered ? 'translateY(-1px)' : 'translateY(0)',
          }}
          onMouseEnter={(e) => handleHighlightHover(highlight, e)}
          onMouseLeave={() => handleHighlightHover(null)}
        >
          {highlight.text}
          {badge && (
            <span className="ml-1 text-xs" style={{ opacity: 0.8 }}>
              {badge}
            </span>
          )}
        </span>
      );

      lastIndex = highlight.end;
    });

    // Add remaining unhighlighted text
    if (lastIndex < response.length) {
      elements.push(
        <span key="text-end">{response.substring(lastIndex)}</span>
      );
    }

    return elements;
  };

  // Filter sections to only show those with highlights
  const sectionsWithHighlights = sections.filter(section =>
    highlights.some(highlight => highlight.sectionId === section.id)
  );

  // Generate unique colors for sections with highlights (using HSL for better distribution)
  // Returns object with base color and alpha variations
  const generateUniqueColor = (index: number, total: number) => {
    const hue = (index * 360) / total; // Distribute evenly across color wheel
    return {
      base: `hsl(${hue}, 85%, 55%)`, // Base color for borders/legend
      bg: `hsla(${hue}, 85%, 55%, 0.25)`, // Semi-transparent background
      bgHover: `hsla(${hue}, 85%, 55%, 0.4)`, // Slightly more visible on hover
    };
  };

  // Create a map of section ID to unique color
  const sectionColorMap: Record<string, any> = {};
  sectionsWithHighlights.forEach((section, index) => {
    sectionColorMap[section.id] = generateUniqueColor(index, sectionsWithHighlights.length);
  });

  return (
    <div className="space-y-6">
      {/* Legend */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-text-primary">
            Section Legend ({sectionsWithHighlights.length} sections with detected quirks)
          </h3>
          {isFilterActive && onClearFilters && (
            <button
              onClick={onClearFilters}
              className="text-sm text-primary hover:text-accent font-medium underline"
            >
              Clear Filters
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {sectionsWithHighlights.map((section) => {
            const colors = sectionColorMap[section.id];
            const isHovered = hoveredSection === section.id;
            const isSelected = selectedSections.has(section.id);

            // Count how many highlights this section has
            const highlightCount = highlights.filter(h => h.sectionId === section.id).length;

            return (
              <button
                key={section.id}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg border-2 transition-all duration-200 hover:shadow-md relative group"
                style={{
                  borderColor: colors.base,
                  transform: isHovered ? 'scale(1.05)' : 'scale(1)',
                  boxShadow: isHovered ? `0 0 8px ${colors.bg}` : 'none',
                  backgroundColor: isSelected ? colors.bg : 'white',
                  opacity: isFilterActive && !isSelected ? 0.5 : 1,
                }}
                onMouseEnter={() => setHoveredSection(section.id)}
                onMouseLeave={() => setHoveredSection(null)}
                onClick={() => onSectionToggle?.(section.id)}
                title={section.name} // Fallback basic tooltip
              >
                <div
                  className="w-4 h-4 rounded"
                  style={{ backgroundColor: colors.base }}
                />
                <span
                  className="text-sm font-medium text-text-primary"
                >
                  {section.name.split(' ')[0] + ' ' + section.name.split(' ')[1]}
                  {isSelected && ' ✓'}
                </span>
                <span
                  className="text-xs text-text-secondary"
                >
                  ({highlightCount})
                </span>

                {/* Tooltip showing full section text */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 max-w-md whitespace-normal">
                  <div className="font-semibold mb-1">{section.name}</div>
                  <div className="text-gray-300 leading-relaxed">{section.text || section.name}</div>
                  <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1 w-2 h-2 bg-gray-900 rotate-45"></div>
                </div>
              </button>
            );
          })}
        </div>
        {isFilterActive && (
          <p className="text-xs text-text-secondary mt-2">
            Click sections to filter. {selectedSections.size} section{selectedSections.size !== 1 ? 's' : ''} selected.
          </p>
        )}
      </div>

      {/* Response Text */}
      <div className="relative">
        <div className="bg-surface-elevated border-2 border-border rounded-xl p-8 shadow-md">
          <div className="text-base leading-relaxed text-text-primary whitespace-pre-wrap font-normal">
            {buildHighlightedText()}
          </div>
        </div>

        {/* Tooltip */}
        {hoveredHighlight && (
          <div
            className="fixed z-50 bg-text-primary text-white px-4 py-3 rounded-lg shadow-xl max-w-xs animate-scale-in"
            style={{
              left: `${tooltipPosition.x + 10}px`,
              top: `${tooltipPosition.y - 10}px`,
              pointerEvents: 'none',
            }}
          >
            <div className="space-y-1">
              <div className="font-semibold text-sm">
                {hoveredHighlight.sectionName}
              </div>
              <div className="text-xs space-y-0.5 text-white/80">
                {hoveredHighlight.spikeRatio && (
                  <div className="font-bold text-yellow-300 text-base">
                    {hoveredHighlight.spikeRatio.toFixed(1)}× spike ratio
                  </div>
                )}
                <div>Impact: {hoveredHighlight.impact.toFixed(1)}× more frequent</div>
                <div>Effect size: {hoveredHighlight.effectSize.toFixed(2)} std devs</div>
                <div>
                  Significance: p {hoveredHighlight.pValue < 0.001 ? '< 0.001' : `= ${hoveredHighlight.pValue.toFixed(3)}`}
                </div>
              </div>
            </div>
            <div
              className="absolute w-2 h-2 bg-text-primary transform rotate-45"
              style={{
                left: '-4px',
                top: '50%',
                marginTop: '-4px',
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
};
