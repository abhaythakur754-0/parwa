/**
 * useShadowMode — React hook for Shadow Mode state management
 *
 * Provides real-time shadow mode status, statistics, comparisons,
 * and actions (enable, disable, promote, graduate, review).
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { shadowModeApi } from '@/lib/shadow-mode-api';
import type {
  ShadowModeStatus,
  ShadowModeStatistics,
  ShadowComparison,
  EnableShadowModeRequest,
  HumanReviewRequest,
} from '@/types/shadow-mode';

// ── Hook Return Type ────────────────────────────────────────────────

export interface UseShadowModeReturn {
  // State
  status: ShadowModeStatus | null;
  statistics: ShadowModeStatistics | null;
  comparisons: ShadowComparison[];
  isLoading: boolean;
  isActionLoading: boolean;
  error: string | null;

  // Actions
  enableShadowMode: (data: EnableShadowModeRequest) => Promise<boolean>;
  disableShadowMode: (reason?: string) => Promise<boolean>;
  promoteShadowMode: (targetStatus?: 'supervised' | 'graduated') => Promise<boolean>;
  graduateShadowMode: () => Promise<boolean>;
  submitReview: (data: HumanReviewRequest) => Promise<boolean>;
  refreshAll: () => Promise<void>;
  refreshComparisons: () => Promise<void>;
}

// ── Hook ────────────────────────────────────────────────────────────

export function useShadowMode(autoRefreshMs = 0): UseShadowModeReturn {
  const [status, setStatus] = useState<ShadowModeStatus | null>(null);
  const [statistics, setStatistics] = useState<ShadowModeStatistics | null>(null);
  const [comparisons, setComparisons] = useState<ShadowComparison[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch Status ────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    try {
      const response = await shadowModeApi.status();
      if (response.status === 'ok' && response.data) {
        setStatus(response.data);
      }
    } catch {
      // Status fetch failed — likely not enabled yet
      setStatus(null);
    }
  }, []);

  // ── Fetch Statistics ─────────────────────────────────────────────

  const fetchStatistics = useCallback(async () => {
    try {
      const response = await shadowModeApi.statistics();
      if (response.status === 'ok' && response.data) {
        setStatistics(response.data);
      }
    } catch {
      setStatistics(null);
    }
  }, []);

  // ── Fetch Comparisons ───────────────────────────────────────────

  const fetchComparisons = useCallback(async () => {
    try {
      const response = await shadowModeApi.comparisons(50, 0);
      if (response.status === 'ok' && response.data) {
        setComparisons(response.data.comparisons || []);
      }
    } catch {
      setComparisons([]);
    }
  }, []);

  // ── Refresh All ──────────────────────────────────────────────────

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    await Promise.all([fetchStatus(), fetchStatistics(), fetchComparisons()]);
    setIsLoading(false);
  }, [fetchStatus, fetchStatistics, fetchComparisons]);

  const refreshComparisons = useCallback(async () => {
    await fetchComparisons();
  }, [fetchComparisons]);

  // ── Initial Load ─────────────────────────────────────────────────

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // ── Auto Refresh ─────────────────────────────────────────────────

  useEffect(() => {
    if (autoRefreshMs > 0) {
      intervalRef.current = setInterval(() => {
        refreshAll();
      }, autoRefreshMs);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefreshMs, refreshAll]);

  // ── Actions ───────────────────────────────────────────────────────

  const enableShadowMode = useCallback(async (data: EnableShadowModeRequest): Promise<boolean> => {
    setIsActionLoading(true);
    setError(null);
    try {
      const response = await shadowModeApi.enable(data);
      if (response.status === 'ok' && response.data?.success) {
        await refreshAll();
        return true;
      }
      setError(response.data?.message || 'Failed to enable shadow mode');
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to enable shadow mode');
      return false;
    } finally {
      setIsActionLoading(false);
    }
  }, [refreshAll]);

  const disableShadowMode = useCallback(async (reason?: string): Promise<boolean> => {
    setIsActionLoading(true);
    setError(null);
    try {
      const response = await shadowModeApi.disable({ reason });
      if (response.status === 'ok' && response.data?.success) {
        setStatus(null);
        setStatistics(null);
        setComparisons([]);
        await refreshAll();
        return true;
      }
      setError(response.data?.message || 'Failed to disable shadow mode');
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disable shadow mode');
      return false;
    } finally {
      setIsActionLoading(false);
    }
  }, [refreshAll]);

  const promoteShadowMode = useCallback(async (targetStatus?: 'supervised' | 'graduated'): Promise<boolean> => {
    setIsActionLoading(true);
    setError(null);
    try {
      const response = await shadowModeApi.promote({ target_status: targetStatus });
      if (response.status === 'ok' && response.data?.success) {
        await refreshAll();
        return true;
      }
      setError(response.data?.message || 'Failed to promote shadow mode');
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to promote shadow mode');
      return false;
    } finally {
      setIsActionLoading(false);
    }
  }, [refreshAll]);

  const graduateShadowMode = useCallback(async (): Promise<boolean> => {
    setIsActionLoading(true);
    setError(null);
    try {
      const response = await shadowModeApi.graduate();
      if (response.status === 'ok' && response.data?.success) {
        await refreshAll();
        return true;
      }
      setError(response.data?.message || 'Failed to graduate shadow mode');
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to graduate shadow mode');
      return false;
    } finally {
      setIsActionLoading(false);
    }
  }, [refreshAll]);

  const submitReview = useCallback(async (data: HumanReviewRequest): Promise<boolean> => {
    setIsActionLoading(true);
    setError(null);
    try {
      const response = await shadowModeApi.review(data);
      if (response.status === 'ok' && response.data?.success) {
        await refreshAll();
        return true;
      }
      setError(response.data?.message || 'Failed to submit review');
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit review');
      return false;
    } finally {
      setIsActionLoading(false);
    }
  }, [refreshAll]);

  return {
    status,
    statistics,
    comparisons,
    isLoading,
    isActionLoading,
    error,
    enableShadowMode,
    disableShadowMode,
    promoteShadowMode,
    graduateShadowMode,
    submitReview,
    refreshAll,
    refreshComparisons,
  };
}
