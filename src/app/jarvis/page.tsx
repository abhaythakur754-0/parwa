'use client';

import React, { Suspense, useState, useEffect } from 'react';
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
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center" style={{ background: '#1A1A1A' }}><div className="text-white/60 text-sm animate-pulse">Loading Jarvis...</div></div>}>
      <JarvisPageInner />
    </Suspense>
  );
}

function JarvisPageInner() {
  const [isOpen] = useState(true);
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
