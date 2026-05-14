/**
 * PARWA Sentry Error Boundary (Phase 6)
 *
 * React error boundary that:
 *   - Captures errors to Sentry with component stack trace
 *   - Shows a user-friendly fallback UI
 *   - Provides a "Try Again" button to reset the error state
 *   - Adds custom tags (component name, route) for filtering
 *
 * Usage:
 *   <SentryErrorBoundary fallback={<CustomFallback />}>
 *     <MyComponent />
 *   </SentryErrorBoundary>
 *
 * BC-008: Never crash — the boundary itself cannot throw.
 */

'use client';

import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import * as Sentry from '@sentry/nextjs';

interface SentryErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
  /** Optional component name for Sentry tagging */
  componentName?: string;
  /** Optional callback when an error is caught */
  onError?: (error: Error, componentStack: string) => void;
  /** Optional callback when user clicks "Try Again" */
  onReset?: () => void;
}

interface SentryErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Default fallback UI shown when an error is caught.
 */
function DefaultFallback({
  error,
  onReset,
}: {
  error: Error | null;
  onReset: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center min-h-[200px] p-8 rounded-xl border border-orange-500/20 bg-[#1A1A1A]/95 backdrop-blur-xl"
    >
      <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center mb-4">
        <svg
          className="w-6 h-6 text-orange-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">
        Something went wrong
      </h3>
      <p className="text-sm text-orange-200/60 text-center mb-4 max-w-md">
        We encountered an unexpected error. Our team has been notified and is
        looking into it.
      </p>
      {process.env.NODE_ENV === 'development' && error && (
        <details className="mb-4 w-full max-w-md">
          <summary className="text-xs text-orange-200/40 cursor-pointer hover:text-orange-200/60">
            Error details (dev only)
          </summary>
          <pre className="mt-2 text-xs text-red-400/80 bg-black/30 rounded-lg p-3 overflow-auto max-h-32">
            {error.message}
          </pre>
        </details>
      )}
      <button
        onClick={onReset}
        className="px-4 py-2 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-lg transition-colors duration-200"
      >
        Try Again
      </button>
    </div>
  );
}

export class SentryErrorBoundary extends Component<
  SentryErrorBoundaryProps,
  SentryErrorBoundaryState
> {
  constructor(props: SentryErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): SentryErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Capture the error to Sentry with additional context
    try {
      Sentry.withScope((scope) => {
        // Add component stack trace
        scope.setExtra('componentStack', errorInfo.componentStack);

        // Add component name if provided
        if (this.props.componentName) {
          scope.setTag('component', this.props.componentName);
        }

        // Add error boundary tag for filtering
        scope.setTag('source', 'error_boundary');

        // Capture the exception
        Sentry.captureException(error);
      });
    } catch {
      // BC-008: Never crash — Sentry capture failure is non-fatal
    }

    // Call optional error callback
    if (this.props.onError) {
      try {
        this.props.onError(error, errorInfo.componentStack || '');
      } catch {
        // BC-008: Never crash
      }
    }

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('[SentryErrorBoundary]', error, errorInfo);
    }
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });

    // Call optional reset callback
    if (this.props.onReset) {
      try {
        this.props.onReset();
      } catch {
        // BC-008: Never crash
      }
    }
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided, otherwise use default
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <DefaultFallback
          error={this.state.error}
          onReset={this.handleReset}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * Higher-order component for wrapping functional components
 * with the Sentry error boundary.
 *
 * Usage:
 *   export default withSentryErrorBoundary(MyComponent, { componentName: 'MyComponent' });
 */
export function withSentryErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  boundaryProps?: Omit<SentryErrorBoundaryProps, 'children'>,
): React.ComponentType<P> {
  const displayName =
    WrappedComponent.displayName || WrappedComponent.name || 'Component';

  const ComponentWithErrorBoundary = (props: P) => (
    <SentryErrorBoundary
      componentName={displayName}
      {...boundaryProps}
    >
      <WrappedComponent {...props} />
    </SentryErrorBoundary>
  );

  ComponentWithErrorBoundary.displayName = `withSentryErrorBoundary(${displayName})`;

  return ComponentWithErrorBoundary;
}
