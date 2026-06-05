'use client';

import React, { Suspense, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { JarvisChat } from '@/components/jarvis/JarvisChat';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';

/**
 * Jarvis Chat Page
 *
 * Full-page Jarvis chat interface for onboarding.
 * Reads URL params (industry, variant, entry_source) SYNCHRONOUSLY
 * via useSearchParams() — no useState+useEffect race condition.
 *
 * FIX: Previously entrySource initialized as 'direct' via useState, then
 * updated in useEffect. By the time useEffect ran, the hook had already
 * created a session with 'direct'. Now we read synchronously from searchParams.
 */

function readLocalStorageParams(params: Record<string, unknown>, variant: string | null, industry: string | null) {
  if (typeof window === 'undefined') return params;

  // Track page visit for context-aware Jarvis routing
  try {
    const existing = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]') as string[];
    if (!existing.includes('jarvis_chat_page')) {
      existing.push('jarvis_chat_page');
      localStorage.setItem('parwa_pages_visited', JSON.stringify(existing));
    }
  } catch {
    // ignore
  }

  try {
    const stored = localStorage.getItem('parwa_jarvis_context');
    if (stored) {
      const ctx = JSON.parse(stored) as Record<string, unknown>;
      if (ctx.variant && !variant) params.variant = ctx.variant;
      if (ctx.variant_id && !variant) params.variant_id = ctx.variant_id;
      if (ctx.industry && !industry) params.industry = ctx.industry;
      if (ctx.selected_variants) params.selected_variants = ctx.selected_variants;
      if (ctx.interests) params.interests = ctx.interests;
      // ── Pass rich variant context so Jarvis knows exactly what the user saw ──
      if (ctx.price) params.price = ctx.price;
      if (ctx.billing_cycle) params.billing_cycle = ctx.billing_cycle;
      if (ctx.tagline) params.tagline = ctx.tagline;
      if (ctx.scenario) params.scenario = ctx.scenario;
      if (ctx.roi) params.roi = ctx.roi;
      if (ctx.best_for) params.best_for = ctx.best_for;
      if (ctx.tickets_per_month) params.tickets_per_month = ctx.tickets_per_month;
      if (ctx.integrations) params.integrations = ctx.integrations;
      if (ctx.unique_features) params.unique_features = ctx.unique_features;
      if (ctx.key_advantage) params.key_advantage = ctx.key_advantage;
      if (ctx.smart_decisions) params.smart_decisions = ctx.smart_decisions;
      if (ctx.core_capability) params.core_capability = ctx.core_capability;
      if (ctx.core_limitation) params.core_limitation = ctx.core_limitation;
      if (ctx.human_cost_replaced) params.human_cost_replaced = ctx.human_cost_replaced;
      if (ctx.variant_tier) params.variant_tier = ctx.variant_tier;
    }
  } catch {
    // ignore
  }

  return params;
}

function JarvisPageInner() {
  const searchParams = useSearchParams();

  // ── SYNCHRONOUS: Read entry source directly from URL params ──
  // No useState('direct') + useEffect race condition.
  const entrySource = searchParams.get('entry_source') || 'jarvis_chat';

  // Build entryParams synchronously from URL + localStorage
  const entryParams = useMemo(() => {
    const params: Record<string, unknown> = {};

    const industry = searchParams.get('industry');
    const variant = searchParams.get('variant');

    if (industry) params.industry = industry;
    if (variant) params.variant = variant;

    // Enrich from localStorage (variant context from models page)
    readLocalStorageParams(params, variant, industry);

    return params;
  }, [searchParams]);

  return (
    <ChatErrorBoundary>
      <JarvisChat
        isOpen={true}
        onClose={() => window.history.back()}
        entrySource={entrySource}
        entryParams={entryParams}
      />
    </ChatErrorBoundary>
  );
}

export default function JarvisPage() {
  return (
    <Suspense>
      <JarvisPageInner />
    </Suspense>
  );
}
