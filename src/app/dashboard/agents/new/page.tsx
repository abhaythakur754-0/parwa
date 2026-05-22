/**
 * Create New Agent Page (/dashboard/agents/new)
 *
 * Form for creating a new AI agent with name, type, variant tier,
 * domain, and personality/tone configuration.
 * Saves to localStorage and redirects back to /dashboard/agents.
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Bot,
  ArrowLeft,
  Save,
  Loader2,
  Zap,
  Shield,
  Cpu,
  MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';

// ── Types ────────────────────────────────────────────────────────────

type AgentType = 'support' | 'sales' | 'technical' | 'general';
type VariantTier = 'light' | 'medium' | 'heavy';

interface AgentFormData {
  name: string;
  type: AgentType;
  variantTier: VariantTier;
  domain: string;
  personality: string;
}

// ── Constants ────────────────────────────────────────────────────────

const AGENT_TYPES: { value: AgentType; label: string; description: string; icon: React.ReactNode }[] = [
  {
    value: 'support',
    label: 'Support',
    description: 'Customer support, FAQ handling, issue resolution',
    icon: <Shield className="w-4 h-4" />,
  },
  {
    value: 'sales',
    label: 'Sales',
    description: 'Lead qualification, product recommendations, upselling',
    icon: <Zap className="w-4 h-4" />,
  },
  {
    value: 'technical',
    label: 'Technical',
    description: 'Deep technical troubleshooting, debugging assistance',
    icon: <Cpu className="w-4 h-4" />,
  },
  {
    value: 'general',
    label: 'General',
    description: 'General-purpose assistant for mixed workloads',
    icon: <MessageSquare className="w-4 h-4" />,
  },
];

const VARIANT_TIERS: { value: VariantTier; label: string; description: string; price: string }[] = [
  {
    value: 'light',
    label: 'Mini PARWA',
    description: 'Lightweight — 5 techniques, simple reasoning, 500 tickets/day',
    price: '$999/mo',
  },
  {
    value: 'medium',
    label: 'PARWA',
    description: 'Standard — 15 techniques, RAG support, basic escalation, 5K tickets/day',
    price: '$2,499/mo',
  },
  {
    value: 'heavy',
    label: 'PARWA High',
    description: 'Premium — 27 techniques, deep reasoning, advanced escalation, unlimited',
    price: '$3,999/mo',
  },
];

const tierColors: Record<VariantTier, string> = {
  light: 'border-zinc-500/30 bg-zinc-500/5 hover:border-zinc-500/50',
  medium: 'border-orange-500/30 bg-orange-500/5 hover:border-orange-500/50',
  heavy: 'border-purple-500/30 bg-purple-500/5 hover:border-purple-500/50',
};

const tierSelectedColors: Record<VariantTier, string> = {
  light: 'border-zinc-400 bg-zinc-500/10 ring-1 ring-zinc-400/50',
  medium: 'border-orange-400 bg-orange-500/10 ring-1 ring-orange-400/50',
  heavy: 'border-purple-400 bg-purple-500/10 ring-1 ring-purple-400/50',
};

const typeColors: Record<AgentType, string> = {
  support: 'border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/50',
  sales: 'border-amber-500/30 bg-amber-500/5 hover:border-amber-500/50',
  technical: 'border-purple-500/30 bg-purple-500/5 hover:border-purple-500/50',
  general: 'border-zinc-500/30 bg-zinc-500/5 hover:border-zinc-500/50',
};

const typeSelectedColors: Record<AgentType, string> = {
  support: 'border-emerald-400 bg-emerald-500/10 ring-1 ring-emerald-400/50',
  sales: 'border-amber-400 bg-amber-500/10 ring-1 ring-amber-400/50',
  technical: 'border-purple-400 bg-purple-500/10 ring-1 ring-purple-400/50',
  general: 'border-zinc-400 bg-zinc-500/10 ring-1 ring-zinc-400/50',
};

// ── Page ─────────────────────────────────────────────────────────────

export default function NewAgentPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState<AgentFormData>({
    name: '',
    type: 'support',
    variantTier: 'light',
    domain: '',
    personality: '',
  });

  const updateField = <K extends keyof AgentFormData>(key: K, value: AgentFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!form.name.trim()) {
      toast.error('Agent name is required');
      return;
    }
    if (!form.domain.trim()) {
      toast.error('Domain/industry is required');
      return;
    }

    setIsSubmitting(true);

    try {
      // Read existing agents from localStorage
      const existingRaw = localStorage.getItem('parwa_agents');
      const existing: AgentFormData[] = existingRaw ? JSON.parse(existingRaw) : [];

      // Create new agent with metadata
      const newAgent = {
        ...form,
        id: `agent_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
        status: 'initializing',
        createdAt: new Date().toISOString(),
      };

      // Save updated list
      localStorage.setItem('parwa_agents', JSON.stringify([...existing, newAgent]));

      toast.success(`Agent "${form.name}" created successfully`, {
        description: `${AGENT_TYPES.find((t) => t.value === form.type)?.label} agent on ${VARIANT_TIERS.find((t) => t.value === form.variantTier)?.label} tier`,
      });

      // Short delay for toast to show, then redirect
      setTimeout(() => {
        router.push('/dashboard/agents');
      }, 600);
    } catch (err) {
      toast.error('Failed to create agent', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="max-w-2xl mx-auto px-4 py-8"
      >
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/dashboard/agents')}
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-4"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Agents
          </button>

          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Create New Agent</h1>
              <p className="text-sm text-zinc-500">
                Configure a new AI agent for your workforce
              </p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Agent Name */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-zinc-300">
              Agent Name <span className="text-orange-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="e.g. Customer Support Bot, Sales Assistant"
              className="w-full px-4 py-2.5 rounded-lg bg-[#1A1A1A] border border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/30 transition-all text-sm"
              autoFocus
            />
          </div>

          {/* Agent Type */}
          <div className="space-y-3">
            <label className="block text-sm font-medium text-zinc-300">
              Agent Type <span className="text-orange-500">*</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {AGENT_TYPES.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => updateField('type', type.value)}
                  className={`text-left p-3.5 rounded-xl border transition-all duration-200 ${
                    form.type === type.value
                      ? typeSelectedColors[type.value]
                      : typeColors[type.value]
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <span className={form.type === type.value ? 'text-white' : 'text-zinc-400'}>
                      {type.icon}
                    </span>
                    <span className={`text-sm font-semibold ${form.type === type.value ? 'text-white' : 'text-zinc-300'}`}>
                      {type.label}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500 leading-relaxed">{type.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Variant Tier */}
          <div className="space-y-3">
            <label className="block text-sm font-medium text-zinc-300">
              Variant Tier <span className="text-orange-500">*</span>
            </label>
            <div className="space-y-3">
              {VARIANT_TIERS.map((tier) => (
                <button
                  key={tier.value}
                  type="button"
                  onClick={() => updateField('variantTier', tier.value)}
                  className={`w-full text-left p-4 rounded-xl border transition-all duration-200 ${
                    form.variantTier === tier.value
                      ? tierSelectedColors[tier.value]
                      : tierColors[tier.value]
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-sm font-semibold ${form.variantTier === tier.value ? 'text-white' : 'text-zinc-300'}`}>
                      {tier.label}
                    </span>
                    <span className="text-xs text-zinc-500 font-medium">{tier.price}</span>
                  </div>
                  <p className="text-xs text-zinc-500 leading-relaxed">{tier.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Domain/Industry */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-zinc-300">
              Domain / Industry <span className="text-orange-500">*</span>
            </label>
            <input
              type="text"
              value={form.domain}
              onChange={(e) => updateField('domain', e.target.value)}
              placeholder="e.g. E-commerce, SaaS, Healthcare, Finance"
              className="w-full px-4 py-2.5 rounded-lg bg-[#1A1A1A] border border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/30 transition-all text-sm"
            />
          </div>

          {/* Personality / Tone */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-zinc-300">
              Personality / Tone
            </label>
            <textarea
              value={form.personality}
              onChange={(e) => updateField('personality', e.target.value)}
              placeholder="Describe how the agent should communicate. e.g. Friendly but professional, concise, empathetic for complaints, uses customer's first name..."
              rows={4}
              className="w-full px-4 py-2.5 rounded-lg bg-[#1A1A1A] border border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/30 transition-all text-sm resize-none"
            />
            <p className="text-xs text-zinc-600">
              Optional. Helps the AI adopt the right tone for your brand.
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-4 border-t border-zinc-800">
            <button
              type="button"
              onClick={() => router.push('/dashboard/agents')}
              className="px-5 py-2.5 rounded-lg text-sm font-medium bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-zinc-800 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !form.name.trim() || !form.domain.trim()}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Create Agent
                </>
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
