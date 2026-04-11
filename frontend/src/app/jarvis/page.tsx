'use client';

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { JarvisChat } from '@/components/jarvis/JarvisChat';

/**
 * Jarvis Chat Page
 *
 * Full-page Jarvis chat interface for onboarding.
 * Reads URL params (industry, variant, entry_source) and passes them
 * so Jarvis knows exactly what the user was looking at.
 */
export default function JarvisPage() {
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

    // Also read bridged context from localStorage (set by ChatWidget/models page)
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('parwa_jarvis_context');
        if (stored) {
          const ctx = JSON.parse(stored) as Record<string, unknown>;
          if (ctx.variant && !variant) params.variant = ctx.variant;
          if (ctx.variant_id && !variant) params.variant_id = ctx.variant_id;
          if (ctx.industry && !industry) params.industry = ctx.industry;
          if (ctx.selected_variants) params.selected_variants = ctx.selected_variants;
          if (ctx.interests) params.interests = ctx.interests;
          // Pass rich variant context from models page to Jarvis session
          if (ctx.entry_source) params.entry_source = ctx.entry_source;
          if (ctx.features) params.features = ctx.features;
          if (ctx.unique_features) params.unique_features = ctx.unique_features;
          if (ctx.roi) params.roi = ctx.roi;
          if (ctx.scenario) params.scenario = ctx.scenario;
          if (ctx.price) params.price = ctx.price;
          if (ctx.tagline) params.tagline = ctx.tagline;
          if (ctx.best_for) params.best_for = ctx.best_for;
          if (ctx.integrations) params.integrations = ctx.integrations;
          if (ctx.core_capability) params.core_capability = ctx.core_capability;
          if (ctx.core_limitation) params.core_limitation = ctx.core_limitation;
          if (ctx.smart_decisions) params.smart_decisions = ctx.smart_decisions;
          if (ctx.key_advantage) params.key_advantage = ctx.key_advantage;
          localStorage.removeItem('parwa_jarvis_context');
        }
      } catch {
        // ignore
      }
    }

    setEntrySource(entrySourceParam || 'direct');
    setEntryParams(params);
  }, [searchParams]);

  return (
    <JarvisChat
      isOpen={isOpen}
      onClose={() => window.history.back()}
      entrySource={entrySource}
      entryParams={entryParams}
    />
  );
}
