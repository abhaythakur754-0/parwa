'use client';

import React, { Suspense, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { JarvisChat } from '@/components/jarvis/JarvisChat';

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
          // Do NOT remove — let useJarvisChat sync to backend first
        }
      } catch {
        // ignore
      }
    }

    setEntrySource(entrySourceParam || 'jarvis_chat');
    setEntryParams(params);
  }, [searchParams]);

  if (process.env.NODE_ENV === 'production') {
    return (
      <main className="min-h-screen flex items-center justify-center bg-[#2C2C31] px-6 py-16">
          <section className="max-w-xl text-center">
            <h1 className="text-3xl font-bold text-white mb-4">Jarvis guest demo is unavailable</h1>
            <p className="text-gray-300 mb-8">
              Public guest sessions are temporary and are disabled in production. Create an account to use persistent Jarvis and secure onboarding.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link href="/signup" className="rounded-xl bg-orange-500 px-6 py-3 font-semibold text-[#2C2C31]">
                Create account
              </Link>
              <Link href="/login" className="rounded-xl border border-white/20 px-6 py-3 font-semibold text-white">
                Sign in
              </Link>
            </div>
          </section>
        </main>
    );
  }

  return (
    <JarvisChat
      isOpen={isOpen}
      onClose={() => window.history.back()}
      entrySource={entrySource}
      entryParams={entryParams}
      isGuestDemo
    />
  );
}

export default function JarvisPage() {
  return (
    <Suspense>
      <JarvisPageInner />
    </Suspense>
  );
}
