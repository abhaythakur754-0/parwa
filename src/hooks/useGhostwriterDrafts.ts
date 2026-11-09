/**
 * useGhostwriterDrafts — React hook for Ghostwriter draft management
 *
 * Provides the drafts list plus actions (draft this gap, approve, reject).
 * No auto-refresh: drafting runs a real LLM call and actions are explicit
 * human decisions — everything reloads after an action instead.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { ghostwriterApi } from '@/lib/ghostwriter-api';
import type {
  ApproveDraftResponse,
  GhostwriterDraft,
} from '@/lib/ghostwriter-api';

// ── Hook Return Type ────────────────────────────────────────────────

export interface UseGhostwriterDraftsReturn {
  drafts: GhostwriterDraft[];
  total: number;
  isLoading: boolean;
  isCreating: boolean;
  /** id of the draft an approve/reject action is currently running on */
  actingDraftId: string | null;
  error: string | null;

  createDraft: (topic: string) => Promise<GhostwriterDraft | null>;
  approveDraft: (draftId: string) => Promise<ApproveDraftResponse | null>;
  rejectDraft: (draftId: string) => Promise<boolean>;
  refresh: () => Promise<void>;
}

// ── Hook ────────────────────────────────────────────────────────────

export function useGhostwriterDrafts(): UseGhostwriterDraftsReturn {
  const [drafts, setDrafts] = useState<GhostwriterDraft[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [actingDraftId, setActingDraftId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await ghostwriterApi.listDrafts(50, 0);
      if (!mountedRef.current) return;
      setDrafts(data.drafts || []);
      setTotal(data.total || 0);
      setError(null);
    } catch {
      if (!mountedRef.current) return;
      setDrafts([]);
      setTotal(0);
      setError('Could not load drafts. The service may be unavailable.');
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // ── Actions ─────────────────────────────────────────────────────

  const createDraft = useCallback(async (topic: string) => {
    setIsCreating(true);
    setError(null);
    try {
      const created = await ghostwriterApi.createDraft(topic);
      await refresh();
      // Return the freshly-loaded row (full shape) when present
      return drafts.find((d) => d.id === created.id) || null;
    } catch {
      setError('Could not draft the article. Please try again.');
      return null;
    } finally {
      setIsCreating(false);
    }
  }, [refresh, drafts]);

  const approveDraft = useCallback(async (draftId: string) => {
    setActingDraftId(draftId);
    setError(null);
    try {
      const result = await ghostwriterApi.approveDraft(draftId);
      await refresh();
      return result;
    } catch {
      setError('Could not approve the draft. Please try again.');
      return null;
    } finally {
      setActingDraftId(null);
    }
  }, [refresh]);

  const rejectDraft = useCallback(async (draftId: string) => {
    setActingDraftId(draftId);
    setError(null);
    try {
      await ghostwriterApi.rejectDraft(draftId);
      await refresh();
      return true;
    } catch {
      setError('Could not reject the draft. Please try again.');
      return false;
    } finally {
      setActingDraftId(null);
    }
  }, [refresh]);

  return {
    drafts,
    total,
    isLoading,
    isCreating,
    actingDraftId,
    error,
    createDraft,
    approveDraft,
    rejectDraft,
    refresh,
  };
}
