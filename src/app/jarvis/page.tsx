'use client';

import React, { Suspense, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { JarvisChat } from '@/components/jarvis/JarvisChat';
import { ChatErrorBoundary } from '@/components/jarvis/ChatErrorBoundary';

/**
 * Jarvis Chat Page
 *
 * Full-page Jarvis chat interface for onboarding.
 * Reads URL params (industry, variant, entry_source) and passes them
 * so Jarvis knows exactly what the user was looking at.
 */

function JarvisPageInner() {
  const [isOpen, setIsOpen] = useState(true);
  const searchParams = useSearchParams();

  // Read URL params once on mount
  const [entrySource, setEntrySource] = useState<string>('direct');
  const [entryParams, setEntryParams] = useState<Record<string, unknown>>({});

  useEffect(() => {
    const params: Record<string, unknown> = {};

    const industry = searchParams.get('industry');
    const variant = searchParams.get('variant');
    const entrySourceParam = searchParams.get('entry_source');

    if (industry) params.industry = industry;
    if (variant) params.variant = variant;

    // Track page visit for context-aware Jarvis routing
    if (typeof window !== 'undefined') {
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
          // Do NOT remove — let useJarvisChat sync to backend first
        }
      } catch {
        // ignore
      }
    }

    setEntrySource(entrySourceParam || 'jarvis_chat');
    setEntryParams(params);
  }, [searchParams]);

  return (
    <ChatErrorBoundary>
      <JarvisChat
        isOpen={isOpen}
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
