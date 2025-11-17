import { useState } from 'react';
import { Quirk, Section } from '@/lib/types';

interface QuirkTableProps {
  quirks: Quirk[];
  sections: Section[];
  colors: string[];
}

export default function QuirkTable({ quirks, sections, colors }: QuirkTableProps) {
  const [sortBy, setSortBy] = useState<'impact' | 'pValue'>('impact');
  const [showOnlySignificant, setShowOnlySignificant] = useState(false);

  // Filter and sort
  let filteredQuirks = showOnlySignificant
    ? quirks.filter(q => q.p_value < 0.05)
    : quirks;

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
              <th className="text-left py-3 px-4 font-semibold text-gray-800">Quirk</th>
              <th className="text-left py-3 px-4 font-semibold text-gray-800">Section</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">Impact</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">With</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">Without</th>
              <th className="text-right py-3 px-4 font-semibold text-gray-800">p-value</th>
              <th className="text-center py-3 px-4 font-semibold text-gray-800">Sig.</th>
            </tr>
          </thead>
          <tbody>
            {filteredQuirks.map((quirk, idx) => {
              const sectionIdx = quirk.attribution.section_index;
              const color = colors[sectionIdx % colors.length];

              return (
                <tr
                  key={idx}
                  className="border-b border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <td className="py-3 px-4">
                    <div className="font-medium text-gray-800">{quirk.name}</div>
                    <div className="text-xs text-gray-500">{quirk.direction}</div>
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
                    {quirk.full_prompt_rate.toFixed(2)}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {quirk.without_section_rate.toFixed(2)}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-700">
                    {quirk.p_value < 0.001 ? '<0.001' : quirk.p_value.toFixed(3)}
                  </td>
                  <td className="py-3 px-4 text-center">
                    {quirk.p_value < 0.05 ? (
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
