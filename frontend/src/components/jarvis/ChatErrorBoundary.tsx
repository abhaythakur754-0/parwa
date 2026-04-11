/**
 * PARWA ChatErrorBoundary (Week 6 — Day 3 — Gap Fix 6)
 *
 * Class-component error boundary that catches render-time errors
 * inside the JarvisChat component tree and shows a fallback UI.
 */

'use client';

import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface ChatErrorBoundaryProps {
  children: React.ReactNode;
}

interface ChatErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ChatErrorBoundary extends React.Component<
  ChatErrorBoundaryProps,
  ChatErrorBoundaryState
> {
  constructor(props: ChatErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ChatErrorBoundaryState {
    return { hasError: true, error };
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full flex flex-col items-center justify-center gap-4 px-6 bg-[#1A1A1A]">
          <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/15 flex items-center justify-center">
            <AlertTriangle className="w-8 h-8 text-red-400/60" />
          </div>

          <div className="text-center max-w-sm">
            <p className="text-sm font-medium text-white/60 mb-1">
              Something went wrong
            </p>
            <p className="text-xs text-white/30 mb-4">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>

            <button
              onClick={this.handleReset}
              className="inline-flex items-center gap-1.5 text-xs text-orange-400 hover:text-orange-300 underline underline-offset-2 transition-colors"
            >
              <RotateCcw className="w-3 h-3" />
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
