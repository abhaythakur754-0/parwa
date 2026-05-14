'use client';

import React, { Component, ReactNode, ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    // Log to Sentry or other error reporting service
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleGoHome = () => {
    window.location.href = '/dashboard';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const isChunkError =
        this.state.error?.message?.includes('ChunkLoadError') ||
        this.state.error?.message?.includes('Loading chunk') ||
        this.state.error?.message?.includes('dynamically imported');

      return (
        <div
          role="alert"
          data-testid="error-boundary"
          className="min-h-[400px] flex items-center justify-center p-8"
        >
          <div className="max-w-md w-full text-center">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>

            <h2 className="text-xl font-bold text-white mb-2">
              {isChunkError ? 'Update Available' : 'Something went wrong'}
            </h2>

            <p className="text-sm text-zinc-400 mb-6">
              {isChunkError
                ? 'A new version of the app is available. Please reload to get the latest version.'
                : 'An unexpected error occurred. Our team has been notified and is working on a fix.'}
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mb-6 text-left">
                <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors">
                  Error details (dev only)
                </summary>
                <pre className="mt-2 p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] text-xs text-red-400 overflow-auto max-h-40">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}

            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
              >
                <RefreshCw className="w-4 h-4" />
                {isChunkError ? 'Reload Page' : 'Try Again'}
              </button>

              {!isChunkError && (
                <button
                  onClick={this.handleGoHome}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                >
                  <Home className="w-4 h-4" />
                  Dashboard
                </button>
              )}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
