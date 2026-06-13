'use client';

import React, { useState } from 'react';
import { Loader2, CheckCircle2, Shield, Scale, FileText, Lock } from 'lucide-react';

interface LegalComplianceProps {
  onComplete: () => void;
  isSubmitting?: boolean;
}

export function LegalCompliance({ onComplete, isSubmitting = false }: LegalComplianceProps) {
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptAiData, setAcceptAiData] = useState(false);
  const [acceptDpa, setAcceptDpa] = useState(false);
  const [acceptSla, setAcceptSla] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const allAccepted = acceptTerms && acceptPrivacy && acceptAiData && acceptDpa && acceptSla;

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
          accept_dpa: acceptDpa,
          accept_sla: acceptSla,
        }),
      });

      if (!res.ok) {
        console.warn('Legal consent API returned non-ok, continuing locally');
      }

      onComplete();
    } catch {
      console.warn('Legal consent API unavailable, completing locally');
      onComplete();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
          <Shield className="w-7 h-7 text-blue-400" />
        </div>
        <h2 className="text-2xl font-bold text-white">Legal Compliance</h2>
        <p className="text-orange-200/40 text-sm">
          Review and accept our policies to continue. Scroll through each section to read the full details.
        </p>
      </div>

      {/* All legal cards in a single scrollable container */}
      <div className="space-y-3 max-h-[55vh] overflow-y-auto pr-1 custom-scrollbar">
        {/* 1. Terms of Service */}
        <LegalCard
          id="terms"
          checked={acceptTerms}
          onChange={setAcceptTerms}
          title="Terms of Service"
          icon={<FileText className="w-5 h-5 text-blue-400" />}
          summary="Governs your use of PARWA's platform, including service commitments, acceptable use, and liability."
        >
          <div className="space-y-3 text-xs text-orange-200/40 leading-relaxed">
            <p><strong className="text-orange-200/60">1. Acceptance of Terms.</strong> By accessing or using PARWA (&quot;the Service&quot;), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service. These Terms apply to all visitors, users, and others who access or use the Service.</p>
            <p><strong className="text-orange-200/60">2. Description of Service.</strong> PARWA provides an AI-powered customer support platform that enables businesses to automate, manage, and optimize customer interactions through intelligent ticket routing, AI-generated responses, knowledge base management, real-time analytics, and multi-channel communication integrations.</p>
            <p><strong className="text-orange-200/60">3. Account Registration.</strong> You must register for an account to use the Service. You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You must immediately notify PARWA of any unauthorized use of your account.</p>
            <p><strong className="text-orange-200/60">4. Acceptable Use.</strong> You agree not to use the Service for any unlawful purpose, not to attempt to gain unauthorized access to any portion of the Service, not to use the Service to transmit any harmful, threatening, or objectionable content, and not to interfere with or disrupt the Service or servers connected to the Service.</p>
            <p><strong className="text-orange-200/60">5. Payment & Billing.</strong> Subscription fees are billed in advance on a monthly or annual basis. All fees are non-refundable except as expressly stated. PARWA reserves the right to change pricing with 30 days&apos; written notice. Overages beyond your plan limits are billed at the per-ticket rate specified in your plan.</p>
            <p><strong className="text-orange-200/60">6. Intellectual Property.</strong> You retain all rights to your content, data, and knowledge base materials uploaded to the Service. PARWA retains all rights to the Service, including software, design, and branding. You grant PARWA a limited license to process your content solely for the purpose of providing the Service.</p>
            <p><strong className="text-orange-200/60">7. Limitation of Liability.</strong> PARWA shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising out of or relating to your use of the Service. PARWA&apos;s total liability shall not exceed the amount paid by you in the 12 months preceding the claim.</p>
            <p><strong className="text-orange-200/60">8. Termination.</strong> Either party may terminate the agreement with 30 days&apos; written notice. PARWA may suspend or terminate your access immediately for breach of these Terms. Upon termination, your data will be retained for 30 days and then permanently deleted unless you request an export.</p>
            <p><strong className="text-orange-200/60">9. Modifications.</strong> PARWA may modify these Terms at any time. Material changes will be communicated via email with at least 30 days&apos; notice. Continued use of the Service after modifications constitutes acceptance of the revised Terms.</p>
            <p><strong className="text-orange-200/60">10. Governing Law.</strong> These Terms shall be governed by and construed in accordance with the laws of the jurisdiction in which PARWA is incorporated, without regard to conflict of law principles.</p>
          </div>
        </LegalCard>

        {/* 2. Privacy Policy */}
        <LegalCard
          id="privacy"
          checked={acceptPrivacy}
          onChange={setAcceptPrivacy}
          title="Privacy Policy"
          icon={<Shield className="w-5 h-5 text-emerald-400" />}
          summary="How we collect, process, store, and protect your data in compliance with GDPR, CCPA, and applicable regulations."
        >
          <div className="space-y-3 text-xs text-orange-200/40 leading-relaxed">
            <p><strong className="text-orange-200/60">1. Data We Collect.</strong> We collect account information (name, email, company name), usage data (interaction logs, support tickets processed, AI query volumes), integration credentials (API keys stored encrypted, never logged in plaintext), knowledge base documents you upload, and billing information processed through our payment provider (we never store full card numbers).</p>
            <p><strong className="text-orange-200/60">2. How We Use Your Data.</strong> Your data is used to provide and improve the Service, train AI models within your isolated tenant environment, process and route customer support tickets, generate analytics and reports, and communicate service updates and billing information. We never sell your data to third parties.</p>
            <p><strong className="text-orange-200/60">3. Data Processing & AI.</strong> Customer interactions processed by PARWA&apos;s AI are handled within your isolated tenant environment. AI model training occurs on aggregated, anonymized data. You can opt out of contributing to model improvements. Conversation logs are retained per your configured retention policy.</p>
            <p><strong className="text-orange-200/60">4. Data Storage & Security.</strong> All data is encrypted at rest (AES-256) and in transit (TLS 1.3). Integration credentials are encrypted with per-tenant keys. We maintain SOC 2 Type II compliance and undergo regular third-party security audits. Data is stored in your selected region with automatic backups.</p>
            <p><strong className="text-orange-200/60">5. Data Retention.</strong> Account data is retained for the duration of your subscription. Upon account deletion, data is purged within 30 days. Conversation logs follow your configured retention period (default 90 days). Knowledge base documents are deleted immediately upon removal request.</p>
            <p><strong className="text-orange-200/60">6. Your Rights (GDPR/CCPA).</strong> You have the right to access, correct, delete, and port your personal data. You may object to processing, restrict processing, and withdraw consent at any time. California residents have additional rights under CCPA including the right to know, delete, and opt-out of sale. We do not sell personal information.</p>
            <p><strong className="text-orange-200/60">7. Third-Party Services.</strong> We integrate with third-party services at your direction. When you connect an integration, your credentials and data are processed according to that service&apos;s privacy policy as well as ours. We act as a data processor on your behalf for connected services.</p>
            <p><strong className="text-orange-200/60">8. International Transfers.</strong> If your data is transferred outside your region, we ensure appropriate safeguards are in place including Standard Contractual Clauses, adequacy decisions, or other legally recognized transfer mechanisms.</p>
            <p><strong className="text-orange-200/60">9. Cookies & Tracking.</strong> We use essential cookies for authentication and session management. Analytics cookies are optional and can be disabled. We do not use tracking cookies for advertising purposes.</p>
            <p><strong className="text-orange-200/60">10. Contact.</strong> For privacy-related inquiries, contact our Data Protection Officer at privacy@parwa.ai. We will respond to verified requests within 30 days.</p>
          </div>
        </LegalCard>

        {/* 3. AI Data Processing Agreement */}
        <LegalCard
          id="ai-data"
          checked={acceptAiData}
          onChange={setAcceptAiData}
          title="AI Data Processing Agreement"
          icon={<Scale className="w-5 h-5 text-violet-400" />}
          summary="Consent for AI processing of your data, model training scope, data isolation, and your ownership rights."
        >
          <div className="space-y-3 text-xs text-orange-200/40 leading-relaxed">
            <p><strong className="text-orange-200/60">1. Scope of Processing.</strong> PARWA processes your uploaded knowledge base documents, customer conversation logs, AI interaction metadata, and configured response templates solely to provide the AI-powered customer support service as described in your subscription plan.</p>
            <p><strong className="text-orange-200/60">2. Data Isolation.</strong> Your data is processed within an isolated tenant environment. Your knowledge base, conversations, and AI configurations are not shared with or accessible by other PARWA customers. Cross-tenant data leakage is prevented through tenant-level encryption and access controls.</p>
            <p><strong className="text-orange-200/60">3. AI Model Training.</strong> By default, anonymized and aggregated patterns from your usage may contribute to improving PARWA&apos;s base AI models. You may opt out of this contribution at any time through your account settings. When opted out, your data is never used for any model improvement purpose. Opting out does not affect the quality of AI responses you receive.</p>
            <p><strong className="text-orange-200/60">4. Data Ownership.</strong> You retain full ownership of all data you provide to PARWA, including knowledge base documents, conversation logs, and AI configurations. PARWA claims no ownership rights over your content. Upon request, we will export or delete your data within 30 days.</p>
            <p><strong className="text-orange-200/60">5. Automated Decision-Making.</strong> PARWA&apos;s AI may make automated decisions in customer support interactions (e.g., ticket routing, response suggestions, priority classification). These decisions are based on your configured rules and AI training data within your tenant. You have the right to review and override any automated decision.</p>
            <p><strong className="text-orange-200/60">6. Human Oversight.</strong> You maintain full control over AI responses through configurable approval workflows, tone settings, and escalation rules. The AI operates within boundaries you define. Any response can be reviewed, modified, or rejected by your human agents before delivery to customers.</p>
            <p><strong className="text-orange-200/60">7. Bias & Fairness.</strong> PARWA implements bias detection and mitigation in its AI models. We conduct regular fairness audits and publish transparency reports. If you identify biased behavior in your AI responses, please report it immediately so we can investigate and remediate.</p>
            <p><strong className="text-orange-200/60">8. Subprocessors.</strong> PARWA uses cloud infrastructure providers and AI/ML service providers as subprocessors. A current list of subprocessors is available at parwa.ai/subprocessors. We notify customers of any subprocessor changes 30 days in advance.</p>
            <p><strong className="text-orange-200/60">9. Data Breach Notification.</strong> In the event of a data breach affecting your data, PARWA will notify you within 72 hours of discovery, provide details of the breach, and take immediate remedial action as required by applicable law.</p>
            <p><strong className="text-orange-200/60">10. Audit Rights.</strong> You have the right to audit PARWA&apos;s data processing practices, subject to reasonable notice and confidentiality obligations. We facilitate audits through independent third-party reports (SOC 2, ISO 27001) available upon request.</p>
          </div>
        </LegalCard>

        {/* 4. Data Processing Agreement (DPA) */}
        <LegalCard
          id="dpa"
          checked={acceptDpa}
          onChange={setAcceptDpa}
          title="Data Processing Agreement"
          icon={<Lock className="w-5 h-5 text-cyan-400" />}
          summary="Formal DPA covering data processing roles, security measures, breach notification, and compliance obligations."
        >
          <div className="space-y-3 text-xs text-orange-200/40 leading-relaxed">
            <p><strong className="text-orange-200/60">1. Parties & Roles.</strong> You (the &quot;Data Controller&quot;) determine the purposes and means of processing personal data. PARWA (the &quot;Data Processor&quot;) processes personal data on your behalf in accordance with your instructions and this Agreement. This DPA supplements the Terms of Service and Privacy Policy.</p>
            <p><strong className="text-orange-200/60">2. Processing Instructions.</strong> PARWA processes personal data only as instructed by you through the Service&apos;s configuration options, for the purposes described in the Terms, as required by applicable law, or as necessary for the performance of the Service.</p>
            <p><strong className="text-orange-200/60">3. Security Measures.</strong> PARWA implements appropriate technical and organizational measures including encryption at rest and in transit, access controls and authentication, regular security assessments, employee training on data protection, incident response procedures, and business continuity plans.</p>
            <p><strong className="text-orange-200/60">4. Subprocessing.</strong> PARWA may engage subprocessors only with your prior authorization (given through the Terms). All subprocessors are bound by equivalent data protection obligations. PARWA remains liable for subprocessor compliance.</p>
            <p><strong className="text-orange-200/60">5. International Transfers.</strong> For transfers outside the EEA/UK, PARWA ensures compliance through Standard Contractual Clauses (SCCs), adequacy decisions, or Binding Corporate Rules as applicable. Transfer impact assessments are conducted for high-risk transfers.</p>
            <p><strong className="text-orange-200/60">6. Breach Notification.</strong> PARWA notifies you of a personal data breach within 72 hours of becoming aware, including the nature of the breach, categories and approximate number of data subjects, likely consequences, and measures taken or proposed to address the breach.</p>
            <p><strong className="text-orange-200/60">7. Deletion & Return.</strong> Upon termination of the Service, PARWA deletes or returns all personal data within 30 days at your election, except where retention is required by law. Confirmation of deletion is provided upon request.</p>
            <p><strong className="text-orange-200/60">8. Cooperation & Audits.</strong> PARWA cooperates with supervisory authorities and data protection impact assessments. Annual third-party audit reports are available upon request. You may conduct or commission audits with reasonable notice.</p>
          </div>
        </LegalCard>

        {/* 5. Service Level Agreement */}
        <LegalCard
          id="sla"
          checked={acceptSla}
          onChange={setAcceptSla}
          title="Service Level Agreement"
          icon={<Scale className="w-5 h-5 text-amber-400" />}
          summary="Uptime guarantees, response time commitments, support tiers, and incident management procedures."
        >
          <div className="space-y-3 text-xs text-orange-200/40 leading-relaxed">
            <p><strong className="text-orange-200/60">1. Uptime Guarantee.</strong> PARWA commits to 99.9% uptime for the core platform (API, dashboard, AI processing). Uptime is measured monthly excluding scheduled maintenance windows. The AI response service commits to 99.5% availability.</p>
            <p><strong className="text-orange-200/60">2. Maintenance Windows.</strong> Scheduled maintenance occurs during off-peak hours (Sunday 02:00-06:00 UTC) with 48 hours advance notice. Emergency maintenance may be performed without notice for critical security issues. Maximum 4 scheduled maintenance windows per month.</p>
            <p><strong className="text-orange-200/60">3. Response Time Targets.</strong> AI-generated responses target under 2 seconds for standard queries. Dashboard API responses target under 500ms. Knowledge base search targets under 1 second. These are targets, not guarantees, and may vary based on complexity and load.</p>
            <p><strong className="text-orange-200/60">4. Support Tiers.</strong> Mini PARWA: Email support, 24-hour response time during business hours. PARWA: Email + chat support, 4-hour response time, business hours. PARWA High: Email + chat + phone support, 1-hour response time, 24/7 availability. Critical issues (platform down) receive priority across all tiers.</p>
            <p><strong className="text-orange-200/60">5. Incident Management.</strong> PARWA maintains an incident response team available 24/7 for critical issues. Incidents are classified as Critical (service unavailable), High (major feature impaired), Medium (feature degraded), and Low (minor issue). Status updates are provided via status.parwa.ai.</p>
            <p><strong className="text-orange-200/60">6. Service Credits.</strong> If uptime falls below 99.9% in a month, you are eligible for service credits: 99.0-99.9% = 10% credit; 95.0-99.0% = 25% credit; below 95% = 50% credit. Credits must be requested within 30 days and apply to future invoices. Maximum credit is 50% of monthly fees.</p>
            <p><strong className="text-orange-200/60">7. Exclusions.</strong> The SLA does not cover issues caused by third-party services or integrations, customer misconfiguration, force majeure events, or internet connectivity issues outside PARWA&apos;s infrastructure. Downtime during scheduled maintenance is excluded from uptime calculations.</p>
          </div>
        </LegalCard>
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

      {/* Custom scrollbar styles */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255,127,17,0.2);
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255,127,17,0.4);
        }
      `}</style>
    </div>
  );
}

// ── Legal Card Component ────────────────────────────────────────────────

function LegalCard({
  id,
  checked,
  onChange,
  title,
  icon,
  summary,
  children,
}: {
  id: string;
  checked: boolean;
  onChange: (val: boolean) => void;
  title: string;
  icon: React.ReactNode;
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl border transition-all duration-200"
      style={{
        background: checked ? 'rgba(255,127,17,0.05)' : 'rgba(255,255,255,0.03)',
        borderColor: checked ? 'rgba(255,127,17,0.3)' : 'rgba(255,255,255,0.08)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 p-4">
        <button
          type="button"
          onClick={() => onChange(!checked)}
          className={`w-5 h-5 rounded flex items-center justify-center shrink-0 transition-all ${
            checked
              ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-white'
              : 'border border-white/20 hover:border-orange-400/50'
          }`}
        >
          {checked && <CheckCircle2 className="w-3.5 h-3.5" />}
        </button>
        <div className="flex items-center gap-2 flex-1">
          {icon}
          <span className="text-sm font-medium text-white">{title}</span>
        </div>
      </div>

      {/* Summary */}
      <div className="px-4 pb-2">
        <p className="text-xs text-orange-200/30">{summary}</p>
      </div>

      {/* Scrollable legal content — always visible */}
      <div className="mx-4 mb-4 p-3 rounded-lg text-xs leading-relaxed max-h-48 overflow-y-auto custom-scrollbar" style={{ background: 'rgba(255,255,255,0.03)' }}>
        {children}
      </div>
    </div>
  );
}
