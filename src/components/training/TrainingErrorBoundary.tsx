'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * TrainingErrorBoundary
 * 
 * Error boundary specifically for training pipeline components.
 * Catches errors and displays a user-friendly fallback UI.
 */
export class TrainingErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Training Error Boundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
    
    // Log to error tracking service in production
    if (process.env.NODE_ENV === 'production') {
      // Could integrate with Sentry, LogRocket, etc.
      console.error('Training pipeline error:', {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      });
    }
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleGoHome = () => {
    window.location.href = '/dashboard/training';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[400px] flex items-center justify-center p-6">
          <Card className="bg-[#1A1A1A] border-red-500/25 max-w-md w-full">
            <CardContent className="p-6 text-center">
              <div className="w-16 h-16 rounded-full bg-red-500/15 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              
              <h2 className="text-xl font-bold text-white mb-2">
                Training Error
              </h2>
              
              <p className="text-gray-400 mb-4">
                Something went wrong in the training pipeline. Please try again.
              </p>

              {process.env.NODE_ENV === 'development' && this.state.error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4 text-left">
                  <p className="text-xs text-red-300 font-mono overflow-auto">
                    {this.state.error.message}
                  </p>
                </div>
              )}

              <div className="flex items-center justify-center gap-3">
                <Button
                  onClick={this.handleRetry}
                  variant="outline"
                  className="bg-white/5 border-white/10 text-gray-300 hover:text-white"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
                <Button
                  onClick={this.handleGoHome}
                  className="bg-gradient-to-r from-[#FF7F11] to-orange-500"
                >
                  <Home className="w-4 h-4 mr-2" />
                  Go to Training
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export default TrainingErrorBoundary;
