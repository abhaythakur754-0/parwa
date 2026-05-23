/**
 * PARWA ProviderSelectorCard (Integration Setup)
 *
 * Shows a list of available providers for a given category (email/sms/payment/crm/etc).
 * Rendered inline in the Jarvis chat stream during onboarding.
 * Users can select a provider, choose custom SMTP/API, or skip.
 */

'use client';

import { useState } from 'react';
import {
  Mail, MessageSquare, CreditCard, Users, ShoppingCart,
  Headphones, Radio, Settings, SkipForward, ChevronRight,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────

export interface ProviderInfo {
  type: string;       // "brevo", "sendgrid", etc.
  name: string;       // "Brevo", "SendGrid", etc.
  description: string;
  popular?: boolean;
  icon?: string;      // emoji or text
}

export interface ProviderSelectorCardProps {
  category: 'email' | 'sms' | 'payment' | 'crm' | 'ecommerce' | 'helpdesk' | 'communication';
  providers: ProviderInfo[];
  onSelect: (providerType: string) => void;
  onSkip: () => void;
}

// ── Category Config ────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; icon: typeof Mail; accent: string; accentBg: string; accentBorder: string; gradientFrom: string; gradientTo: string }> = {
  email:         { label: 'Email Provider',         icon: Mail,          accent: 'text-blue-400',       accentBg: 'bg-blue-500/10',   accentBorder: 'border-blue-500/15',   gradientFrom: 'from-blue-500',   gradientTo: 'to-blue-600' },
  sms:           { label: 'SMS Provider',           icon: MessageSquare, accent: 'text-green-400',      accentBg: 'bg-green-500/10',  accentBorder: 'border-green-500/15',  gradientFrom: 'from-green-500',  gradientTo: 'to-green-600' },
  payment:       { label: 'Payment Provider',       icon: CreditCard,    accent: 'text-amber-400',      accentBg: 'bg-amber-500/10',  accentBorder: 'border-amber-500/15',  gradientFrom: 'from-amber-500',  gradientTo: 'to-amber-600' },
  crm:           { label: 'CRM',                    icon: Users,         accent: 'text-purple-400',     accentBg: 'bg-purple-500/10', accentBorder: 'border-purple-500/15', gradientFrom: 'from-purple-500', gradientTo: 'to-purple-600' },
  ecommerce:     { label: 'E-Commerce Platform',    icon: ShoppingCart,  accent: 'text-teal-400',       accentBg: 'bg-teal-500/10',   accentBorder: 'border-teal-500/15',   gradientFrom: 'from-teal-500',   gradientTo: 'to-teal-600' },
  helpdesk:      { label: 'Help Desk',              icon: Headphones,    accent: 'text-rose-400',       accentBg: 'bg-rose-500/10',   accentBorder: 'border-rose-500/15',   gradientFrom: 'from-rose-500',   gradientTo: 'to-rose-600' },
  communication: { label: 'Communication Platform', icon: Radio,         accent: 'text-indigo-400',     accentBg: 'bg-indigo-500/10', accentBorder: 'border-indigo-500/15', gradientFrom: 'from-indigo-500', gradientTo: 'to-indigo-600' },
};

// ── Component ──────────────────────────────────────────────────────

export function ProviderSelectorCard({
  category,
  providers,
  onSelect,
  onSkip,
}: ProviderSelectorCardProps) {
  const [hoveredProvider, setHoveredProvider] = useState<string | null>(null);
  const config = CATEGORY_CONFIG[category] ?? CATEGORY_CONFIG.email;
  const Icon = config.icon;

  // Sort: popular first
  const sorted = [...providers].sort((a, b) => (b.popular ? 1 : 0) - (a.popular ? 1 : 0));

  return (
    <div className={`glass rounded-xl p-4 border ${config.accentBorder} max-w-sm w-full`}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className={`w-8 h-8 rounded-lg ${config.accentBg} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${config.accent}`} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Choose Your {config.label}</h3>
          <p className="text-[10px] text-white/40">{providers.length} provider{providers.length !== 1 ? 's' : ''} available</p>
        </div>
      </div>

      {/* Provider List */}
      <div className="space-y-1.5 mb-3 max-h-[260px] overflow-y-auto scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
        {sorted.map((provider) => (
          <button
            key={provider.type}
            onClick={() => onSelect(provider.type)}
            onMouseEnter={() => setHoveredProvider(provider.type)}
            onMouseLeave={() => setHoveredProvider(null)}
            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg transition-all text-left group ${
              hoveredProvider === provider.type
                ? 'bg-white/[0.06] border border-white/10'
                : 'bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.05]'
            }`}
          >
            {/* Icon */}
            <div className={`w-8 h-8 rounded-lg ${config.accentBg} flex items-center justify-center shrink-0 text-base`}>
              {provider.icon || provider.name.charAt(0)}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-white/90 truncate">{provider.name}</span>
                {provider.popular && (
                  <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${config.accentBg} ${config.accent} border ${config.accentBorder}`}>
                    Popular
                  </span>
                )}
              </div>
              <p className="text-[10px] text-white/35 truncate">{provider.description}</p>
            </div>

            {/* Arrow */}
            <ChevronRight className={`w-3.5 h-3.5 text-white/20 transition-all shrink-0 ${
              hoveredProvider === provider.type ? 'text-white/40 translate-x-0.5' : ''
            }`} />
          </button>
        ))}
      </div>

      {/* Custom SMTP/API Option */}
      <button
        onClick={() => onSelect('custom')}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-dashed border-white/10 hover:bg-white/[0.05] transition-all mb-2 text-left"
      >
        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
          <Settings className="w-3.5 h-3.5 text-white/40" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-xs font-medium text-white/60">Custom SMTP / API</span>
          <p className="text-[10px] text-white/25">Connect your own provider</p>
        </div>
      </button>

      {/* Skip */}
      <button
        onClick={onSkip}
        className="w-full flex items-center justify-center gap-1.5 text-[11px] text-white/35 hover:text-white/55 transition-colors py-1.5"
      >
        <SkipForward className="w-3 h-3" />
        Skip for now
      </button>
    </div>
  );
}
