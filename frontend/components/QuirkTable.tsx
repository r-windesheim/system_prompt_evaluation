import React, { useState } from 'react';
import { Quirk, Section } from '@/lib/types';

interface QuirkTableProps {
  quirks: Quirk[];
  sections: Section[];
  colors: string[];
  selectedSections?: Set<string>;
}

export default function QuirkTable({ quirks, sections, colors, selectedSections = new Set() }: QuirkTableProps) {
  const [sortBy, setSortBy] = useState<'impact' | 'pValue'>('impact');
  const [showOnlySignificant, setShowOnlySignificant] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleRow = (index: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedRows(newExpanded);
  };

  // Filter and sort
  let filteredQuirks = quirks;

  // Apply section filter
  if (selectedSections.size > 0) {
    filteredQuirks = filteredQuirks.filter(q => selectedSections.has(q.sectionId));
  }

  // Apply significance filter
  if (showOnlySignificant) {
    filteredQuirks = filteredQuirks.filter(q => q.p_value < 0.05);
  }

  filteredQuirks = [...filteredQuirks].sort((a, b) => {
    if (sortBy === 'impact') {
      return Math.abs(b.impact) - Math.abs(a.impact);
    } else {
      return a.p_value - b.p_value;
    }
  });

  return (
    <div>
      {/* Controls */}
      <div className="flex items-center gap-4 mb-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showOnlySignificant}
            onChange={(e) => setShowOnlySignificant(e.target.checked)}
            className="rounded"
          />
          <span className="text-gray-700">Show only significant (p &lt; 0.05)</span>
        </label>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'impact' | 'pValue')}
          className="text-sm border border-gray-300 rounded px-3 py-1"
        >
          <option value="impact">Sort by Impact</option>
          <option value="pValue">Sort by Significance</option>
        </select>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-gray-300">
              <th className="text-center py-3 px-4 font-semibold text-gray-800 w-12"></th>
              <th className="text-left py-3 px-4 font-semibold text-gray-800">Quirk</th>
              <th className="text-left py-3 px-4 font-semibold text-gray-800">Section</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">Impact</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">
                <div className="flex flex-col items-end">
                  <span>With Section</span>
                  <span className="text-xs font-normal text-gray-500">rate when included</span>
                </div>
              </th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">
                <div className="flex flex-col items-end">
                  <span>Without Section</span>
                  <span className="text-xs font-normal text-gray-500">rate when removed</span>
                </div>
              </th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">p-value</th>
              <th className="text-center py-3 px-4 font-semibold text-gray-800">Sig.</th>
            </tr>
          </thead>
          <tbody>
            {filteredQuirks.map((quirk, idx) => {
              // Find section index from sectionId
              const sectionIdx = sections.findIndex(s => s.id === quirk.sectionId);
              const color = colors[sectionIdx % colors.length];
              const pValue = quirk.p_value || quirk.pValue || 0;
              const isExpanded = expandedRows.has(idx);
              const hasExamples = quirk.example_snippets?.with_full && quirk.example_snippets?.without_section;

              return (
                <React.Fragment key={idx}>
                  <tr
                    className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
                  >
                    <td className="py-3 px-4 text-center">
                      {hasExamples && (
                        <button
                          onClick={() => toggleRow(idx)}
                          className="text-gray-600 hover:text-gray-900 transition-colors p-1 rounded hover:bg-gray-200"
                          aria-label={isExpanded ? "Collapse" : "Expand"}
                        >
                          <svg
                            className={`w-5 h-5 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                            fill="none"
                            strokeWidth="2"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-gray-800">{quirk.name}</div>
                      <div className="text-xs text-gray-500">
                        {quirk.impact > 0 ? 'Increases frequency' : 'Decreases frequency'}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div
                        className="inline-flex items-center gap-2 px-3 py-1 rounded text-white text-xs font-medium"
                        style={{ backgroundColor: color }}
                      >
                        Section {sectionIdx + 1}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span
                        className={`font-semibold ${
                          quirk.impact > 0 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {quirk.impact > 0 ? '+' : ''}
                        {quirk.impact.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-gray-700">
                      {typeof quirk.withSection === 'number' ? quirk.withSection.toFixed(2) : '—'}%
                    </td>
                    <td className="py-3 px-4 text-right text-gray-700">
                      {typeof quirk.withoutSection === 'number' ? quirk.withoutSection.toFixed(2) : '—'}%
                    </td>
                    <td className="py-3 px-4 text-right text-gray-700">
                      {pValue < 0.001 ? '<0.001' : pValue.toFixed(3)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {pValue < 0.05 ? (
                        <span className="inline-block px-2 py-1 bg-green-100 text-green-800 text-xs font-semibold rounded">
                          ✓
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                          —
                        </span>
                      )}
                    </td>
                  </tr>

                  {/* Expandable example row */}
                  {isExpanded && hasExamples && (
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <td colSpan={8} className="py-4 px-4">
                        <div className="grid grid-cols-2 gap-4 max-w-6xl">
                          {/* With Full Prompt */}
                          <div className="bg-white rounded-lg p-4 border-2 border-green-200 shadow-sm">
                            <h4 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-2">
                              <span className="inline-block w-2 h-2 rounded-full bg-green-500"></span>
                              With Full Prompt
                            </h4>
                            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                              {quirk.example_snippets.with_full}
                            </div>
                          </div>

                          {/* Without Section */}
                          <div className="bg-white rounded-lg p-4 border-2 border-red-200 shadow-sm">
                            <h4 className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-2">
                              <span className="inline-block w-2 h-2 rounded-full bg-red-500"></span>
                              Without Section {sectionIdx + 1}
                            </h4>
                            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                              {quirk.example_snippets.without_section}
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>

        {filteredQuirks.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No quirks found with current filters
          </div>
        )}
      </div>
    </div>
  );
}
