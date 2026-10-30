'use client';

import { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck,
  Lock,
  Fingerprint,
  HeartPulse,
  Activity,
  Eye,
  FileCheck,
  BadgeCheck,
  ChevronRight,
  ArrowRight,
} from 'lucide-react';

/**
 * TrustSection — "Security you can verify" section.
 *
 * Every claim here maps to real code (verified via graphify):
 * - Rust PII redactor (parwa_core: pii_redactor.rs, Luhn card detection)
 * - Guardrails engine incl. PHI + financial regulatory checks
 * - MFA, audit_log_service, IncidentService, self-healing, DLQ
 * - Data at rest in Supabase on AWS
 * - PII is stripped BEFORE any LLM inference call
 *
 * Contains no SOC 2 / certification claims at all (removed by product decision —
 * we are not certified, so we do not show the letters),
 * does not mention escalation or shadow mode (excluded by product decision).
 */

const pillars = [
  {
    icon: <ShieldCheck className="w-5 h-5 text-orange-300" />,
    title: 'Rust-Native PII Redaction',
    body: 'Names, emails, and card numbers (Luhn-verified) are stripped in a Rust core before any AI model ever sees them.',
  },
  {
    icon: <Lock className="w-5 h-5 text-orange-300" />,
    title: 'Encrypted in Transit & at Rest',
    body: 'TLS on every connection. Customer data rests in Supabase on AWS.',
  },
  {
    icon: <Fingerprint className="w-5 h-5 text-orange-300" />,
    title: 'MFA + Full Audit Trail',
    body: 'Multi-factor authentication on accounts, and every admin action is written to an immutable audit log.',
  },
  {
    icon: <HeartPulse className="w-5 h-5 text-orange-300" />,
    title: 'Regulatory Guardrails',
    body: 'PHI and financial-policy checks run inside the pipeline — sensitive requests are caught before they leave.',
  },
  {
    icon: <Activity className="w-5 h-5 text-orange-300" />,
    title: 'Self-Healing Infrastructure',
    body: 'Circuit breakers, dead-letter queues, and anomaly detection keep the pipeline stable under failure.',
  },
  {
    icon: <Eye className="w-5 h-5 text-orange-300" />,
    title: 'Monitored 24/7',
    body: 'Health endpoints, uptime checks, and error tracking watch every ticket end to end.',
  },
];

const dataFlow = [
  'Customer message arrives',
  'PII stripped in Rust',
  'AI reasons on redacted text',
  'Action verified before sending',
  'Data stored in your AWS region',
];

const subprocessors = [
  { name: 'Supabase', role: 'Database (Postgres)', note: 'Managed Postgres, on AWS' },
  { name: 'Render', role: 'Application hosting', note: 'Backend API + workers' },
  { name: 'Z.ai', role: 'AI inference + integration runtime', note: 'Receives redacted text only' },
  { name: 'Twilio', role: 'SMS & voice channels', note: 'Message/call transport' },
  { name: 'Groq / Mistral', role: 'LLM providers', note: 'Via gateway — redacted payloads only' },
];

const commitments = [
  'DPA available on request',
  'Data deleted when you leave',
  'Public subprocessor list',
  'CAIQ questionnaire on request',
];

