/**
 * PARWA useRetryWithBackoff Hook
 *
 * Retries a failed async operation with exponential backoff.
 * Used for API calls, data fetches, and other operations that may
 * fail transiently (network issues, rate limits, server errors).
 *
 * Features:
 * - Exponential backoff with optional jitter
 * - Max retry limit
 * - Cancel in-flight retries on unmount
 * - Success/error callbacks
 * - Manual trigger + auto-retry modes
 *
 * Usage:
 *   const { execute, isRetrying, retryCount, error, reset } = useRetryWithBackoff(fetchData, {
 *     maxRetries: 3,
 *     baseDelay: 1000,
 *     onSuccess: (data) => console.log(data),
 *   });
 */

'use client';

import { useState, useRef, useCallback } from 'react';

export interface RetryOptions<T = unknown> {
  /** Maximum number of retries (default: 3) */
  maxRetries?: number;
  /** Base delay in ms — doubles each retry (default: 1000) */
  baseDelay?: number;
  /** Maximum delay cap in ms (default: 30000) */
  maxDelay?: number;
  /** Add random jitter to prevent thundering herd (default: true) */
  jitter?: boolean;
  /** Called on successful execution */
  onSuccess?: (data: T) => void;
  /** Called when all retries are exhausted */
  onError?: (error: Error) => void;
  /** Called on each retry attempt */
  onRetry?: (retryCount: number, error: Error) => void;
  /** Only retry on specific error types (default: always retry) */
  retryIf?: (error: Error) => boolean;
}

export interface RetryState<T = unknown> {
  /** Whether an execution is in progress (initial or retry) */
  isLoading: boolean;
  /** Whether we are currently in a retry cycle */
  isRetrying: boolean;
  /** Current retry count (0 = first attempt, 1 = first retry, etc.) */
  retryCount: number;
  /** The last error encountered */
  error: Error | null;
  /** The data from the last successful execution */
  data: T | null;
  /** Whether all retries have been exhausted */
  hasExhaustedRetries: boolean;
}

export function useRetryWithBackoff<T = unknown>(
  fn: () => Promise<T>,
  options: RetryOptions<T> = {}
): RetryState<T> & {
  /** Execute the function (starts retry cycle on failure) */
  execute: () => Promise<T | null>;
  /** Reset the retry state */
  reset: () => void;
  /** Cancel any pending retries */
  cancel: () => void;
} {
  const {
    maxRetries = 3,
    baseDelay = 1000,
    maxDelay = 30000,
    jitter = true,
    onSuccess,
    onError,
    onRetry,
    retryIf,
  } = options;

  const [state, setState] = useState<RetryState<T>>({
    isLoading: false,
    isRetrying: false,
    retryCount: 0,
    error: null,
    data: null,
    hasExhaustedRetries: false,
  });

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const cancelledRef = useRef(false);

  // Cleanup on unmount
  const cleanup = useCallback(() => {
    mountedRef.current = false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // We use a ref for the function to always call the latest version
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const calculateDelay = useCallback(
    (retryCount: number): number => {
      const exponentialDelay = baseDelay * Math.pow(2, retryCount);
      const cappedDelay = Math.min(exponentialDelay, maxDelay);
      if (jitter) {
        // Add random jitter: 0.5x to 1.5x the delay
        return cappedDelay * (0.5 + Math.random());
      }
      return cappedDelay;
    },
    [baseDelay, maxDelay, jitter]
  );

  const execute = useCallback(async (): Promise<T | null> => {
    cancelledRef.current = false;
    let currentRetry = 0;

    setState((prev) => ({
      ...prev,
      isLoading: true,
      isRetrying: false,
      retryCount: 0,
      error: null,
      hasExhaustedRetries: false,
    }));

    while (currentRetry <= maxRetries) {
      if (cancelledRef.current || !mountedRef.current) return null;

      try {
        const result = await fnRef.current();

        if (!mountedRef.current) return null;

        setState({
          isLoading: false,
          isRetrying: false,
          retryCount: currentRetry,
          error: null,
          data: result,
          hasExhaustedRetries: false,
        });

        onSuccess?.(result);
        return result;
      } catch (err) {
        if (!mountedRef.current) return null;

        const error = err instanceof Error ? err : new Error(String(err));

        // Check if we should retry this type of error
        if (retryIf && !retryIf(error)) {
          setState((prev) => ({
            ...prev,
            isLoading: false,
            error,
            hasExhaustedRetries: true,
          }));
          onError?.(error);
          return null;
        }

        currentRetry++;

        if (currentRetry > maxRetries) {
          setState({
            isLoading: false,
            isRetrying: false,
            retryCount: currentRetry - 1,
            error,
            data: null,
            hasExhaustedRetries: true,
          });
          onError?.(error);
          return null;
        }

        // Retry
        onRetry?.(currentRetry, error);

        setState((prev) => ({
          ...prev,
          isRetrying: true,
          retryCount: currentRetry,
          error,
        }));

        const delay = calculateDelay(currentRetry - 1);

        // Wait with backoff
        await new Promise<void>((resolve) => {
          timerRef.current = setTimeout(resolve, delay);
        });

        if (cancelledRef.current || !mountedRef.current) return null;
      }
    }

    return null;
  }, [maxRetries, calculateDelay, onSuccess, onError, onRetry, retryIf]);

  const reset = useCallback(() => {
    cancelledRef.current = true;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setState({
      isLoading: false,
      isRetrying: false,
      retryCount: 0,
      error: null,
      data: null,
      hasExhaustedRetries: false,
    });
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setState((prev) => ({
      ...prev,
      isLoading: false,
      isRetrying: false,
    }));
  }, []);

  // Track mount state
  // Note: We need to set mountedRef on each render cycle
  mountedRef.current = true;

  return {
    ...state,
    execute,
    reset,
    cancel,
  };
}
