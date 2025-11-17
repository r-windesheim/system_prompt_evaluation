import { useState } from 'react';
import { useRouter } from 'next/router';
import { api } from '@/lib/api';
import { Section } from '@/lib/types';
import SectionCard from '@/components/SectionCard';

export default function Home() {
  const router = useRouter();
  const [prompt, setPrompt] = useState('');
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDecompose = async () => {
    if (!prompt.trim()) {
      setError('Please enter a system prompt');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.decomposePrompt(prompt, true);

      if (!result.validation_passed) {
        setError(result.validation_message || 'Validation failed');
        return;
      }

      // Convert to Section objects
      const parsedSections: Section[] = result.sections.map((text, idx) => ({
        id: idx,
        text,
        enabled: true,
      }));

      setSections(parsedSections);
    } catch (err: any) {
      setError(err.message || 'Failed to decompose prompt');
    } finally {
      setLoading(false);
    }
  };

  const toggleSection = (id: number) => {
    setSections(sections.map(s =>
      s.id === id ? { ...s, enabled: !s.enabled } : s
    ));
  };

  const updateSectionText = (id: number, text: string) => {
    setSections(sections.map(s =>
      s.id === id ? { ...s, text } : s
    ));
  };

  const removeSection = (id: number) => {
    setSections(sections.filter(s => s.id !== id));
  };

  const handleContinue = () => {
    const enabledSections = sections.filter(s => s.enabled);

    if (enabledSections.length === 0) {
      setError('Please enable at least one section');
      return;
    }

    // Store sections in sessionStorage for next screen
    sessionStorage.setItem('sections', JSON.stringify(enabledSections));
    router.push('/configure');
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-bold text-white mb-4">
          Prompt Quirk Analyzer
        </h1>
        <p className="text-xl text-white/90">
          Discover how each section of your prompt shapes AI behavior
        </p>
      </div>

      {/* Main Card */}
      <div className="card mb-8">
        {/* Step 1: Input */}
        {sections.length === 0 && (
          <>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">
              Paste Your System Prompt
            </h2>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Paste your system prompt here..."
              className="input min-h-[400px] font-mono text-sm resize-y"
              disabled={loading}
            />

            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                {error}
              </div>
            )}

            <button
              onClick={handleDecompose}
              disabled={loading || !prompt.trim()}
              className="btn-primary mt-6 w-full text-lg"
            >
              {loading ? 'Analyzing...' : 'Analyze Prompt'}
            </button>
          </>
        )}

        {/* Step 2: Review Sections */}
        {sections.length > 0 && (
          <>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">
              Detected Sections ({sections.length})
            </h2>
            <p className="text-gray-600 mb-6">
              Review and edit the detected sections. Uncheck any you want to exclude from analysis.
            </p>

            <div className="space-y-4 mb-6">
              {sections.map((section) => (
                <SectionCard
                  key={section.id}
                  section={section}
                  onToggle={toggleSection}
                  onUpdate={updateSectionText}
                  onRemove={removeSection}
                />
              ))}
            </div>

            {error && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                {error}
              </div>
            )}

            <div className="flex gap-4">
              <button
                onClick={() => setSections([])}
                className="px-6 py-3 border-2 border-gray-300 text-gray-700 font-semibold rounded-lg hover:bg-gray-50 transition-colors"
              >
                Start Over
              </button>
              <button
                onClick={handleContinue}
                className="btn-primary flex-1 text-lg"
              >
                Continue to Analysis →
              </button>
            </div>
          </>
        )}
      </div>

      {/* Help Text */}
      {sections.length === 0 && (
        <div className="card bg-white/90">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">
            How it works
          </h3>
          <ol className="space-y-2 text-gray-700">
            <li className="flex gap-3">
              <span className="font-bold text-primary">1.</span>
              <span>Paste your system prompt above</span>
            </li>
            <li className="flex gap-3">
              <span className="font-bold text-primary">2.</span>
              <span>We'll decompose it into logical sections using GPT-4o</span>
            </li>
            <li className="flex gap-3">
              <span className="font-bold text-primary">3.</span>
              <span>Select which sections to test and configure analysis</span>
            </li>
            <li className="flex gap-3">
              <span className="font-bold text-primary">4.</span>
              <span>See color-coded results showing which sections cause which behaviors</span>
            </li>
          </ol>
        </div>
      )}
    </div>
  );
}