export default function TrustSection() {
  const [isInView, setIsInView] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsInView(true);
      },
      { threshold: 0.1 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  const reveal = (_delayMs = 0) =>
    `transition-all duration-700 motion-reduce:transition-none ${
      isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
    }`;

  return (
    <section ref={sectionRef} id="security" className="relative overflow-hidden py-16 sm:py-20 lg:py-24" aria-labelledby="trust-heading">
      {/* Ambient glow orbs — silver-grey via theme */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-0 left-1/4 w-80 h-80 bg-orange-600/8 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className={`text-center mb-10 sm:mb-14 ${reveal(0)}`}>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/25 text-orange-300 text-xs font-semibold mb-5">
            <ShieldCheck className="w-3.5 h-3.5" />
            Trust &amp; Security
          </span>
          <h2 id="trust-heading" className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-5">
            Security You Can{' '}
            <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">Verify.</span>
          </h2>
          <p className="text-base sm:text-lg text-gray-400 max-w-2xl mx-auto">
            Enterprise security is not a PDF badge — it is engineering that runs on every
            single ticket. Here is exactly what runs on yours.
          </p>
        </div>

        {/* Engineering pillars */}
        <div className={`grid sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 mb-10 sm:mb-12 ${reveal(100)}`}>
          {pillars.map((p, i) => (
            <div
              key={p.title}
              className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6 hover:border-orange-400/30 hover:bg-white/[0.07] transition-colors duration-300"
              style={{ transitionDelay: `${i * 60}ms` }}
            >
              <div className="w-10 h-10 rounded-lg bg-orange-500/15 border border-orange-400/25 flex items-center justify-center mb-4">
                {p.icon}
              </div>
              <h3 className="text-sm sm:text-base font-bold text-white mb-2">{p.title}</h3>
              <p className="text-xs sm:text-sm text-gray-400 leading-relaxed">{p.body}</p>
            </div>
          ))}
        </div>

        {/* Data flow strip */}
        <div className={`mb-10 sm:mb-12 ${reveal(200)}`}>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4 text-center">
              Where your customer data goes — and does not
            </h3>
            <ol className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-1">
              {dataFlow.map((step, i) => (
                <li key={step} className="flex items-center gap-2 flex-1 min-w-0">
                  <span
                    className={`flex-1 rounded-lg border px-3 py-2.5 text-center text-[11px] sm:text-xs font-medium leading-snug ${
                      i === 1
                        ? 'border-orange-400/40 bg-orange-500/10 text-orange-200'
                        : 'border-white/10 bg-white/[0.05] text-gray-300'
                    }`}
                    style={{ transitionDelay: `${i * 60}ms` }}
                  >
                    <span className="block text-[10px] text-gray-500 font-bold mb-0.5">STEP {i + 1}</span>
                    {step}
                  </span>
                  {i < dataFlow.length - 1 && (
                    <ChevronRight className="hidden sm:block w-4 h-4 text-gray-600 flex-shrink-0" aria-hidden="true" />
                  )}
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Subprocessors + commitments */}
        <div className={`grid lg:grid-cols-5 gap-4 sm:gap-5 mb-8 sm:mb-10 ${reveal(250)}`}>
          {/* Subprocessor list — desktop table, mobile cards inside one panel */}
          <div className="lg:col-span-3 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Subprocessors — the complete list
            </h3>
            <ul className="space-y-2.5">
              {subprocessors.map((s) => (
                <li key={s.name} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-3 rounded-lg bg-white/[0.04] border border-white/[0.06] px-3.5 py-2.5">
                  <span className="text-xs sm:text-sm font-bold text-white w-28 flex-shrink-0">{s.name}</span>
                  <span className="text-xs sm:text-sm text-gray-300 flex-1">{s.role}</span>
                  <span className="text-[11px] sm:text-xs text-gray-500 sm:text-right sm:w-44 flex-shrink-0">{s.note}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Commitments */}
          <div className="lg:col-span-2 rounded-2xl border border-orange-400/20 bg-gradient-to-b from-orange-500/[0.07] to-white/[0.03] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Our commitments to you
            </h3>
            <ul className="space-y-3">
              {commitments.map((c) => (
                <li key={c} className="flex items-start gap-2.5 text-xs sm:text-sm text-gray-200">
                  <BadgeCheck className="w-4 h-4 text-orange-300 flex-shrink-0 mt-0.5" aria-hidden="true" />
                  {c}
                </li>
              ))}
            </ul>
            <p className="mt-5 text-[11px] leading-relaxed text-gray-500 border-t border-white/10 pt-4">
              Full trust pack — security whitepaper, DPA template, subprocessor list, and a
              completed CAIQ self-assessment — available on request.
            </p>
          </div>
        </div>

        {/* Punchline + CTA */}
        <div className={`rounded-2xl border border-orange-400/20 bg-gradient-to-r from-orange-500/[0.08] via-white/[0.04] to-orange-500/[0.08] backdrop-blur-sm p-6 sm:p-8 text-center ${reveal(300)}`}>
          <p className="text-base sm:text-lg text-gray-300 max-w-2xl mx-auto leading-relaxed">
            Ask us anything about security. We answer with{' '}
            <span className="text-white font-bold">engineering</span>, not PDFs.
          </p>
          <a
            href="mailto:security@parwa.dev?subject=Trust%20pack%20request"
            className="group inline-flex items-center gap-2 mt-5 rounded-xl px-7 py-3.5 text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#2C2C31] shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 hover:-translate-y-0.5 transition-all duration-500 focus-visible-ring"
          >
            Request the Full Trust Pack
            <FileCheck className="w-4 h-4" aria-hidden="true" />
            <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" aria-hidden="true" />
          </a>
        </div>
      </div>
    </section>
  );
}
