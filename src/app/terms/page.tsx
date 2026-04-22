'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function TermsPage() {
  return (
    <div
      className="min-h-screen py-12 px-4 sm:px-6 lg:px-8"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}
    >
      <div className="max-w-3xl mx-auto">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-orange-200/50 hover:text-orange-300 transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>

        <div
          className="rounded-2xl p-8 sm:p-10"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
            backdropFilter: 'blur(20px)',
          }}
        >
          <h1 className="text-2xl font-bold text-white mb-6">Terms of Service</h1>
          <p className="text-white/30 text-sm mb-8">Last updated: January 1, 2026</p>

          <div className="prose prose-invert prose-sm max-w-none space-y-6">
            <section>
              <h2 className="text-lg font-semibold text-white mb-2">1. Acceptance of Terms</h2>
              <p className="text-white/60 leading-relaxed">
                By accessing or using PARWA&apos;s AI customer support platform, you agree to be bound
                by these Terms of Service.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">2. Service Description</h2>
              <p className="text-white/60 leading-relaxed">
                PARWA provides AI-powered customer support agents across email, chat, SMS, voice,
                and social media channels.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">3. Billing</h2>
              <p className="text-white/60 leading-relaxed">
                Plans are billed monthly or annually with a 15% discount for annual billing.
                You may cancel anytime.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">4. Contact</h2>
              <p className="text-white/60 leading-relaxed">
                For legal inquiries, contact us at legal@parwa.ai.
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
