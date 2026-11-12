import React, { useState } from 'react';
import { Layout } from '../components/Layout';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { TextArea, Input } from '../components/Input';
import { Select } from '../components/Select';
import { Badge } from '../components/Badge';
import { ProgressBar } from '../components/ProgressBar';
import { useRouter } from 'next/router';

interface Section {
  id: string;
  title: string;
  text: string;
  enabled: boolean;
  color: string;
}

const SECTION_COLORS = ['blue', 'green', 'amber', 'red', 'purple', 'teal'];

// Default sections from original Streamlit app (config.py)
const DEFAULT_SECTIONS = [
  "You are Claude, a helpful AI assistant created by Anthropic.",
  "Be direct and concise. Avoid unnecessary flattery like 'great question' or 'excellent idea'.",
  "Think critically and provide balanced perspectives. Don't just agree with everything.",
  "When uncertain, acknowledge limitations and suggest ways to find better information.",
  "Use examples and analogies to make complex topics more understandable.",
  "Be encouraging but realistic about challenges and potential outcomes."
];

const PREDEFINED_QUERIES = [
  'Should I do this?',
  'What do you think?',
  'This seems wrong',
  'Can you fix it?',
  'I don\'t understand',
  'Explain photosynthesis',
];

export default function Analyze() {
  const router = useRouter();
  const [step, setStep] = useState<'input' | 'sections' | 'configure' | 'analyzing'>('input');
  const [prompt, setPrompt] = useState('');
  const [sections, setSections] = useState<Section[]>([]);
  const [testQuery, setTestQuery] = useState(PREDEFINED_QUERIES[5]);
  const [numResponses, setNumResponses] = useState(30);
  const [includeSemanticQuirks, setIncludeSemanticQuirks] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');

  const handleDecompose = async () => {
    if (!prompt.trim()) return;

    try {
      setStatusMessage('Decomposing prompt into sections...');
      setAnalyzing(true);

      // Call backend API to decompose the prompt
      // Use exclude_factual: false for better grouping (aims for 15-30 logical sections)
      // exclude_factual: true would extract every tiny instruction separately
      const response = await fetch('http://localhost:8000/api/decompose-prompt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: prompt,
          exclude_factual: false  // Group related content into coherent sections
        })
      });

      if (!response.ok) {
        throw new Error('Failed to decompose prompt');
      }

      const data = await response.json();

      // Convert API response to Section format
      const apiSections: Section[] = data.sections.map((text: string, index: number) => ({
        id: String(index),
        title: `Section ${index + 1}`,
        text: text,
        enabled: true,
        color: SECTION_COLORS[index % SECTION_COLORS.length],
      }));

      setSections(apiSections);
      setAnalyzing(false);
      setStep('sections');
    } catch (error) {
      console.error('Error decomposing prompt:', error);
      setAnalyzing(false);
      setStatusMessage('Failed to decompose prompt. Please try again.');

      // Optionally show error to user
      alert('Failed to decompose prompt. Make sure the backend server is running on http://localhost:8000');
    }
  };

  const handleToggleSection = (id: string) => {
    setSections((prev) =>
      prev.map((section) =>
        section.id === id ? { ...section, enabled: !section.enabled } : section
      )
    );
  };

  const handleEditSection = (id: string, field: 'title' | 'text', value: string) => {
    setSections((prev) =>
      prev.map((section) =>
        section.id === id ? { ...section, [field]: value } : section
      )
    );
  };

  const handleRemoveSection = (id: string) => {
    setSections((prev) => prev.filter((section) => section.id !== id));
  };

  const handleStartAnalysis = async () => {
    setStep('analyzing');
    setAnalyzing(true);
    setProgress(0);

    const enabledSections = sections.filter((s) => s.enabled);
    const sectionTexts = enabledSections.map(s => s.text);

    try {
      setStatusMessage('Starting analysis...');
      setProgress(5);

      // Call real backend API
      const response = await fetch('http://localhost:8000/api/analyze-quirks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          sections: sectionTexts,
          test_queries: [testQuery],
          n_responses: numResponses,
          model: null, // Use default
          include_semantic: includeSemanticQuirks
        })
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      // Simulate progress while waiting
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 95) return prev;
          return prev + 1;
        });
      }, 2000);

      const result = await response.json();
      clearInterval(progressInterval);

      setProgress(100);
      setStatusMessage('Complete! Redirecting to results...');

      // Map backend response to frontend format
      const mappedResult = {
        ...result,
        quirks: result.quirks.map((quirk: any) => ({
          ...quirk,
          // Map backend snake_case to frontend camelCase
          sectionId: quirk.attribution?.section_index?.toString() || '0',
          sectionName: quirk.attribution?.section_text?.substring(0, 50) + '...' || 'Unknown',
          withSection: quirk.attribution?.with_section || 0,
          withoutSection: quirk.attribution?.without_section || 0,
          spike_ratio: quirk.spike_ratio || 1.0,
          spikeRatio: quirk.spike_ratio || 1.0, // Add camelCase version
        }))
      };

      // Map showcase attributions if present
      if (mappedResult.showcase?.attributions) {
        mappedResult.showcase.attributions = mappedResult.showcase.attributions.map((attr: any) => ({
          ...attr,
          spikeRatio: attr.spike_ratio || attr.impact || 1.0,
        }));
      }

      // Store mapped results
      sessionStorage.setItem('sections', JSON.stringify(sections));
      sessionStorage.setItem('analysisResult', JSON.stringify(mappedResult));

      setAnalyzing(false);

      // Small delay then redirect
      await new Promise((resolve) => setTimeout(resolve, 500));
      router.push('/results');

    } catch (error: any) {
      console.error('Analysis failed:', error);
      setAnalyzing(false);
      setStatusMessage('Analysis failed. Please try again.');
      alert(`Analysis failed: ${error.message}\n\nMake sure the backend is running on http://localhost:8000`);
      setStep('configure');
    }
  };

  return (
    <Layout>
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            {(['input', 'sections', 'configure'] as const).map((s, idx) => (
              <React.Fragment key={s}>
                <div
                  className={`flex items-center space-x-2 ${
                    step === s ? 'text-primary' : step === 'analyzing' || sections.length > 0 && idx < 2 ? 'text-success' : 'text-text-tertiary'
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold transition-all ${
                      step === s
                        ? 'bg-primary text-white ring-4 ring-primary/20'
                        : step === 'analyzing' || (sections.length > 0 && idx < 2)
                        ? 'bg-success text-white'
                        : 'bg-surface border-2 border-border'
                    }`}
                  >
                    {step === 'analyzing' || (sections.length > 0 && idx < 2) ? '✓' : idx + 1}
                  </div>
                  <span className="text-sm font-medium capitalize">{s}</span>
                </div>
                {idx < 2 && (
                  <div
                    className={`flex-1 h-1 mx-4 rounded ${
                      sections.length > 0 && idx === 0 ? 'bg-success' : step === 'configure' && idx === 1 ? 'bg-success' : 'bg-border'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step 1: Input Prompt */}
        {step === 'input' && (
          <div className="animate-slide-up space-y-6">
            <div className="text-center mb-8">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                Analyze Your Prompt
              </h1>
              <p className="text-lg text-text-secondary max-w-2xl mx-auto">
                Paste your system prompt below and we'll decompose it into testable sections
              </p>
            </div>

            <Card padding="lg">
              <TextArea
                label="System Prompt"
                placeholder="You are Claude, a helpful AI assistant created by Anthropic...

Be direct and concise. Avoid unnecessary flattery.

Think critically and provide balanced perspectives..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={12}
                helperText="Paste your complete system prompt. We'll intelligently split it into logical sections."
              />
              
              <div className="mt-6 flex justify-between items-center gap-4">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => {
                    const defaultSections: Section[] = DEFAULT_SECTIONS.map((text, index) => ({
                      id: String(index),
                      title: `Section ${index + 1}`,
                      text: text,
                      enabled: true,
                      color: SECTION_COLORS[index % SECTION_COLORS.length],
                    }));
                    setSections(defaultSections);
                    setStep('sections');
                  }}
                >
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Use Example Sections
                </Button>

                <Button
                  size="lg"
                  onClick={handleDecompose}
                  disabled={!prompt.trim() || analyzing}
                >
                  {analyzing ? (
                    <>
                      <svg className="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                      </svg>
                      Decompose My Prompt
                    </>
                  )}
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Step 2: Review Sections */}
        {step === 'sections' && (
          <div className="animate-slide-up space-y-6">
            <div className="text-center mb-8">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                Review Sections
              </h1>
              <p className="text-lg text-text-secondary max-w-2xl mx-auto">
                Check, edit, or remove sections before analysis
              </p>
            </div>

            <div className="space-y-4">
              {sections.map((section, idx) => (
                <Card key={section.id} padding="lg" hover>
                  <div className="flex items-start space-x-4">
                    <input
                      type="checkbox"
                      checked={section.enabled}
                      onChange={() => handleToggleSection(section.id)}
                      className="mt-1 w-5 h-5 rounded border-border text-primary focus:ring-primary focus:ring-offset-0"
                    />
                    
                    <div className="flex-1 space-y-3">
                      <div className="flex items-center space-x-3">
                        <Badge variant="primary" size="sm">Section {parseInt(section.id) + 1}</Badge>
                        <Input
                          value={section.title}
                          onChange={(e) => handleEditSection(section.id, 'title', e.target.value)}
                          className="flex-1 font-semibold"
                        />
                      </div>
                      
                      <TextArea
                        value={section.text}
                        onChange={(e) => handleEditSection(section.id, 'text', e.target.value)}
                        rows={2}
                        className="text-sm"
                      />
                    </div>
                    
                    <button
                      onClick={() => handleRemoveSection(section.id)}
                      className="p-2 text-text-tertiary hover:text-error transition-colors"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </Card>
              ))}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep('input')}>
                ← Back
              </Button>
              <Button
                size="lg"
                onClick={() => setStep('configure')}
                disabled={sections.filter((s) => s.enabled).length === 0}
              >
                Continue to Configuration
                <svg className="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Configure Analysis */}
        {step === 'configure' && (
          <div className="animate-slide-up space-y-6">
            <div className="text-center mb-8">
              <h1 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent">
                Configure Analysis
              </h1>
              <p className="text-lg text-text-secondary max-w-2xl mx-auto">
                Choose test parameters for behavioral quirk detection
              </p>
            </div>

            <Card padding="lg" className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-3">
                  Selected Sections ({sections.filter((s) => s.enabled).length})
                </label>
                <div className="flex flex-wrap gap-2">
                  {sections
                    .filter((s) => s.enabled)
                    .map((section) => (
                      <Badge key={section.id} variant="primary" size="lg">
                        {section.title}
                      </Badge>
                    ))}
                </div>
              </div>

              <div>
                <Select
                  label="Test Query"
                  value={testQuery}
                  onChange={setTestQuery}
                  options={PREDEFINED_QUERIES.map(q => ({ value: q, label: q }))}
                  helperText="Choose from presets or enter custom query below"
                />
                <Input
                  value={testQuery}
                  onChange={(e) => setTestQuery(e.target.value)}
                  placeholder="Or enter custom test query..."
                  className="mt-3"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-text-primary mb-2">
                  Number of Responses per Configuration
                </label>
                <Input
                  type="number"
                  value={numResponses}
                  onChange={(e) => setNumResponses(parseInt(e.target.value) || 30)}
                  min={10}
                  max={100}
                  helperText="More responses = better statistics but higher cost"
                />
              </div>

              <div className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  id="semantic-quirks"
                  checked={includeSemanticQuirks}
                  onChange={(e) => setIncludeSemanticQuirks(e.target.checked)}
                  className="w-5 h-5 rounded border-border text-primary focus:ring-primary"
                />
                <label htmlFor="semantic-quirks" className="text-sm font-medium text-text-primary">
                  Include semantic quirk analysis (doubles API cost)
                </label>
              </div>

              <div className="pt-4 border-t border-border">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-text-secondary">Estimated configurations:</span>
                  <span className="font-semibold">{sections.filter((s) => s.enabled).length + 1}</span>
                </div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-text-secondary">Total responses:</span>
                  <span className="font-semibold">{(sections.filter((s) => s.enabled).length + 1) * numResponses}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-secondary">Estimated cost:</span>
                  <span className="font-semibold text-primary">
                    $
                    {(
                      ((sections.filter((s) => s.enabled).length + 1) * numResponses * 0.0003) *
                      (includeSemanticQuirks ? 2 : 1)
                    ).toFixed(2)}
                  </span>
                </div>
              </div>
            </Card>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep('sections')}>
                ← Back
              </Button>
              <Button size="lg" onClick={handleStartAnalysis}>
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Start Analysis
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Analyzing */}
        {step === 'analyzing' && (
          <div className="animate-fade-in">
            <Card padding="lg" className="text-center space-y-6">
              <div className="w-20 h-20 mx-auto bg-gradient-to-br from-primary to-accent rounded-full flex items-center justify-center animate-pulse-soft">
                <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              
              <div>
                <h2 className="text-2xl font-bold mb-2">Analyzing Your Prompt</h2>
                <p className="text-text-secondary">{statusMessage}</p>
              </div>
              
              <ProgressBar progress={progress} className="max-w-md mx-auto" />
              
              <p className="text-sm text-text-tertiary">
                This may take 2-5 minutes depending on the number of sections and responses
              </p>
            </Card>
          </div>
        )}
      </div>
    </Layout>
  );
}

