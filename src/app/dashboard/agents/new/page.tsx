/**
 * Create New Agent Page (/dashboard/agents/new)
 *
 * Simple 3-section form inspired by OpenAI GPT Builder:
 *   1. Identity — name, domain, instructions (system prompt)
 *   2. What it can handle — free-text capabilities (LLM auto-detects)
 *   3. Restrictions — natural language rules
 *
 * No hardcoded types. No checkbox grids. Just describe what you want.
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Bot, ArrowLeft, Save, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

interface AgentFormData {
  name: string;
  domain: string;
  canHandle: string;
  instructions: string;
  restrictions: string;
}

export default function NewAgentPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [form, setForm] = useState<AgentFormData>({
    name: '', domain: '', canHandle: '', instructions: '', restrictions: '',
  });

  const updateField = <K extends keyof AgentFormData>(key: K, value: AgentFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { toast.error('Agent name is required'); return; }
    if (!form.canHandle.trim()) { toast.error('Please describe what this agent can handle'); return; }
    setIsSubmitting(true);
    try {
      const capabilities = form.canHandle.split(/[,\n;]+/).map((s) => s.trim().toLowerCase().replace(/\s+/g, '_')).filter((s) => s.length > 0);
      const res = await fetch('/api/ai/agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({
          agent_name: form.name.trim(), agent_role: form.domain.trim() || 'general',
          domain: form.domain.trim(), capabilities,
          instructions: form.instructions.trim() || null, restrictions: form.restrictions.trim() || null,
          feature_ids: [], task_ids: [],
        }),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody?.detail?.[0]?.msg || errBody?.detail || `HTTP ${res.status}`);
      }
      toast.success(`Agent "${form.name}" created successfully`, { description: `${capabilities.length} capabilities · will handle matching tickets` });
      setTimeout(() => { router.push('/dashboard/agents'); }, 800);
    } catch (err) {
      toast.error('Failed to create agent', { description: err instanceof Error ? err.message : 'Unknown error' });
    } finally { setIsSubmitting(false); }
  };

  const inputClasses = "w-full px-4 py-2.5 rounded-lg bg-[#1A1A1A] border border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/30 transition-all text-sm";
  const labelClasses = "block text-sm font-medium text-zinc-300 mb-1.5";
  const sectionClasses = "rounded-xl border border-white/[0.05] bg-white/[0.015] p-4 space-y-3";
  const sectionTitleClasses = "text-xs font-semibold text-zinc-300 uppercase tracking-wide flex items-center gap-2";

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="max-w-2xl mx-auto px-4 py-8">
        <div className="mb-8">
          <button onClick={() => router.push('/dashboard/agents')} className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-4">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Agents
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Create New Agent</h1>
              <p className="text-sm text-zinc-500">Describe what this agent does — no restrictions, any type</p>
            </div>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className={sectionClasses}>
            <div className={sectionTitleClasses}><span className="w-1 h-3 rounded-full bg-orange-500" />1. Identity</div>
            <div>
              <label className={labelClasses}>Agent Name <span className="text-orange-500">*</span></label>
              <input type="text" value={form.name} onChange={(e) => updateField('name', e.target.value)} placeholder="e.g. Refund Specialist, Freight Tracker, Legal Advisor" className={inputClasses} autoFocus />
            </div>
            <div>
              <label className={labelClasses}>Domain / Industry</label>
              <input type="text" value={form.domain} onChange={(e) => updateField('domain', e.target.value)} placeholder="e.g. E-commerce, SaaS, Healthcare, Logistics" className={inputClasses} />
              <p className="text-[11px] text-zinc-600 mt-1">Optional — helps the system understand context.</p>
            </div>
            <div>
              <label className={labelClasses}>Instructions (System Prompt)</label>
              <textarea value={form.instructions} onChange={(e) => updateField('instructions', e.target.value)} placeholder="e.g. You are a refund specialist. Be concise. Always cite the refund policy. For amounts over $500, ask for guidance before processing." rows={3} className={inputClasses + ' resize-none'} />
              <p className="text-[11px] text-zinc-600 mt-1">Tell the AI how to behave. This becomes its system prompt when handling tickets.</p>
            </div>
          </div>
          <div className={sectionClasses}>
            <div className={sectionTitleClasses}><span className="w-1 h-3 rounded-full bg-orange-500" />2. What It Can Handle</div>
            <div>
              <label className={labelClasses}>Can Handle <span className="text-orange-500">*</span></label>
              <textarea value={form.canHandle} onChange={(e) => updateField('canHandle', e.target.value)} placeholder="e.g. refund requests, chargebacks, return processing, money-back claims" rows={3} className={inputClasses + ' resize-none'} />
              <p className="text-[11px] text-zinc-600 mt-1">Describe what this agent handles. Separate multiple items with commas. Tickets matching these will route to this agent automatically.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {['refunds', 'billing', 'technical support', 'complaints', 'fraud', 'shipping', 'legal', 'VIP customers'].map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => { const current = form.canHandle.trim(); updateField('canHandle', current ? `${current}, ${suggestion}` : suggestion); }} className="px-2 py-1 rounded-md bg-white/[0.04] hover:bg-white/[0.08] text-zinc-400 hover:text-zinc-200 text-[11px] border border-white/[0.06] transition-colors">+ {suggestion}</button>
              ))}
            </div>
          </div>
          <div className={sectionClasses}>
            <div className={sectionTitleClasses}><span className="w-1 h-3 rounded-full bg-orange-500" />3. Restrictions</div>
            <div>
              <label className={labelClasses}>Restrictions / Rules</label>
              <textarea value={form.restrictions} onChange={(e) => updateField('restrictions', e.target.value)} placeholder="e.g. Never share competitor pricing. Max refund $500 without guidance. Always escalate legal threats." rows={3} className={inputClasses + ' resize-none'} />
              <p className="text-[11px] text-zinc-600 mt-1">Natural language rules the agent must follow. Optional.</p>
            </div>
          </div>
          <div className="flex items-center gap-3 pt-4 border-t border-zinc-800">
            <button type="button" onClick={() => router.push('/dashboard/agents')} className="px-5 py-2.5 rounded-lg text-sm font-medium bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-zinc-800 transition-all">Cancel</button>
            <button type="submit" disabled={isSubmitting || !form.name.trim() || !form.canHandle.trim()} className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none">
              {isSubmitting ? (<span className="inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Creating...</span>) : (<span className="inline-flex items-center gap-2"><Save className="w-4 h-4" />Create Agent</span>)}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
