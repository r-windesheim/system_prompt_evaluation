import React, { useState } from 'react';
import { Card } from './Card';
import { Badge } from './Badge';

interface BeforeAfterSliderProps {
  fullPromptResponse: string;
  leaveOneOutResponses: Record<string, string[]>; // Map of config_name -> responses
  sections: Array<{ id: string; title: string; text: string }>;
  quirks: Array<{
    name: string;
    impact: number;
    sectionId: string;
    spikeRatio?: number;
    spike_ratio?: number;
  }>;
}

export const BeforeAfterSlider: React.FC<BeforeAfterSliderProps> = ({
  fullPromptResponse,
  leaveOneOutResponses,
  sections,
  quirks,
}) => {
  const [mode, setMode] = useState<'full' | 'without'>('full');
  const [selectedSection, setSelectedSection] = useState<string>(sections[0]?.id || '0');

  // Get the response for the selected leave-one-out config
  const getLeaveOneOutResponse = () => {
    const sectionIdx = sections.findIndex(s => s.id === selectedSection);
    const configKey = `without_${sectionIdx}`;  // FIX: Use correct format
    const responses = leaveOneOutResponses[configKey];
    return responses && responses.length > 0 ? responses[0] : 'No response available';
  };

  // Get quirks for the selected section
  const getSectionQuirks = () => {
    return quirks.filter(q => q.sectionId === selectedSection);
  };

  const currentResponse = mode === 'full' ? fullPromptResponse : getLeaveOneOutResponse();
  const sectionQuirks = getSectionQuirks();

  // Get the selected section details
  const currentSection = sections.find(s => s.id === selectedSection);

  // Separate increases and decreases
  const increases = sectionQuirks.filter(q => q.impact > 0);
  const decreases = sectionQuirks.filter(q => q.impact < 0);

  return (
    <Card padding="lg">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center space-x-3 mb-3">
            <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
            </svg>
            <h2 className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Before & After Comparison
            </h2>
          </div>
          <p className="text-sm text-text-secondary">
            Compare responses with the full prompt vs. without specific sections
          </p>
        </div>

        {/* Toggle Controls */}
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Mode Toggle */}
          <div className="flex-1">
            <label className="text-xs font-medium text-text-secondary mb-2 block">
              View Mode
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode('full')}
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === 'full'
                    ? 'bg-gradient-to-r from-primary to-accent text-white shadow-md'
                    : 'bg-surface border border-border text-text-secondary hover:bg-surface-elevated'
                }`}
              >
                With Full Prompt
              </button>
              <button
                onClick={() => setMode('without')}
                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === 'without'
                    ? 'bg-gradient-to-r from-primary to-accent text-white shadow-md'
                    : 'bg-surface border border-border text-text-secondary hover:bg-surface-elevated'
                }`}
              >
                Without Section...
              </button>
            </div>
          </div>

          {/* Section Selector (only visible in 'without' mode) */}
          {mode === 'without' && (
            <div className="flex-1">
              <label className="text-xs font-medium text-text-secondary mb-2 block">
                Remove Section
              </label>
              <select
                value={selectedSection}
                onChange={(e) => setSelectedSection(e.target.value)}
                className="w-full px-4 py-2 rounded-lg border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {sections.map((section) => (
                  <option key={section.id} value={section.id}>
                    Section {parseInt(section.id) + 1}: {section.title.substring(0, 40)}...
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Info Banner */}
        <div className={`p-4 rounded-lg border-2 ${
          mode === 'full'
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-start space-x-3">
            <div className={`mt-0.5 ${mode === 'full' ? 'text-green-600' : 'text-red-600'}`}>
              {mode === 'full' ? (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 9.586 8.707 8.293z" clipRule="evenodd" />
                </svg>
              )}
            </div>
            <div className="flex-1">
              <h4 className={`text-sm font-semibold mb-1 ${
                mode === 'full' ? 'text-green-800' : 'text-red-800'
              }`}>
                {mode === 'full'
                  ? 'Full Prompt Response'
                  : `Without: "${currentSection?.title || `Section ${parseInt(selectedSection) + 1}`}"`
                }
              </h4>
              <p className={`text-xs ${
                mode === 'full' ? 'text-green-700' : 'text-red-700'
              }`}>
                {mode === 'full'
                  ? `Showing behaviors that INCREASE with sections (${increases.length} increases)`
                  : `Showing behaviors that INCREASE when section is removed (${decreases.length} decreases from that section)`
                }
              </p>
              {mode === 'without' && currentSection && (
                <p className="text-xs text-red-600 mt-2 italic border-t border-red-200 pt-2">
                  Removed section: "{currentSection.text.substring(0, 150)}{currentSection.text.length > 150 ? '...' : ''}"
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Response Display */}
        <div className="bg-surface-elevated border-2 border-border rounded-xl p-8 shadow-md">
          <div className="text-base leading-relaxed text-text-primary whitespace-pre-wrap font-normal">
            {currentResponse}
          </div>
        </div>

        {/* Stats Summary */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-green-600 mb-1">
              {increases.length}
            </div>
            <div className="text-xs text-green-700 uppercase tracking-wider">
              Behaviors Increased
            </div>
            {increases.length > 0 && (
              <div className="mt-2 space-y-1">
                {increases.slice(0, 3).map((q, idx) => (
                  <div key={idx} className="text-xs text-green-600">
                    • {q.name}: +{q.impact.toFixed(1)}
                  </div>
                ))}
                {increases.length > 3 && (
                  <div className="text-xs text-green-500">
                    +{increases.length - 3} more...
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="text-2xl font-bold text-red-600 mb-1">
              {decreases.length}
            </div>
            <div className="text-xs text-red-700 uppercase tracking-wider">
              Behaviors Decreased
            </div>
            {decreases.length > 0 && (
              <div className="mt-2 space-y-1">
                {decreases.slice(0, 3).map((q, idx) => (
                  <div key={idx} className="text-xs text-red-600">
                    • {q.name}: {q.impact.toFixed(1)}
                  </div>
                ))}
                {decreases.length > 3 && (
                  <div className="text-xs text-red-500">
                    +{decreases.length - 3} more...
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};
