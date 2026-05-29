/**
 * PARWA useDemoVariant Hook
 *
 * React hook for managing the $1 Demo Pack variant selection flow.
 * Handles variant listing, session creation, usage tracking, and billing.
 */

'use client';

import { useCallback, useEffect, useState } from 'react';
import type {
  DemoVariant,
  DemoSession,
  DemoKnowledgeBase,
  DemoBillSummary,
  VariantTier,
  DemoUsage,
} from '@/types/demo-variant';
import {
  listVariants,
  createDemoSession,
  getDemoUsage,
  getDemoBilling,
} from '@/lib/demo-variant-api';

// ── Hook State ──────────────────────────────────────────────────

interface UseDemoVariantState {
  // Variant selection
  variants: DemoVariant[];
  selectedVariant: DemoVariant | null;
  selectedIndustry: string;
  industries: string[];

  // Session
  demoSession: DemoSession | null;
  isSessionLoading: boolean;

  // Usage
  usage: DemoUsage | null;

  // Billing
  billSummary: DemoBillSummary | null;

  // Knowledge Base
  knowledgeBases: DemoKnowledgeBase[];
  selectedKBs: string[];

  // General
  isLoading: boolean;
  error: string | null;
}

// ── Hook Return Type ────────────────────────────────────────────

interface UseDemoVariantReturn extends UseDemoVariantState {
  // Actions
  selectVariant: (variant: DemoVariant) => void;
  selectIndustry: (industry: string) => void;
  startDemo: () => Promise<void>;
  refreshUsage: () => Promise<void>;
  refreshBilling: () => Promise<void>;
  selectKB: (kbId: string) => void;
  deselectKB: (kbId: string) => void;
  clearError: () => void;
}

// ── Default State ───────────────────────────────────────────────

const DEFAULT_STATE: UseDemoVariantState = {
  variants: [],
  selectedVariant: null,
  selectedIndustry: '',
  industries: [],
  demoSession: null,
  isSessionLoading: false,
  usage: null,
  billSummary: null,
  knowledgeBases: [],
  selectedKBs: [],
  isLoading: false,
  error: null,
};

// ── Hook ────────────────────────────────────────────────────────

export function useDemoVariant(): UseDemoVariantReturn {
  const [state, setState] = useState<UseDemoVariantState>(DEFAULT_STATE);

  // Load variants on mount
  useEffect(() => {
    let mounted = true;

    async function load() {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const response = await listVariants();
        if (mounted) {
          setState((prev) => ({
            ...prev,
            variants: response.variants,
            industries: response.industries,
            isLoading: false,
          }));
        }
      } catch (err) {
        if (mounted) {
          setState((prev) => ({
            ...prev,
            error: err instanceof Error ? err.message : 'Failed to load variants',
            isLoading: false,
          }));
        }
      }
    }

    load();
    return () => { mounted = false; };
  }, []);

  // ── Actions ───────────────────────────────────────────────────

  const selectVariant = useCallback((variant: DemoVariant) => {
    setState((prev) => ({ ...prev, selectedVariant: variant }));
  }, []);

  const selectIndustry = useCallback((industry: string) => {
    setState((prev) => ({ ...prev, selectedIndustry: industry }));
  }, []);

  const startDemo = useCallback(async () => {
    if (!state.selectedVariant || !state.selectedIndustry) {
      setState((prev) => ({
        ...prev,
        error: 'Please select a variant and industry first.',
      }));
      return;
    }

    setState((prev) => ({ ...prev, isSessionLoading: true, error: null }));

    try {
      const response = await createDemoSession({
        variant_id: state.selectedVariant.id,
        variant_tier: state.selectedVariant.tier as VariantTier,
        industry: state.selectedIndustry,
        entry_source: 'demo_pack',
      });

      setState((prev) => ({
        ...prev,
        demoSession: response.session,
        isSessionLoading: false,
      }));

      // Load billing info
      if (response.session.id) {
        try {
          const billingResponse = await getDemoBilling(response.session.id);
          setState((prev) => ({
            ...prev,
            billSummary: billingResponse.bill_summary,
          }));
        } catch {
          // Non-critical — billing info can be loaded later
        }
      }
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : 'Failed to start demo',
        isSessionLoading: false,
      }));
    }
  }, [state.selectedVariant, state.selectedIndustry]);

  const refreshUsage = useCallback(async () => {
    if (!state.demoSession?.id) return;

    try {
      const response = await getDemoUsage(state.demoSession.id);
      setState((prev) => ({ ...prev, usage: response.usage }));
    } catch (err) {
      // Non-critical
    }
  }, [state.demoSession?.id]);

  const refreshBilling = useCallback(async () => {
    if (!state.demoSession?.id) return;

    try {
      const response = await getDemoBilling(state.demoSession.id);
      setState((prev) => ({ ...prev, billSummary: response.bill_summary }));
    } catch (err) {
      // Non-critical
    }
  }, [state.demoSession?.id]);

  const selectKB = useCallback((kbId: string) => {
    setState((prev) => ({
      ...prev,
      selectedKBs: prev.selectedKBs.includes(kbId)
        ? prev.selectedKBs
        : [...prev.selectedKBs, kbId],
    }));
  }, []);

  const deselectKB = useCallback((kbId: string) => {
    setState((prev) => ({
      ...prev,
      selectedKBs: prev.selectedKBs.filter((id) => id !== kbId),
    }));
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    selectVariant,
    selectIndustry,
    startDemo,
    refreshUsage,
    refreshBilling,
    selectKB,
    deselectKB,
    clearError,
  };
}

export default useDemoVariant;
