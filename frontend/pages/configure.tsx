import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { api } from '@/lib/api';
import { Section } from '@/lib/types';

export default function Configure() {
  const router = useRouter();
  const [sections, setSections] = useState<Section[]>([]);
  const [availableQueries, setAvailableQueries] = useState<string[]>([]);
  const [selectedQuery, setSelectedQuery] = useState('');
  const [nResponses, setNResponses] = useState(30);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [costEstimate, setCostEstimate] = useState<number | null>(null);

  // Load sections from sessionStorage
  useEffect(() => {
    const stored = sessionStorage.getItem('sections');
    if (!stored) {
      router.push('/');
      return;
    }

    const parsedSections: Section[] = JSON.parse(stored);
    setSections(parsedSections);

    // Load available queries
    loadConfig();
    estimateCost(parsedSections.length, nResponses);
  }, []);

  const loadConfig = async () => {
    try {
      const config = await api.getConfig();
      setAvailableQueries(config.quirk_analysis_queries);
      setSelectedQuery(config.quirk_analysis_queries[0]);
    } catch (err: any) {
      setError('Failed to load configuration');
    }
  };

  const estimateCost = async (nSections: number, nResp: number) => {
    try {
      const result = await api.estimateCost(nSections, nResp);
      setCostEstimate(result.total_cost);
    } catch (err) {
      console.error('Cost estimation failed:', err);
    }
  };

  const handleNResponsesChange = (value: number) => {
    setNResponses(value);
    estimateCost(sections.length, value);
  };

  const handleStartAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    setProgress(0);

    try {
      const sectionTexts = sections.map(s => s.text);
      const queries = selectedQuery ? [selectedQuery] : undefined;

      // Simulate progress (actual progress tracking would require WebSocket/SSE)
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 2, 95));
      }, 500);

      const result = await api.analyzeQuirks(
        sectionTexts,
        queries,
        nResponses,
        false // No semantic quirks for MVP
      );

      clearInterval(progressInterval);
      setProgress(100);

      // Store results
      sessionStorage.setItem('analysisResult', JSON.stringify(result));
      sessionStorage.setItem('sections', JSON.stringify(sections));

      // Navigate to results
      setTimeout(() => {
        router.push('/results');
      }, 500);

    } catch (err: any) {
      setError(err.message || 'Analysis failed');
      setAnalyzing(false);
      setProgress(0);
    }
  };

  const SECTION_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16',
  ];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-white mb-2">
          Configure Analysis
        </h1>
        <p className="text-lg text-white/90">
          Select test query and parameters
        </p>
      </div>

      {/* Main Card */}
      <div className="card">
        {/* Selected Sections */}
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-800 mb-4">
            Selected Sections ({sections.length})
          </h2>
          <div className="flex flex-wrap gap-3">
            {sections.map((section, idx) => (
              <div
                key={section.id}
                className="px-4 py-2 rounded-lg text-white font-medium text-sm"
                style={{ backgroundColor: SECTION_COLORS[idx % SECTION_COLORS.length] }}
              >
                Section {idx + 1}
              </div>
            ))}
          </div>
        </div>

        {/* Test Query Selection */}
        <div className="mb-8">
          <label className="block text-gray-800 font-semibold mb-3">
            Test Query
          </label>
          <select
            value={selectedQuery}
            onChange={(e) => setSelectedQuery(e.target.value)}
            className="input"
            disabled={analyzing}
          >
            {availableQueries.map((query, idx) => (
              <option key={idx} value={query}>
                {query}
              </option>
            ))}
          </select>
          <p className="text-sm text-gray-600 mt-2">
            The AI will respond to this query with each prompt variation
          </p>
        </div>

        {/* Number of Responses */}
        <div className="mb-8">
          <label className="block text-gray-800 font-semibold mb-3">
            Number of Responses per Configuration
          </label>
          <input
            type="number"
            value={nResponses}
            onChange={(e) => handleNResponsesChange(parseInt(e.target.value))}
            min={10}
            max={100}
            step={10}
            className="input w-32"
            disabled={analyzing}
          />
          <p className="text-sm text-gray-600 mt-2">
            More responses = more reliable but slower and more expensive
          </p>
        </div>

        {/* Cost Estimate */}
        {costEstimate !== null && (
          <div className="mb-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-gray-800">Estimated Cost</p>
                <p className="text-sm text-gray-600">
                  {sections.length + 1} configurations × {nResponses} responses
                </p>
              </div>
              <div className="text-2xl font-bold text-blue-600">
                ${costEstimate.toFixed(3)}
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* Progress */}
        {analyzing && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">
                {progress < 30 && 'Generating responses...'}
                {progress >= 30 && progress < 60 && 'Analyzing quirks...'}
                {progress >= 60 && progress < 95 && 'Computing statistics...'}
                {progress >= 95 && 'Finalizing results...'}
              </span>
              <span className="text-sm font-medium text-gray-700">
                {Math.round(progress)}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
              <div
                className="h-full bg-gradient-primary transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={() => router.push('/')}
            disabled={analyzing}
            className="px-6 py-3 border-2 border-gray-300 text-gray-700 font-semibold rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            ← Back
          </button>
          <button
            onClick={handleStartAnalysis}
            disabled={analyzing || !selectedQuery}
            className="btn-primary flex-1 text-lg"
          >
            {analyzing ? 'Analyzing...' : 'Start Analysis'}
          </button>
        </div>
      </div>

      {/* Info Box */}
      {!analyzing && (
        <div className="card bg-white/90 mt-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">
            What happens next?
          </h3>
          <ul className="space-y-2 text-gray-700 text-sm">
            <li>• Generate {nResponses} responses with your full prompt</li>
            <li>• Generate {nResponses} responses for each section removed (leave-one-out testing)</li>
            <li>• Detect behavioral quirks in all responses</li>
            <li>• Identify which sections cause which quirks</li>
            <li>• Show you color-coded results</li>
          </ul>
        </div>
      )}
    </div>
  );
}
