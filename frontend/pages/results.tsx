import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import dynamic from 'next/dynamic';
import { Section, AnalysisResult, Highlight } from '@/lib/types';
import { Layout } from '@/components/Layout';
import { ImpactGauge } from '@/components/ImpactGauge';
import { ShowcaseResponse } from '@/components/ShowcaseResponse';
import QuirkTable from '@/components/QuirkTable';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { IntensitySlider, DirectionFilter } from '@/components/IntensitySlider';
import { BeforeAfterSlider } from '@/components/BeforeAfterSlider';

// Dynamically import NetworkGraph to avoid SSR issues with canvas/WebGL
const NetworkGraph = dynamic(
  () => import('@/components/NetworkGraph').then((mod) => ({ default: mod.NetworkGraph })),
  {
    ssr: false,
    loading: () => (
      <Card padding="lg">
        <div className="text-center text-text-secondary py-8">
          Loading network graph...
        </div>
      </Card>
    ),
  }
);

export default function Results() {
  const router = useRouter();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSections, setSelectedSections] = useState<Set<string>>(new Set());
  const [intensityThreshold, setIntensityThreshold] = useState<number>(1.0); // 1.0 = shows both 2x increases and 0.5x decreases
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>('increases');
  const [selectedLeaveOneOutSection, setSelectedLeaveOneOutSection] = useState<string>('0');

  useEffect(() => {
    loadResults();
  }, []);

  const loadResults = async () => {
    try {
      // Load from sessionStorage
      const storedResult = sessionStorage.getItem('analysisResult');
      const storedSections = sessionStorage.getItem('sections');

      if (!storedResult || !storedSections) {
        router.push('/analyze');
        return;
      }

      const parsedResult: AnalysisResult = JSON.parse(storedResult);
      const parsedSections: Section[] = JSON.parse(storedSections);

      // Map old data format to new format if needed
      if (parsedResult.quirks && parsedResult.quirks.length > 0) {
        parsedResult.quirks = parsedResult.quirks.map((quirk: any) => {
          // If withSection/withoutSection are missing, try to map from attribution or other fields
          if (typeof quirk.withSection !== 'number' && quirk.attribution) {
            quirk.withSection = quirk.attribution.with_section || 0;
          }
          if (typeof quirk.withoutSection !== 'number' && quirk.attribution) {
            quirk.withoutSection = quirk.attribution.without_section || 0;
          }
          // Ensure spikeRatio is set
          if (!quirk.spikeRatio && quirk.spike_ratio) {
            quirk.spikeRatio = quirk.spike_ratio;
          }
          // Ensure sectionId is set
          if (!quirk.sectionId && quirk.attribution?.section_index !== undefined) {
            quirk.sectionId = quirk.attribution.section_index.toString();
          }
          return quirk;
        });
      }

      setResult(parsedResult);
      setSections(parsedSections);
      setLoading(false);
    } catch (err: any) {
      console.error('Failed to load results:', err);
      setLoading(false);
    }
  };

  // Get showcase data from API results or generate fallback
  const generateShowcaseData = () => {
    if (!result || !sections.length) return null;

    // Use real showcase data from API if available
    if (result.showcase && result.showcase.response_text && result.showcase.attributions) {
      return {
        text: result.showcase.response_text,
        highlights: result.showcase.attributions
      };
    }

    // Fallback to mock data if showcase not available (backwards compatibility)
    const exampleResponse = `I think it's important to provide a thoughtful analysis here. Based on my understanding, there are several key factors to consider. For example, when working with data structures in Python, you might want to use a dictionary for efficient key-value lookups. However, it's worth noting that there are trade-offs between different approaches. I'm not entirely certain about all the edge cases, but the general principle should apply. You're definitely on the right track with this approach!`;

    const highlights: Highlight[] = [
      { text: "I think it's important to provide a thoughtful analysis here.", start: 0, end: 61, sectionId: sections[0]?.id || '0', sectionName: sections[0]?.title || 'Section 1', color: 'blue', impact: 8.5, pValue: 0.02, effectSize: 0.65 },
      { text: "For example, when working with data structures in Python, you might want to use a dictionary for efficient key-value lookups.", start: 124, end: 251, sectionId: sections[3]?.id || '3', sectionName: sections[3]?.title || 'Section 4', color: 'red', impact: 7.02, pValue: 0.06, effectSize: 0.54 },
      { text: "I'm not entirely certain about all the edge cases", start: 331, end: 381, sectionId: sections[2]?.id || '2', sectionName: sections[2]?.title || 'Section 3', color: 'amber', impact: 5.36, pValue: 0.009, effectSize: 0.48 },
      { text: "You're definitely on the right track with this approach!", start: 422, end: 478, sectionId: sections[4]?.id || '4', sectionName: sections[4]?.title || 'Section 5', color: 'purple', impact: 9.08, pValue: 0.07, effectSize: 0.71 },
    ];

    return { text: exampleResponse, highlights };
  };

  const calculateImpactScore = () => {
    if (!result || result.quirks.length === 0) return 0;
    const avgImpact = result.quirks.reduce((sum, q) => sum + Math.abs(q.impact), 0) / result.quirks.length;
    return Math.min(Math.round((avgImpact / 20) * 100), 100);
  };
  
  const getPValue = (quirk: any) => quirk.p_value ?? quirk.pValue ?? 1;

  const SECTION_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16',
  ];

  // Toggle section selection for filtering
  const toggleSectionFilter = (sectionId: string) => {
    const newSelected = new Set(selectedSections);
    if (newSelected.has(sectionId)) {
      newSelected.delete(sectionId);
    } else {
      newSelected.add(sectionId);
    }
    setSelectedSections(newSelected);
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedSections(new Set());
  };

  if (loading) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto text-center py-12">
          <Card>
            <div className="text-lg text-text-secondary">Loading results...</div>
          </Card>
        </div>
      </Layout>
    );
  }

  if (!result) {
    return (
      <Layout>
        <div className="max-w-6xl mx-auto py-12">
          <Card>
            <div className="text-error mb-4">No results found</div>
            <Button onClick={() => router.push('/analyze')}>
              Start New Analysis
            </Button>
          </Card>
        </div>
      </Layout>
    );
  }

  const impactScore = calculateImpactScore();
  const significantQuirks = result.quirks.filter(q => getPValue(q) < 0.05).length;
  const showcaseDataRaw = generateShowcaseData();

  // Get the appropriate response text based on direction filter
  const getDisplayResponse = () => {
    // For decreases mode, show the leave-one-out response
    if (directionFilter === 'decreases' && result.leave_one_out_responses) {
      const sectionIdx = parseInt(selectedLeaveOneOutSection);
      const configKey = `without_${sectionIdx}`;
      const responses = result.leave_one_out_responses[configKey];

      console.log('=== GET DISPLAY RESPONSE (DECREASES) ===');
      console.log('Selected section:', selectedLeaveOneOutSection);
      console.log('Config key:', configKey);
      console.log('Available configs:', Object.keys(result.leave_one_out_responses));
      console.log('Found responses:', responses ? responses.length : 0);

      if (responses && responses.length > 0) {
        console.log('Returning leave-one-out response, length:', responses[0].length);
        console.log('First 100 chars:', responses[0].substring(0, 100));
        return responses[0];
      }
    }

    // Otherwise show the full response
    const fullResponse = showcaseDataRaw?.text || '';
    console.log('=== GET DISPLAY RESPONSE (INCREASES) ===');
    console.log('Returning full response, length:', fullResponse.length);
    console.log('First 100 chars:', fullResponse.substring(0, 100));
    return fullResponse;
  };

  // Helper function to convert spike ratio to "significance"
  // For increases (>=1.0): use ratio as-is
  // For decreases (<1.0): convert to equivalent increase (1/ratio)
  // Example: 0.5x decrease = 2x significance, 0.33x decrease = 3x significance
  const getSignificance = (ratio: number): number => {
    if (ratio >= 1.0) return ratio;
    if (ratio > 0) return 1 / ratio;
    return 1.0; // Fallback
  };

  // Apply intensity filter and direction filter to showcase highlights
  const showcaseData = showcaseDataRaw && (() => {
    // For decreases mode, use the leave-one-out showcase if available
    if (directionFilter === 'decreases') {
      console.log('=== DECREASES MODE DEBUG ===');
      console.log('Has leave_one_out_showcases?', !!result.leave_one_out_showcases);

      if (result.leave_one_out_showcases) {
        console.log('Available showcase configs:', Object.keys(result.leave_one_out_showcases));

        const sectionIdx = parseInt(selectedLeaveOneOutSection);
        const configKey = `without_${sectionIdx}`;
        console.log('Looking for config:', configKey);

        const looShowcase = result.leave_one_out_showcases[configKey];
        console.log('Found showcase?', !!looShowcase);

        if (looShowcase) {
          console.log('Response text length:', looShowcase.response_text.length);
          console.log('First 200 chars:', looShowcase.response_text.substring(0, 200));
          console.log('Attributions count:', looShowcase.attributions.length);

          // COMPARE to full response
          console.log('--- COMPARISON ---');
          console.log('Full response length:', showcaseDataRaw.text.length);
          console.log('Full first 200:', showcaseDataRaw.text.substring(0, 200));
          console.log('Are they the same?', looShowcase.response_text === showcaseDataRaw.text);

          // Filter highlights by intensity threshold
          const filtered = looShowcase.attributions.filter(h => {
            const ratio = h.spikeRatio || Math.abs(h.impact) || 1.0;
            return getSignificance(ratio) >= intensityThreshold;
          });

          return {
            text: looShowcase.response_text,
            highlights: filtered,
          };
        }
      }

      // Fallback: show leave-one-out response without highlights
      console.log('Fallback: Using getDisplayResponse()');
      return {
        text: getDisplayResponse(),
        highlights: [],
      };
    }

    // For increases mode, filter highlights from the full response
    console.log('=== INCREASES MODE ===');
    console.log('Full response length:', showcaseDataRaw.text.length);

    const filtered = showcaseDataRaw.highlights.filter(h => {
      const ratio = h.spikeRatio || Math.abs(h.impact) || 1.0;
      if (getSignificance(ratio) < intensityThreshold) return false;

      // Only show increases
      if (h.impact <= 0) return false;

      return true;
    });

    return {
      text: showcaseDataRaw.text,
      highlights: filtered,
    };
  })();

  const filteredQuirks = result.quirks.filter(q => {
    const ratio = q.spikeRatio || q.spike_ratio || Math.abs(q.impact) || 1.0;
    const significance = getSignificance(ratio);

    // Apply intensity threshold
    if (significance < intensityThreshold) return false;

    // Apply direction filter
    const isIncrease = q.impact > 0;
    if (directionFilter === 'increases' && !isIncrease) return false;
    if (directionFilter === 'decreases' && isIncrease) return false;

    return true;
  });

  // Calculate counts for each direction
  const increasesFiltered = result.quirks.filter(q => {
    const ratio = q.spikeRatio || q.spike_ratio || Math.abs(q.impact) || 1.0;
    return q.impact > 0 && getSignificance(ratio) >= intensityThreshold;
  });
  const decreasesFiltered = result.quirks.filter(q => {
    const ratio = q.spikeRatio || q.spike_ratio || Math.abs(q.impact) || 1.0;
    return q.impact <= 0 && getSignificance(ratio) >= intensityThreshold;
  });

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-in">
        {/* Hero Section - Impact Score */}
        <Card padding="md">
          <div className="flex flex-col md:flex-row items-center md:items-start gap-6">
            {/* Impact Gauge - Left Side */}
            <div className="flex-shrink-0">
              <ImpactGauge score={impactScore} size={140} />
            </div>
            
            {/* Summary and Stats - Right Side */}
            <div className="flex-1 flex flex-col space-y-4">
              <div>
                <h1 className="text-2xl font-bold text-text-primary mb-2">
                  Analysis Complete
                </h1>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {result.auto_summary || `Analysis complete! Detected ${result.total_quirks_detected} behavioral quirks across ${sections.length} sections.`}
                </p>
              </div>

              {/* Stats Grid - Compact */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gradient-to-br from-primary to-accent text-white p-4 rounded-lg shadow-md">
                  <div className="text-3xl font-bold mb-1">{result.total_quirks_detected}</div>
                  <div className="text-xs opacity-90 uppercase tracking-wider">Quirks</div>
                </div>
                <div className="bg-gradient-to-br from-success to-success/80 text-white p-4 rounded-lg shadow-md">
                  <div className="text-3xl font-bold mb-1">{significantQuirks}</div>
                  <div className="text-xs opacity-90 uppercase tracking-wider">Significant</div>
                </div>
                <div className="bg-gradient-to-br from-secondary to-secondary/80 text-white p-4 rounded-lg shadow-md">
                  <div className="text-3xl font-bold mb-1">{sections.length}</div>
                  <div className="text-xs opacity-90 uppercase tracking-wider">Sections</div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Intensity Slider */}
        <IntensitySlider
          threshold={intensityThreshold}
          onThresholdChange={setIntensityThreshold}
          visibleCount={filteredQuirks.length}
          totalCount={result.total_quirks_detected}
          direction={directionFilter}
          onDirectionChange={setDirectionFilter}
          increaseCount={increasesFiltered.length}
          decreaseCount={decreasesFiltered.length}
        />

        {/* Section Selector for Decreases Mode */}
        {directionFilter === 'decreases' && (
          <Card padding="md">
            {!result.leave_one_out_responses ? (
              <div className="flex items-center gap-3 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <svg className="w-5 h-5 text-yellow-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <p className="text-sm font-semibold text-yellow-800">Leave-one-out responses not available</p>
                  <p className="text-xs text-yellow-700">This analysis was run without leave-one-out data. Run a new analysis to enable decrease viewing.</p>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <div className="flex-shrink-0">
                  <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6" />
                  </svg>
                </div>
                <div className="flex-1">
                  <label className="text-sm font-semibold text-text-primary mb-2 block">
                    Viewing responses WITHOUT which section?
                  </label>
                  <p className="text-xs text-text-secondary mb-3">
                    Select a section to view responses generated without it (showing behaviors that increase when removed)
                  </p>
                  <select
                    value={selectedLeaveOneOutSection}
                    onChange={(e) => setSelectedLeaveOneOutSection(e.target.value)}
                    className="w-full px-4 py-2 rounded-lg border border-border bg-surface text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    {sections.map((section) => (
                      <option key={section.id} value={section.id}>
                        Section {parseInt(section.id) + 1}: {section.title.substring(0, 60)}...
                      </option>
                    ))}
                  </select>
                  <div className="mt-2 text-xs text-text-secondary">
                    Available configs: {result.leave_one_out_responses ? Object.keys(result.leave_one_out_responses).join(', ') : 'None'}
                  </div>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Showcase Response with Sentence Attribution - MAIN FEATURE */}
        {showcaseData && (
          <Card padding="lg">
            {/* Response Mode Indicator */}
            {directionFilter !== 'both' && (
              <div className={`mb-4 p-4 rounded-lg border-2 ${
                directionFilter === 'increases'
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center space-x-3">
                  <div className={directionFilter === 'increases' ? 'text-green-600' : 'text-red-600'}>
                    {directionFilter === 'increases' ? (
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M3.293 9.707a1 1 0 010-1.414l6-6a1 1 0 011.414 0l6 6a1 1 0 01-1.414 1.414L11 5.414V17a1 1 0 11-2 0V5.414L4.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 10.293a1 1 0 010 1.414l-6 6a1 1 0 01-1.414 0l-6-6a1 1 0 111.414-1.414L9 14.586V3a1 1 0 012 0v11.586l4.293-4.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1">
                    <h4 className={`text-sm font-semibold mb-1 ${
                      directionFilter === 'increases' ? 'text-green-800' : 'text-red-800'
                    }`}>
                      {directionFilter === 'increases'
                        ? 'Viewing: Full Prompt Response'
                        : `Viewing: Response WITHOUT Section ${parseInt(selectedLeaveOneOutSection) + 1}`
                      }
                    </h4>
                    <p className={`text-xs ${
                      directionFilter === 'increases' ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {directionFilter === 'increases'
                        ? 'Showing behaviors that appear MORE with sections included'
                        : 'Showing behaviors that appear MORE when the section is removed (decreases)'
                      }
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="mb-6">
              <div className="flex items-center space-x-3 mb-3">
                <svg className="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
                </svg>
                <h2 className="text-2xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                  Sentence Attribution Showcase
                </h2>
              </div>
              <p className="text-sm text-text-secondary">
                See how different prompt sections influence specific parts of the AI's response. Hover over highlighted text to see detailed statistics.
              </p>
            </div>

            {/* Mode indicator */}
            {directionFilter === 'decreases' && (
              <div className="mb-4 p-4 bg-red-50 border-2 border-red-200 rounded-xl">
                <div className="flex items-start space-x-3">
                  <svg className="w-5 h-5 text-red-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="text-sm font-semibold text-red-800 mb-1">
                      Viewing Response WITHOUT Section {parseInt(selectedLeaveOneOutSection) + 1}
                    </h4>
                    <p className="text-xs text-red-700">
                      Showing the AI's response generated <strong>without</strong> the selected section.
                      Highlighted behaviors appear <strong>more frequently</strong> when the section is removed,
                      revealing what the section was <strong>suppressing</strong> in the full prompt.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {directionFilter === 'increases' && (
              <div className="mb-4 p-4 bg-green-50 border-2 border-green-200 rounded-xl">
                <div className="flex items-start space-x-3">
                  <svg className="w-5 h-5 text-green-600 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <h4 className="text-sm font-semibold text-green-800 mb-1">
                      Viewing Increases Mode
                    </h4>
                    <p className="text-xs text-green-700">
                      Highlighting quirks that <strong>increase</strong> when sections are present.
                      These are behaviors that <strong>appear or strengthen</strong> with the full prompt.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <ShowcaseResponse
              response={showcaseData.text}
              highlights={showcaseData.highlights}
              sections={sections.map((section, idx) => ({
                id: section.id,
                name: section.title,
                text: section.text, // Add full section text for tooltips
                color: ['blue', 'green', 'amber', 'red', 'purple', 'teal'][idx % 6],
              }))}
              selectedSections={selectedSections}
              onSectionToggle={toggleSectionFilter}
              onClearFilters={clearFilters}
            />
          </Card>
        )}

        {/* Detailed Quirk Table */}
        <Card padding="lg">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-border">
            <div>
              <h2 className="text-2xl font-bold text-text-primary mb-1">
                Detailed Quirk Analysis
              </h2>
              <p className="text-sm text-text-secondary">
                Explore individual quirks and their statistical significance
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const dataStr = JSON.stringify(result, null, 2);
                const dataBlob = new Blob([dataStr], { type: 'application/json' });
                const url = URL.createObjectURL(dataBlob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `quirk-analysis-${result.analysis_id}.json`;
                link.click();
              }}
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Export Results
            </Button>
          </div>

          <QuirkTable
            quirks={filteredQuirks}
            sections={sections}
            colors={SECTION_COLORS}
            selectedSections={selectedSections}
          />
        </Card>

        {/* Network Graph */}
        {result.network_graph && (
          <NetworkGraph
            nodes={result.network_graph.nodes}
            edges={result.network_graph.edges}
          />
        )}

        {/* Before/After Comparison (Secondary Feature) */}
        {result.leave_one_out_responses && result.showcase && (
          <BeforeAfterSlider
            fullPromptResponse={result.showcase.response_text}
            leaveOneOutResponses={result.leave_one_out_responses}
            sections={sections.map(s => ({ id: s.id, title: s.title, text: s.text }))}
            quirks={result.quirks.map(q => ({
              name: q.name,
              impact: q.impact,
              sectionId: q.sectionId,
              spikeRatio: q.spikeRatio || q.spike_ratio,
            }))}
          />
        )}

        {/* Actions */}
        <div className="flex gap-4 pt-4">
          <Button
            variant="primary"
            size="lg"
            className="flex-1"
            onClick={() => router.push('/analyze')}
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Analyze New Prompt
          </Button>
        </div>
      </div>
    </Layout>
  );
}
