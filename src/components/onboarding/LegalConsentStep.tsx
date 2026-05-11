'use client';

import React, { useState } from 'react';
import {
  ShieldCheck,
  FileText,
  Lock,
  Brain,
  ExternalLink,
  ArrowRight,
  ArrowLeft,
  Loader2,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { onboardingApi, getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';

interface LegalConsentStepProps {
  onNext: () => void;
}

/**
 * Consent card configuration defining the three mandatory legal
 * consents that the user must accept before proceeding. Each card
 * has an icon, title, short description, and the full policy text
 * that can be displayed in a modal when the user clicks the link.
 */
const CONSENT_CARDS = [
  {
    id: 'terms' as const,
    icon: FileText,
    title: 'Terms of Service',
    description:
      'By accepting, you agree to our Terms of Service governing the use of the PARWA platform, including acceptable use policies, service level commitments, and dispute resolution procedures.',
    fullText: `PARWA TERMS OF SERVICE

Last Updated: January 2025

1. ACCEPTANCE OF TERMS
By accessing or using the PARWA platform ("Service"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, you may not access or use the Service.

2. DESCRIPTION OF SERVICE
PARWA provides an AI-powered customer support platform that automates ticket handling, response generation, and customer communication. The Service includes AI assistant capabilities, integration with third-party platforms, knowledge base management, and analytics.

3. ACCOUNT RESPONSIBILITIES
You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You agree to notify PARWA immediately of any unauthorized use of your account.

4. ACCEPTABLE USE
You agree not to use the Service for any unlawful purpose or in any way that could damage, disable, or impair the Service. You shall not attempt to gain unauthorized access to any part of the Service.

5. DATA PROCESSING
Your use of the Service is also governed by our Privacy Policy, which describes how we collect, use, and share your data.

6. SERVICE MODIFICATIONS
PARWA reserves the right to modify, suspend, or discontinue the Service at any time, including the availability of any feature, database, or content.

7. LIMITATION OF LIABILITY
PARWA shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of the Service.

8. GOVERNING LAW
These Terms shall be governed by and construed in accordance with applicable laws, without regard to conflict of law principles.`,
  },
  {
    id: 'privacy' as const,
    icon: Lock,
    title: 'Privacy Policy',
    description:
      'Our Privacy Policy explains how we collect, use, store, and protect your personal and company data. This includes information about data retention, processing purposes, and your rights regarding your data.',
    fullText: `PARWA PRIVACY POLICY

Last Updated: January 2025

1. INFORMATION WE COLLECT
We collect information you provide directly, including account details (name, email, company name), usage data, support tickets processed through our platform, and integration credentials you choose to connect.

2. HOW WE USE YOUR INFORMATION
We use collected information to provide and improve our Service, process customer support tickets, train and improve AI models, communicate with you about your account, and comply with legal obligations.

3. DATA STORAGE AND SECURITY
We implement industry-standard security measures to protect your data, including encryption at rest and in transit, regular security audits, access controls, and monitoring systems.

4. DATA SHARING
We do not sell your personal information. We may share data with service providers who assist in operating our platform, when required by law, or with your explicit consent.

5. YOUR RIGHTS
You have the right to access, correct, delete, or export your personal data. You may also object to certain processing activities and request data portability.

6. DATA RETENTION
We retain your data for as long as your account is active or as needed to provide the Service. You may request deletion of your data at any time.

7. COOKIES AND TRACKING
We use essential cookies for authentication and session management, and analytics cookies to understand how our Service is used.

8. CONTACT
For privacy-related inquiries, contact our Data Protection Officer at privacy@parwa.ai.`,
  },
  {
    id: 'ai_data' as const,
    icon: Brain,
    title: 'AI Data Processing',
    description:
      'Consent to AI processing of your support data, including ticket content and customer communications, to generate automated responses and improve AI accuracy over time. Your data is never shared with third parties for model training.',
    fullText: `PARWA AI DATA PROCESSING CONSENT

Last Updated: January 2025

1. SCOPE OF AI PROCESSING
By accepting this consent, you authorize PARWA to process your customer support data, including ticket content, customer messages, response drafts, and knowledge base documents through our AI systems.

2. PURPOSE OF PROCESSING
AI processing is used to: generate automated responses to customer inquiries, classify and route support tickets, extract insights and analytics from support data, improve AI model accuracy and response quality, and provide real-time suggestions to support agents.

3. DATA HANDLING
All AI processing occurs within PARWA's secure infrastructure. Your data is encrypted during processing and is not persisted beyond the necessary processing window unless you explicitly save AI-generated content.

4. NO THIRD-PARTY TRAINING
Your data is never shared with third parties for AI model training purposes. PARWA uses your data solely to provide the Service to your organization.

5. HUMAN OVERSIGHT
All AI-generated responses include human review mechanisms. You can configure the level of AI autonomy, including mandatory human approval before responses are sent to customers.

6. OPT-OUT
You may withdraw this consent at any time by disabling AI features in your account settings. Withdrawal of consent does not affect the lawfulness of processing prior to withdrawal.

7. DATA MINIMIZATION
We process only the minimum data necessary to provide AI features. Sensitive personal data receives additional protections and is excluded from AI training processes.

8. AUDIT AND TRANSPARENCY
You may request an audit of AI processing activities involving your data. PARWA maintains logs of all AI decisions and provides explanations of automated processing upon request.`,
  },
];

/**
 * LegalConsentStep Component (Step 2)
 *
 * Collects three mandatory legal consents from the user before
 * they can proceed in the onboarding wizard. Each consent is
 * displayed as an interactive card with a checkbox, title,
 * description, and a link to view the full policy text in a
 * modal overlay. The "Accept & Continue" button only becomes
 * enabled when all three checkboxes are checked, enforcing
 * the requirement that users must accept all policies (F-029).
 */
export function LegalConsentStep({ onNext }: LegalConsentStepProps) {
  const [consents, setConsents] = useState({
    terms: false,
    privacy: false,
    ai_data: false,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeModal, setActiveModal] = useState<'terms' | 'privacy' | 'ai_data' | null>(null);

  const allAccepted = consents.terms && consents.privacy && consents.ai_data;

  const toggleConsent = (id: 'terms' | 'privacy' | 'ai_data') => {
    setConsents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSubmit = async () => {
    if (!allAccepted || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onboardingApi.submitLegal({
        accept_terms: consents.terms,
        accept_privacy: consents.privacy,
        accept_ai_data: consents.ai_data,
      });
      await onboardingApi.completeStep(2);
      toast.success('Legal consents accepted');
      onNext();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const activePolicy = CONSENT_CARDS.find((c) => c.id === activeModal);

  return (
    <div className="max-w-xl mx-auto">
      {/* Header */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/20 mb-6">
          <ShieldCheck className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
          Legal Agreements
        </h2>
        <p className="text-orange-200/50 text-sm">
          Please review and accept the following agreements to continue setting up your account.
          All three are required before you can proceed.
        </p>
      </div>

      {/* Consent cards */}
      <div className="space-y-4">
        {CONSENT_CARDS.map((card) => {
          const Icon = card.icon;
          const isChecked = consents[card.id];

          return (
            <div
              key={card.id}
              className={cn(
                'card-parwa p-6 transition-all duration-300',
                isChecked && 'border-orange-500/30 bg-orange-500/[0.04]'
              )}
            >
              <div className="flex items-start gap-4">
                {/* Checkbox */}
                <button
                  type="button"
                  onClick={() => toggleConsent(card.id)}
                  className={cn(
                    'mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all duration-200',
                    isChecked
                      ? 'bg-orange-500 border-orange-500'
                      : 'border-white/20 hover:border-orange-400/50'
                  )}
                  aria-label={`Accept ${card.title}`}
                  aria-checked={isChecked}
                  role="checkbox"
                >
                  {isChecked && (
                    <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>

                {/* Card content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="w-4 h-4 text-orange-400 flex-shrink-0" />
                    <h3 className="text-sm font-semibold text-white">{card.title}</h3>
                  </div>
                  <p className="text-xs text-orange-200/40 leading-relaxed mb-2">
                    {card.description}
                  </p>
                  <button
                    type="button"
                    onClick={() => setActiveModal(card.id)}
                    className="inline-flex items-center gap-1 text-xs text-orange-400 hover:text-orange-300 transition-colors"
                  >
                    Read Full Policy
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action button */}
      <div className="mt-8 flex items-center justify-center">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!allAccepted || isSubmitting}
          className="btn-primary-parwa py-3 px-8 w-full sm:w-auto"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Accepting...
            </>
          ) : (
            <>
              Accept & Continue
              <ArrowRight className="w-5 h-5 ml-2" />
            </>
          )}
        </button>
      </div>

      {/* Policy modal overlay */}
      {activeModal && activePolicy && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
          onClick={() => setActiveModal(null)}
        >
          <div
            className="card-elevated-parwa p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto scrollbar-premium"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white">{activePolicy.title}</h3>
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                aria-label="Close modal"
              >
                <X className="w-4 h-4 text-white/60" />
              </button>
            </div>
            <div className="text-sm text-orange-200/60 whitespace-pre-wrap leading-relaxed">
              {activePolicy.fullText}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default LegalConsentStep;
