'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';

/**
 * Models Page - Light green theme
 * AI product showcase for the 3 PARWA AI variants.
 */

interface AIModel {
  id: string;
  name: string;
  tagline: string;
  tier: string;
  description: string;
  capabilities: string[];
  accentColor: string;
  accentBg: string;
  accentBorder: string;
  accentText: string;
  accentGlow: string;
  icon: React.ReactNode;
}

const models: AIModel[] = [
  {
    id: 'mini-parwa',
    name: 'Mini PARWA',
    tagline: '"The Freshy"',
    tier: 'Entry Level',
    description: 'Your first AI teammate. Handles FAQs, ticket intake, and never sleeps. Perfect for businesses just getting started with AI-powered support.',
    capabilities: ['Instant FAQ responses — zero training needed', 'Automated ticket intake and categorization', 'Up to 2 concurrent calls handled simultaneously', 'Smart escalation for complex issues to human agents', 'Basic knowledge base learning from your docs', '24/7 availability — works while you sleep'],
    accentColor: 'from-emerald-500 to-emerald-400',
    accentBg: 'bg-emerald-50',
    accentBorder: 'border-emerald-300',
    accentText: 'text-emerald-600',
    accentGlow: 'shadow-emerald-500/10',
    icon: <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" /></svg>,
  },
  {
    id: 'parwa-junior',
    name: 'PARWA',
    tagline: '"The Junior"',
    tier: 'Most Popular',
    description: 'Your smartest junior agent. Resolves 70-80% of support cases autonomously, verifies complex actions, and always recommends the right path forward.',
    capabilities: ['Resolves 70-80% of tickets autonomously', 'Verifies refunds and processes — never executes without approval', 'Recommends APPROVE / REVIEW / DENY for every decision', 'Full knowledge base with context-aware responses', 'Multi-language support for 50+ languages', 'Real-time escalation to human when confidence is low'],
    accentColor: 'from-emerald-600 to-emerald-500',
    accentBg: 'bg-emerald-50',
    accentBorder: 'border-emerald-300',
    accentText: 'text-emerald-700',
    accentGlow: 'shadow-emerald-600/10',
    icon: <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" /></svg>,
  },
  {
    id: 'parwa-senior',
    name: 'PARWA High',
    tagline: '"The Senior"',
    tier: 'Enterprise',
    description: 'Your most experienced senior agent. Handles complex cases, provides strategic insights, predicts churn, and manages up to 5 concurrent conversations.',
    capabilities: ['Resolves the most complex support cases with ease', 'Up to 5 concurrent calls handled simultaneously', 'Churn prediction and proactive retention strategies', 'Video support and screen-sharing capabilities', 'Strategic insights and revenue impact analytics', 'Full autonomous operations with human approval flows'],
    accentColor: 'from-emerald-700 to-emerald-600',
    accentBg: 'bg-emerald-100',
    accentBorder: 'border-emerald-400',
    accentText: 'text-emerald-800',
    accentGlow: 'shadow-emerald-600/10',
    icon: <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" /></svg>,
  },
];

export default function ModelsPage() {
  // Track page visit for context-aware Jarvis routing
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const existing = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]') as string[];
        if (!existing.includes('models_page')) {
          existing.push('models_page');
          localStorage.setItem('parwa_pages_visited', JSON.stringify(existing));
        }
      } catch {
        // ignore
      }
    }
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-b from-[#ECFDF5] to-white">
      <NavigationBar />
      <main className="flex-grow relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-emerald-200/15 rounded-full blur-[150px]" />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-emerald-100/15 rounded-full blur-[120px]" />
        </div>

        <section className="relative py-16 sm:py-20 md:py-28">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-50 border border-emerald-300/50 mb-6">
              <div className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
              <span className="text-sm text-emerald-700 font-medium">AI-Powered Support Agents</span>
            </div>
            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-4 sm:mb-6">
              Meet the <span className="text-gradient">PARWA</span> AI Family
            </h1>
            <p className="text-base sm:text-lg text-gray-500 max-w-2xl mx-auto px-4">
              Three intelligent AI agents, each designed for a different stage of your business growth. Choose the one that fits your needs — or start small and scale up instantly.
            </p>
          </div>
        </section>

        <section className="relative pb-16 sm:pb-20 md:pb-28">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
              {models.map((model, index) => (
                <div key={model.id}
                  className={`relative rounded-2xl border ${model.accentBorder} bg-white p-6 sm:p-8 transition-all duration-500 hover:-translate-y-2 hover:shadow-xl ${model.accentGlow} group`}
                  style={{ transitionDelay: `${index * 100}ms` }}>
                  <div className={`absolute -top-16 -right-16 w-32 h-32 ${model.accentBg} rounded-full blur-[60px] pointer-events-none opacity-50 group-hover:opacity-100 transition-opacity duration-500`} />
                  {model.tier && (
                    <div className="absolute top-4 right-4 sm:top-6 sm:right-6">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${model.accentBg} ${model.accentBorder} border ${model.accentText}`}>{model.tier}</span>
                    </div>
                  )}
                  <div className={`w-16 h-16 rounded-2xl ${model.accentBg} flex items-center justify-center mb-6 transition-all duration-300 group-hover:scale-110 ${model.accentText}`}>{model.icon}</div>
                  <h3 className="text-xl sm:text-2xl font-bold text-gray-900 mb-1">{model.name}</h3>
                  <p className={`text-sm font-medium ${model.accentText} mb-4`}>{model.tagline}</p>
                  <p className="text-sm text-gray-500 leading-relaxed mb-6">{model.description}</p>
                  <ul className="space-y-3 mb-8">
                    {model.capabilities.map((capability, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <svg className={`w-4 h-4 mt-0.5 flex-shrink-0 ${model.accentText}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        <span className="text-sm text-gray-600">{capability}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href="/pricing" className={`block w-full text-center bg-gradient-to-r ${model.accentColor} text-white px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-300 hover:shadow-lg ${model.accentGlow} hover:-translate-y-0.5`}>
                    View Details
                  </Link>
                </div>
              ))}
            </div>
            <div className="text-center mt-12 sm:mt-16 space-y-6">
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link href="/jarvis?entry_source=models_page" className="inline-flex items-center gap-2 bg-gradient-to-r from-orange-500 to-orange-400 text-white px-6 py-3 rounded-xl text-sm font-semibold transition-all duration-300 shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 hover:-translate-y-0.5">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                  Try Live Chat with Jarvis
                </Link>
                <Link href="/pricing" className="inline-flex items-center gap-2 text-emerald-600 hover:text-emerald-700 font-medium transition-colors duration-300">
                  Compare all plans and pricing
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
