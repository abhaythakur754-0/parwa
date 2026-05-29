/**
 * PARWA IntegrationSummaryCard (Integration Setup)
 *
 * Summary card showing all connected and skipped integrations.
 * Industry-aware suggestions and "continue" actions.
 * Rendered inline in the Jarvis chat stream during onboarding.
 */

'use client';

import {
  CheckCircle2, SkipForward, Plus, ArrowRight,
  Sparkles, LayoutGrid,
} from 'lucide-react';
import { useState } from 'react';

// ── Types ──────────────────────────────────────────────────────────

export interface ConnectedIntegration {
  category: string;
  provider: string;
  status: string;
}

export interface SkippedIntegration {
  category: string;
}

export interface IntegrationSummaryCardProps {
  connected: ConnectedIntegration[];
  skipped: SkippedIntegration[];
  industry: string;
  onAddMore: () => void;
  onContinue: () => void;
}

// ── Category display names ─────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  email: 'Email',
  sms: 'SMS',
  payment: 'Payment',
  crm: 'CRM',
  ecommerce: 'E-Commerce',
  helpdesk: 'Help Desk',
  communication: 'Communication',
};

// ── Industry suggestions ───────────────────────────────────────────

const INDUSTRY_SUGGESTIONS: Record<string, { category: string; providers: string[] }[]> = {
  'e-commerce': [
    { category: 'payment', providers: ['Stripe', 'PayPal'] },
    { category: 'ecommerce', providers: ['Shopify', 'WooCommerce'] },
    { category: 'helpdesk', providers: ['Zendesk', 'Freshdesk'] },
  ],
  'saas': [
    { category: 'email', providers: ['SendGrid', 'Brevo'] },
    { category: 'crm', providers: ['HubSpot', 'Salesforce'] },
    { category: 'communication', providers: ['Slack', 'Discord'] },
  ],
  'logistics': [
    { category: 'crm', providers: ['Salesforce', 'SAP'] },
    { category: 'communication', providers: ['Slack', 'Microsoft Teams'] },
    { category: 'sms', providers: ['Twilio', 'Vonage'] },
  ],
  'healthcare': [
    { category: 'email', providers: ['Brevo', 'Mailgun'] },
    { category: 'crm', providers: ['Salesforce', 'HubSpot'] },
    { category: 'communication', providers: ['Slack', 'Zoom'] },
  ],
  'real-estate': [
    { category: 'crm', providers: ['HubSpot', 'Pipedrive'] },
    { category: 'sms', providers: ['Twilio', 'MessageBird'] },
    { category: 'email', providers: ['SendGrid', 'Brevo'] },
  ],
  'education': [
    { category: 'communication', providers: ['Slack', 'Microsoft Teams'] },
    { category: 'email', providers: ['Brevo', 'Mailgun'] },
    { category: 'payment', providers: ['Stripe', 'PayPal'] },
  ],
  'default': [
    { category: 'email', providers: ['Brevo', 'SendGrid'] },
    { category: 'payment', providers: ['Stripe'] },
    { category: 'crm', providers: ['HubSpot'] },
  ],
};

// ── Component ──────────────────────────────────────────────────────

export function IntegrationSummaryCard({
  connected,
  skipped,
  industry,
  onAddMore,
  onContinue,
}: IntegrationSummaryCardProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Get industry-specific suggestions
  const suggestions = INDUSTRY_SUGGESTIONS[industry.toLowerCase()] || INDUSTRY_SUGGESTIONS['default'];

  // Filter out already-connected categories
  const connectedCategories = new Set(connected.map((c) => c.category.toLowerCase()));
  const relevantSuggestions = suggestions.filter(
    (s) => !connectedCategories.has(s.category.toLowerCase()),
  );

  return (
    <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <LayoutGrid className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Integration Summary</h3>
          <p className="text-[10px] text-white/40">
            {connected.length} connected · {skipped.length} skipped
          </p>
        </div>
      </div>

      {/* Connected providers */}
      {connected.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">Connected</p>
          <div className="space-y-1">
            {connected.map((item, i) => (
              <div
                key={`${item.category}-${i}`}
                className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-xs text-white/80 font-medium">{item.provider}</span>
                  <span className="text-[10px] text-white/30 ml-1.5">
                    {CATEGORY_LABELS[item.category] || item.category}
                  </span>
                </div>
                <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400/70">
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skipped categories */}
      {skipped.length > 0 && (
        <div className="mb-3">
          <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">Skipped</p>
          <div className="flex flex-wrap gap-1.5">
            {skipped.map((item, i) => (
              <span
                key={`${item.category}-${i}`}
                className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-md bg-white/[0.03] border border-white/[0.06] text-white/35"
              >
                <SkipForward className="w-2.5 h-2.5" />
                {CATEGORY_LABELS[item.category] || item.category}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Industry suggestions */}
      {relevantSuggestions.length > 0 && (
        <div className="mb-3">
          <button
            onClick={() => setShowSuggestions(!showSuggestions)}
            className="w-full flex items-center gap-1.5 text-[11px] text-amber-400/60 hover:text-amber-400/80 transition-colors py-1"
          >
            <Sparkles className="w-3 h-3" />
            <span>Popular for {industry || 'your industry'}</span>
          </button>

          {showSuggestions && (
            <div className="mt-1.5 space-y-1.5">
              {relevantSuggestions.map((suggestion) => (
                <div
                  key={suggestion.category}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <span className="text-[10px] text-white/30 min-w-[60px]">
                    {CATEGORY_LABELS[suggestion.category] || suggestion.category}:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {suggestion.providers.map((p) => (
                      <span
                        key={p}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/5 text-amber-300/50 border border-amber-500/10"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {connected.length === 0 && skipped.length === 0 && (
        <div className="text-center py-3 mb-3">
          <p className="text-[11px] text-white/30">No integrations set up yet.</p>
          <p className="text-[10px] text-white/20 mt-0.5">Connect your first provider to get started.</p>
        </div>
      )}

      {/* Actions */}
      <div className="space-y-2">
        <button
          onClick={onContinue}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-xs font-medium hover:from-emerald-400 hover:to-emerald-500 transition-all active:scale-[0.98]"
        >
          All Done — Continue
          <ArrowRight className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={onAddMore}
          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/50 text-xs hover:bg-white/[0.06] hover:text-white/70 transition-all"
        >
          <Plus className="w-3 h-3" />
          Set up more integrations
        </button>
      </div>
    </div>
  );
}
