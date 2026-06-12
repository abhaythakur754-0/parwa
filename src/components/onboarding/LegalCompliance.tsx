'use client';

import React, { useState } from 'react';
import { Loader2, CheckCircle2, Shield, ChevronDown, ChevronUp } from 'lucide-react';

interface LegalComplianceProps {
  onComplete: () => void;
  isSubmitting?: boolean;
}

export function LegalCompliance({ onComplete, isSubmitting = false }: LegalComplianceProps) {
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptAiData, setAcceptAiData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const allAccepted = acceptTerms && acceptPrivacy && acceptAiData;

  const handleSubmit = async () => {
    if (!allAccepted) {
      setError('All consents must be accepted to continue.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch('/api/onboarding/legal-consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          accept_terms: acceptTerms,
          accept_privacy: acceptPrivacy,
          accept_ai_data: acceptAiData,
        }),
      });

      // Even if the API fails, we still complete locally
      if (!res.ok) {
        console.warn('Legal consent API returned non-ok, continuing locally');
      }

      onComplete();
    } catch (err) {
      // API unavailable — complete step locally anyway
      console.warn('Legal consent API unavailable, completing locally');
      onComplete();
    } finally {
      setSubmitting(false);
    }
  };

  const cards = [
    {
      id: 'terms',
      checked: acceptTerms,
      onChange: setAcceptTerms,
      title: 'Terms of Service',
      icon: <Shield className="w-5 h-5 text-blue-400" />,
      description: 'Our terms govern your use of PARWA\'s AI-powered customer support platform, including service level commitments, data handling responsibilities, and acceptable use policies.',
      content: 'These Terms of Service ("Terms") govern your access to and use of PARWA, including our AI-powered customer support platform, analytics dashboard, and all associated services. By creating an account, you agree to be bound by these Terms and our Privacy Policy.',
    },
    {
      id: 'privacy',
      checked: acceptPrivacy,
      onChange: setAcceptPrivacy,
      title: 'Privacy Policy',
      icon: <Shield className="w-5 h-5 text-emerald-400" />,
      description: 'How we collect, process, and protect your data in compliance with GDPR, CCPA, and other applicable regulations.',
      content: 'PARWA is committed to protecting your privacy. We collect only the data necessary to provide our services, process it transparently, and never sell your data to third parties. Our AI systems are designed with privacy-by-design principles, ensuring customer data is handled responsibly and in compliance with applicable data protection laws.',
    },
    {
      id: 'ai-data',
      checked: acceptAiData,
      onChange: setAcceptAiData,
      title: 'AI Data Processing Agreement',
      icon: <Shield className="w-5 h-5 text-violet-400" />,
      description: 'Consent for using your data to improve AI models and provide intelligent customer support responses.',
      content: 'To provide AI-powered customer support, PARWA processes your uploaded knowledge base documents, conversation logs, and customer interactions. This data is used to train and improve our AI models. You retain full ownership of your data and can request deletion at any time. Data is encrypted at rest and in transit, and processed within your isolated tenant environment.',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
          <Shield className="w-7 h-7 text-blue-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Legal Compliance</h2>
        <p className="text-orange-200/40 text-sm">
          Review and accept our policies to continue setting up your account.
        </p>
      </div>

      <div className="space-y-3">
        {cards.map((card) => (
          <div
            key={card.id}
            className="rounded-xl border transition-all duration-200"
            style={{
              background: card.checked ? 'rgba(255,127,17,0.05)' : 'rgba(255,255,255,0.03)',
              borderColor: card.checked ? 'rgba(255,127,17,0.3)' : 'rgba(255,255,255,0.08)',
            }}
          >
            {/* Header row */}
            <div
              className="flex items-center gap-3 p-4 cursor-pointer"
              onClick={() => setExpandedCard(expandedCard === card.id ? null : card.id)}
            >
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); card.onChange(!card.checked); }}
                className={`w-5 h-5 rounded flex items-center justify-center shrink-0 transition-all ${
                  card.checked
                    ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white'
                    : 'border border-white/20 hover:border-orange-400/50'
                }`}
              >
                {card.checked && <CheckCircle2 className="w-3.5 h-3.5" />}
              </button>
              <div className="flex items-center gap-2 flex-1">
                {card.icon}
                <span className="text-sm font-medium text-white">{card.title}</span>
              </div>
              {expandedCard === card.id ? (
                <ChevronUp className="w-4 h-4 text-zinc-500" />
              ) : (
                <ChevronDown className="w-4 h-4 text-zinc-500" />
              )}
            </div>

            {/* Description */}
            <div className="px-4 pb-2">
              <p className="text-xs text-orange-200/30">{card.description}</p>
            </div>

            {/* Expandable content */}
            {expandedCard === card.id && (
              <div className="mx-4 mb-4 p-3 rounded-lg text-xs text-orange-200/30 leading-relaxed" style={{ background: 'rgba(255,255,255,0.03)' }}>
                {card.content}
              </div>
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={!allAccepted || submitting || isSubmitting}
          className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 disabled:from-zinc-700 disabled:to-zinc-700 disabled:text-zinc-500 text-[#1A1A1A] disabled:text-zinc-500 font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 disabled:shadow-none text-sm flex items-center gap-2"
        >
          {submitting || isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Accepting...
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4" />
              Accept All & Continue
            </>
          )}
        </button>
      </div>
    </div>
  );
}
