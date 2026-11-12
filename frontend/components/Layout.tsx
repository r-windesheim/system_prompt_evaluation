import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const router = useRouter();
  const currentPath = router.pathname;

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur-md border-b border-border shadow-sm">
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/analyze" className="flex items-center space-x-3 group">
            <div className="w-10 h-10 bg-gradient-to-br from-primary to-accent rounded-xl flex items-center justify-center shadow-md group-hover:shadow-lg transition-all group-hover:scale-105">
              <span className="text-white text-xl font-bold">P</span>
            </div>
            <div className="flex flex-col">
              <span className="text-lg font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent leading-tight">
                Prompt Analyzer
              </span>
              <span className="text-xs text-text-tertiary">System Prompt Evaluation</span>
            </div>
          </Link>
          
          <div className="flex items-center space-x-4">
            {/* Navigation Tabs */}
            <div className="flex items-center space-x-2 bg-surface-elevated rounded-lg p-1 border border-border">
              <Link
                href="/analyze"
                className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-200 ${
                  currentPath === '/analyze' || currentPath === '/'
                    ? 'bg-gradient-to-r from-primary to-accent text-white shadow-md'
                    : 'text-text-secondary hover:text-primary hover:bg-surface'
                }`}
              >
                Analyze
              </Link>
              <Link
                href="/results"
                className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-200 ${
                  currentPath === '/results'
                    ? 'bg-gradient-to-r from-primary to-accent text-white shadow-md'
                    : 'text-text-secondary hover:text-primary hover:bg-surface'
                }`}
              >
                Results
              </Link>
            </div>
            
            {/* GitHub Link */}
            <a
              href="https://github.com/Astral-Oblivion/system_prompt_evaluation"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-primary hover:bg-surface-elevated transition-all group border border-transparent hover:border-border"
              title="View on GitHub"
            >
              <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
              </svg>
              <span className="hidden sm:inline">GitHub</span>
            </a>
          </div>
        </nav>
      </header>
      
      <main className="flex-1">
        {children}
      </main>
      
      <footer className="border-t border-border bg-background py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row justify-between items-center space-y-2 sm:space-y-0">
            <div className="text-sm text-text-secondary">
              AI Prompt Analyzer • Built with Next.js and Python
            </div>
            <a
              href="https://github.com/Astral-Oblivion/system_prompt_evaluation"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-text-tertiary hover:text-primary transition-colors"
            >
              View Source on GitHub →
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};
