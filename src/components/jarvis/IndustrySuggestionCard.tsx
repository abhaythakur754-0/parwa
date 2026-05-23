/**
 * PARWA IndustrySuggestionCard (Integration Setup)
 *
 * Suggests popular integrations based on the user's industry.
 * Clickable suggestion chips that pre-fill the provider selector.
 * Rendered inline in the Jarvis chat stream during onboarding.
 */

'use client';

import { Lightbulb, ChevronRight } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────

export interface IndustrySuggestion {
  providerType: string;   // "shopify", "stripe", etc.
  providerName: string;   // "Shopify", "Stripe", etc.
  category: string;       // "ecommerce", "payment", etc.
  icon?: string;          // emoji or text
}

export interface IndustrySuggestionCardProps {
  industry: string;
  suggestions: IndustrySuggestion[];
  onSelectSuggestion: (providerType: string, category: string) => void;
  onDismiss?: () => void;
}

// ── Fallback industry suggestions ──────────────────────────────────

const FALLBACK_SUGGESTIONS: Record<string, IndustrySuggestion[]> = {
  'e-commerce': [
    { providerType: 'shopify',       providerName: 'Shopify',      category: 'ecommerce',     icon: '🛍️' },
    { providerType: 'zendesk',       providerName: 'Zendesk',      category: 'helpdesk',      icon: '🎧' },
    { providerType: 'stripe',        providerName: 'Stripe',       category: 'payment',       icon: '💳' },
    { providerType: 'woocommerce',   providerName: 'WooCommerce',  category: 'ecommerce',     icon: '🛒' },
  ],
  'saas': [
    { providerType: 'slack',         providerName: 'Slack',        category: 'communication', icon: '💬' },
    { providerType: 'hubspot',       providerName: 'HubSpot',      category: 'crm',           icon: '🎯' },
    { providerType: 'stripe',        providerName: 'Stripe',       category: 'payment',       icon: '💳' },
    { providerType: 'sendgrid',      providerName: 'SendGrid',     category: 'email',         icon: '📧' },
  ],
  'logistics': [
    { providerType: 'sap',           providerName: 'SAP',          category: 'crm',           icon: '📦' },
    { providerType: 'salesforce',    providerName: 'Salesforce',   category: 'crm',           icon: '☁️' },
    { providerType: 'twilio',        providerName: 'Twilio',       category: 'sms',           icon: '📱' },
  ],
  'healthcare': [
    { providerType: 'salesforce',    providerName: 'Salesforce',   category: 'crm',           icon: '☁️' },
    { providerType: 'brevo',         providerName: 'Brevo',        category: 'email',         icon: '📧' },
    { providerType: 'zoom',          providerName: 'Zoom',         category: 'communication', icon: '📹' },
  ],
  'real-estate': [
    { providerType: 'hubspot',       providerName: 'HubSpot',      category: 'crm',           icon: '🎯' },
    { providerType: 'twilio',        providerName: 'Twilio',       category: 'sms',           icon: '📱' },
    { providerType: 'sendgrid',      providerName: 'SendGrid',     category: 'email',         icon: '📧' },
  ],
  'education': [
    { providerType: 'slack',         providerName: 'Slack',        category: 'communication', icon: '💬' },
    { providerType: 'stripe',        providerName: 'Stripe',       category: 'payment',       icon: '💳' },
    { providerType: 'microsoft_teams', providerName: 'Microsoft Teams', category: 'communication', icon: '👥' },
  ],
  'default': [
    { providerType: 'brevo',         providerName: 'Brevo',        category: 'email',         icon: '📧' },
    { providerType: 'stripe',        providerName: 'Stripe',       category: 'payment',       icon: '💳' },
    { providerType: 'hubspot',       providerName: 'HubSpot',      category: 'crm',           icon: '🎯' },
  ],
};

const CATEGORY_LABELS: Record<string, string> = {
  email: 'Email',
  sms: 'SMS',
  payment: 'Payment',
  crm: 'CRM',
  ecommerce: 'E-Commerce',
  helpdesk: 'Help Desk',
  communication: 'Communication',
};

// ── Component ──────────────────────────────────────────────────────

export function IndustrySuggestionCard({
  industry,
  suggestions,
  onSelectSuggestion,
  onDismiss,
}: IndustrySuggestionCardProps) {
  // Use provided suggestions or fall back to industry defaults
  const items = suggestions.length > 0
    ? suggestions
    : (FALLBACK_SUGGESTIONS[industry.toLowerCase()] || FALLBACK_SUGGESTIONS['default']);

  const displayIndustry = industry
    ? industry.charAt(0).toUpperCase() + industry.slice(1).replace(/-/g, ' ')
    : 'Your Industry';

  // Group by category for display
  const grouped = items.reduce<Record<string, IndustrySuggestion[]>>((acc, item) => {
    const key = item.category;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="glass rounded-xl p-4 border border-amber-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
          <Lightbulb className="w-4 h-4 text-amber-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Recommended for You</h3>
          <p className="text-[10px] text-white/40">Popular integrations for {displayIndustry}</p>
        </div>
      </div>

      {/* Grouped suggestions */}
      <div className="space-y-2.5 mb-3">
        {Object.entries(grouped).map(([category, providers]) => (
          <div key={category}>
            <p className="text-[10px] text-white/30 uppercase tracking-wider mb-1.5">
              Popular for {CATEGORY_LABELS[category] || category}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {providers.map((provider) => (
                <button
                  key={provider.providerType}
                  onClick={() => onSelectSuggestion(provider.providerType, provider.category)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white/70 text-xs hover:bg-amber-500/10 hover:border-amber-500/20 hover:text-amber-200 transition-all active:scale-[0.97] group"
                >
                  {provider.icon && (
                    <span className="text-xs">{provider.icon}</span>
                  )}
                  <span className="font-medium">{provider.providerName}</span>
                  <ChevronRight className="w-2.5 h-2.5 text-white/20 group-hover:text-amber-300/60 transition-colors" />
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Dismiss */}
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="w-full flex items-center justify-center text-[11px] text-white/30 hover:text-white/50 transition-colors py-1"
        >
          No thanks, I&apos;ll choose manually
        </button>
      )}
    </div>
  );
}
