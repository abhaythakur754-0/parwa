'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle2, XCircle, TestTube, Wifi } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────

export interface TestResult {
  success: boolean;
  latency_ms?: number;
  message: string;
}

interface TestConnectionProps {
  /** Async function that performs the connectivity test */
  onTest: () => Promise<TestResult>;
  /** Whether a test is currently in progress */
  isTesting: boolean;
  /** Result from the most recent test (null if no test has been run) */
  testResult: TestResult | null;
  /** D12-P14: Previous test result, shown as faded when a new test is run */
  previousTestResult?: TestResult | null;
}

// ── Component ─────────────────────────────────────────────────────────

/**
 * Reusable test connection component with live status updates.
 *
 * Renders a "Test Connection" button and a result panel that shows:
 * - A yellow spinner while testing
 * - A green checkmark with latency badge on success
 * - A red X with error message on failure
 */
export function TestConnection({ onTest, isTesting, testResult, previousTestResult }: TestConnectionProps) {
  return (
    <div className="space-y-3">
      {/* Test Connection Button */}
      <Button
        type="button"
        variant="outline"
        onClick={onTest}
        disabled={isTesting}
        className="w-full sm:w-auto"
      >
        {isTesting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Testing Connection...
          </>
        ) : (
          <>
            <TestTube className="mr-2 h-4 w-4" />
            Test Connection
          </>
        )}
      </Button>

      {/* Result Panel */}
      {isTesting && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800/40 dark:bg-yellow-950/30 p-4">
          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-yellow-100 dark:bg-yellow-900/50">
            <Wifi className="h-4 w-4 text-yellow-600 dark:text-yellow-400 animate-pulse" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              Testing connection...
            </p>
            <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-0.5">
              Attempting to reach the endpoint. This may take up to 10 seconds.
            </p>
          </div>
        </div>
      )}

      {/* Success Result */}
      {testResult && testResult.success && !isTesting && (
        <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 dark:border-green-800/40 dark:bg-green-950/30 p-4">
          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-100 dark:bg-green-900/50 shrink-0">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-green-800 dark:text-green-200">
              Connected successfully
            </p>
            <p className="text-xs text-green-600 dark:text-green-400 mt-0.5 truncate">
              {testResult.message}
            </p>
          </div>
          {typeof testResult.latency_ms === 'number' && (
            <Badge
              variant="secondary"
              className="shrink-0 bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300"
            >
              {testResult.latency_ms}ms
            </Badge>
          )}
        </div>
      )}

      {/* Failure Result */}
      {testResult && !testResult.success && !isTesting && (
        <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 dark:border-red-800/40 dark:bg-red-950/30 p-4">
          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-red-100 dark:bg-red-900/50 shrink-0 mt-0.5">
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-red-800 dark:text-red-200">
              Connection failed
            </p>
            <p className="text-xs text-red-600 dark:text-red-400 mt-0.5 break-words">
              {testResult.message}
            </p>
          </div>
          {typeof testResult.latency_ms === 'number' && (
            <Badge
              variant="secondary"
              className="shrink-0 bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
            >
              {testResult.latency_ms}ms
            </Badge>
          )}
        </div>
      )}
      {/* D12-P14: Previous result shown as faded/smaller when a new test result exists */}
      {previousTestResult && !isTesting && (
        <div
          className={`flex items-start gap-3 rounded-lg border p-3 opacity-60 ${
            previousTestResult.success
              ? 'border-green-200 bg-green-50 dark:border-green-800/40 dark:bg-green-950/30'
              : 'border-red-200 bg-red-50 dark:border-red-800/40 dark:bg-red-950/30'
          }`}
        >
          {previousTestResult.success ? (
            <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
          ) : (
            <XCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-muted-foreground">Previous result</p>
            <p className="text-xs text-muted-foreground mt-0.5 break-words">
              {previousTestResult.message}
            </p>
          </div>
          {typeof previousTestResult.latency_ms === 'number' && (
            <Badge variant="secondary" className="shrink-0 text-xs">
              {previousTestResult.latency_ms}ms
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
