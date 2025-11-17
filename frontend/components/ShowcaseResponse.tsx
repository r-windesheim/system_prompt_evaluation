import { useState } from 'react';
import { ShowcaseData, Attribution } from '@/lib/types';

interface ShowcaseResponseProps {
  data: ShowcaseData;
  colors: string[];
}

export default function ShowcaseResponse({ data, colors }: ShowcaseResponseProps) {
  const [hoveredSection, setHoveredSection] = useState<number | null>(null);

  // Sort attributions by start position
  const sortedAttributions = [...data.attributions].sort((a, b) => a.start - b.start);

  // Build segments with attributions
  const segments: Array<{ text: string; attribution?: Attribution }> = [];
  let currentPos = 0;

  sortedAttributions.forEach(attr => {
    // Add plain text before this attribution
    if (attr.start > currentPos) {
      segments.push({
        text: data.response_text.slice(currentPos, attr.start),
      });
    }

    // Add attributed text
    segments.push({
      text: attr.text,
      attribution: attr,
    });

    currentPos = attr.end;
  });

  // Add remaining text
  if (currentPos < data.response_text.length) {
    segments.push({
      text: data.response_text.slice(currentPos),
    });
  }

  const getHighlightStyle = (attr?: Attribution) => {
    if (!attr) return {};

    const isHovered = hoveredSection === attr.section_id;

    return {
      backgroundColor: attr.color + (isHovered ? '40' : '30'),
      color: '#1f2937',
      padding: '2px 4px',
      borderRadius: '4px',
      transition: 'all 0.2s',
      cursor: 'pointer',
      display: 'inline-block',
      transform: isHovered ? 'scale(1.02)' : 'scale(1)',
      boxShadow: isHovered ? `0 2px 8px ${attr.color}40` : 'none',
    };
  };

  return (
    <div className="bg-white border-2 border-gray-200 rounded-xl p-8">
      <div className="text-base leading-relaxed text-gray-800">
        {segments.map((segment, idx) => (
          <span
            key={idx}
            style={getHighlightStyle(segment.attribution)}
            onMouseEnter={() =>
              segment.attribution && setHoveredSection(segment.attribution.section_id)
            }
            onMouseLeave={() => setHoveredSection(null)}
            title={
              segment.attribution
                ? `Section ${segment.attribution.section_id + 1}: ${segment.attribution.quirk_type.replace(/_/g, ' ')}`
                : undefined
            }
          >
            {segment.text}
          </span>
        ))}
      </div>

      {/* Stats */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <div className="text-sm text-gray-600">
          <span className="font-semibold">{data.attributions.length}</span> phrases attributed to{' '}
          <span className="font-semibold">
            {new Set(data.attributions.map(a => a.section_id)).size}
          </span>{' '}
          sections
        </div>
      </div>
    </div>
  );
}
