'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function PrivacyPage() {
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
          <h1 className="text-2xl font-bold text-white mb-6">Privacy Policy</h1>
          <p className="text-white/30 text-sm mb-8">Last updated: January 1, 2026</p>

          <div className="prose prose-invert prose-sm max-w-none space-y-6">
            <section>
              <h2 className="text-lg font-semibold text-white mb-2">1. Information We Collect</h2>
              <p className="text-white/60 leading-relaxed">
                PARWA collects information you provide directly (name, email, company details) and
                usage data (messages sent, features used, session analytics). We do not sell your
                data to third parties.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">2. How We Use Your Data</h2>
              <p className="text-white/60 leading-relaxed">
                Your data is used to provide and improve our AI customer support services,
                personalize your experience, and communicate important updates. Customer support
                conversations are used to train and improve our AI models only within your
                organization&apos;s tenant isolation.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">3. Data Security</h2>
              <p className="text-white/60 leading-relaxed">
                We employ AES-256 encryption at rest, TLS 1.3 in transit, per-tenant data isolation,
                and comply with GDPR and SOC 2 Type II standards.
              </p>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-white mb-2">4. Contact</h2>
              <p className="text-white/60 leading-relaxed">
                For privacy inquiries, contact us at privacy@parwa.ai.
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
