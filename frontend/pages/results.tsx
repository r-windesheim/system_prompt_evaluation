import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { Section, AnalysisResult, ShowcaseData } from '@/lib/types';
import ImpactGauge from '@/components/ImpactGauge';
import ShowcaseResponse from '@/components/ShowcaseResponse';
import QuirkTable from '@/components/QuirkTable';
import { api } from '@/lib/api';

export default function Results() {
  const router = useRouter();
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [showcaseData, setShowcaseData] = useState<ShowcaseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadResults();
  }, []);

  const loadResults = async () => {
    try {
      // Load from sessionStorage
      const storedResult = sessionStorage.getItem('analysisResult');
      const storedSections = sessionStorage.getItem('sections');

      if (!storedResult || !storedSections) {
        router.push('/');
        return;
      }

      const parsedResult: AnalysisResult = JSON.parse(storedResult);
      const parsedSections: Section[] = JSON.parse(storedSections);

      setResult(parsedResult);
      setSections(parsedSections);

      // Generate showcase response if we have quirks
      if (parsedResult.quirks.length > 0) {
        await generateShowcase(parsedResult, parsedSections);
      }

      setLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load results');
      setLoading(false);
    }
  };

  const generateShowcase = async (
    analysisResult: AnalysisResult,
    sectionList: Section[]
  ) => {
    try {
      // Use the first quirk's example response as showcase
      const firstQuirk = analysisResult.quirks[0];
      const responseText = firstQuirk.example_snippets?.with_full ||
        "I think it's worth considering both sides of this issue. While I'm not entirely certain, here are the key points: For example, if you're working with Python, you could use a dictionary to store the data. However, there are some trade-offs to consider. You're on the right track!";

      // Generate attributions
      const showcaseResult = await api.generateAttributions(
        responseText,
        analysisResult.quirks,
        sectionList.map(s => s.text)
      );

      setShowcaseData(showcaseResult);
    } catch (err) {
      console.error('Failed to generate showcase:', err);
      // Continue without showcase
    }
  };

  const calculateImpactScore = () => {
    if (!result || result.quirks.length === 0) return 0;

    // Calculate average impact score
    const avgImpact = result.quirks.reduce((sum, q) => sum + Math.abs(q.impact), 0) / result.quirks.length;

    // Normalize to 0-100 scale (assuming max impact is around 20)
    return Math.min(Math.round((avgImpact / 20) * 100), 100);
  };

  const SECTION_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16',
  ];

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto text-center">
        <div className="card">
          <div className="text-lg text-gray-600">Loading results...</div>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="card">
          <div className="text-red-700 mb-4">{error || 'No results found'}</div>
          <button
            onClick={() => router.push('/')}
            className="btn-primary"
          >
            Start New Analysis
          </button>
        </div>
      </div>
    );
  }

  const impactScore = calculateImpactScore();
  const significantQuirks = result.quirks.filter(q => q.p_value < 0.05).length;

  return (
    <div className="max-w-7xl mx-auto">
      {/* Hero Section - Impact Score */}
      <div className="card mb-8 text-center">
        <ImpactGauge score={impactScore} />

        <p className="text-xl text-gray-700 mt-6 mb-8 max-w-3xl mx-auto leading-relaxed">
          {result.auto_summary || `Analysis complete! Detected ${result.total_quirks_detected} behavioral quirks across ${sections.length} sections.`}
        </p>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-6 mt-8">
          <div className="bg-gradient-primary text-white p-6 rounded-2xl">
            <div className="text-4xl font-bold mb-2">{result.total_quirks_detected}</div>
            <div className="text-sm opacity-90">Quirks Detected</div>
          </div>
          <div className="bg-gradient-primary text-white p-6 rounded-2xl">
            <div className="text-4xl font-bold mb-2">{significantQuirks}</div>
            <div className="text-sm opacity-90">Statistically Significant</div>
          </div>
          <div className="bg-gradient-primary text-white p-6 rounded-2xl">
            <div className="text-4xl font-bold mb-2">{sections.length}</div>
            <div className="text-sm opacity-90">Sections Analyzed</div>
          </div>
        </div>
      </div>

      {/* Showcase Response */}
      {showcaseData && (
        <div className="card mb-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-6 flex items-center gap-3">
            <span className="text-4xl">🎯</span>
            Showcase Response
          </h2>

          {/* Legend */}
          <div className="bg-gray-50 p-6 rounded-xl mb-6">
            <p className="text-sm font-semibold text-gray-700 mb-4">Sections:</p>
            <div className="flex flex-wrap gap-3">
              {sections.map((section, idx) => (
                <div
                  key={section.id}
                  className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer"
                  style={{ borderLeft: `4px solid ${SECTION_COLORS[idx % SECTION_COLORS.length]}` }}
                >
                  <div
                    className="w-6 h-6 rounded"
                    style={{ backgroundColor: SECTION_COLORS[idx % SECTION_COLORS.length] }}
                  />
                  <span className="text-sm font-medium text-gray-800">
                    Section {idx + 1}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Color-coded Response */}
          <ShowcaseResponse data={showcaseData} colors={SECTION_COLORS} />
        </div>
      )}

      {/* Detailed Quirk Table */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-800">
            Detailed Quirk Analysis
          </h2>
          <button
            onClick={() => {
              const dataStr = JSON.stringify(result, null, 2);
              const dataBlob = new Blob([dataStr], { type: 'application/json' });
              const url = URL.createObjectURL(dataBlob);
              const link = document.createElement('a');
              link.href = url;
              link.download = `quirk-analysis-${result.analysis_id}.json`;
              link.click();
            }}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors"
          >
            Export Results
          </button>
        </div>

        <QuirkTable quirks={result.quirks} sections={sections} colors={SECTION_COLORS} />
      </div>

      {/* Actions */}
      <div className="flex gap-4 mb-8">
        <button
          onClick={() => router.push('/')}
          className="btn-primary flex-1"
        >
          Analyze New Prompt
        </button>
      </div>
    </div>
  );
}
