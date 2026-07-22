/**
 * Agent Setup Page (/dashboard/agents/setup)
 *
 * Paste a job description → LLM analyzes it → suggests 2-5 specialized
 * agents → review + create them.
 *
 * This is the "I don't know what agents to create" flow. The user pastes
 * their CS role JD, the builder does the thinking.
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Bot, ArrowLeft, Sparkles, Loader2, Check, Plus, FileText } from 'lucide-react';
import { toast } from 'sonner';

interface AgentSuggestion {
  agent_name: string;
  domain: string;
  capabilities: string[];
  instructions: string;
  restrictions: string;
}

export default function AgentSetupPage() {
  const router = useRouter();
  const [jd, setJd] = useState('');
  const [industry, setIndustry] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [suggestions, setSuggestions] = useState<AgentSuggestion[]>([]);
  const [creatingIdx, setCreatingIdx] = useState<number | null>(null);
  const [createdIdxs, setCreatedIdxs] = useState<Set<number>>(new Set());

  const handleAnalyze = async () => {
    if (jd.trim().length < 50) {
      toast.error('Please paste a longer job description (at least 50 characters)');
      return;
    }
    setIsAnalyzing(true);
    setSuggestions([]);
    setCreatedIdxs(new Set());
    try {
      const res = await fetch('/api/ai/agents/auto-create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          job_description: jd.trim(),
          industry: industry.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || err?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.status === 'error') {
        throw new Error(data.message || 'LLM analysis failed');
      }
      const sugs: AgentSuggestion[] = data.suggestions || [];
      if (sugs.length === 0) {
        toast.error('The builder could not suggest any agents. Try a more detailed job description.');
        return;
      }
      setSuggestions(sugs);
      toast.success(`Builder suggested ${sugs.length} agents — review and create the ones you want`);
    } catch (err) {
      toast.error('Failed to analyze job description', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleCreateOne = async (idx: number) => {
    const s = suggestions[idx];
    if (!s) return;
    setCreatingIdx(idx);
    try {
      const res = await fetch('/api/ai/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          agent_name: s.agent_name,
          agent_role: s.domain,
          domain: s.domain,
          capabilities: s.capabilities,
          instructions: s.instructions || null,
          restrictions: s.restrictions || null,
          feature_ids: [],
          task_ids: [],
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.[0]?.msg || err?.detail || `HTTP ${res.status}`);
      }
      setCreatedIdxs((prev) => new Set(prev).add(idx));
      toast.success(`Agent "${s.agent_name}" created`);
    } catch (err) {
      toast.error(`Failed to create "${s.agent_name}"`, {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setCreatingIdx(null);
    }
  };

  const handleCreateAll = async () => {
    for (let i = 0; i < suggestions.length; i++) {
      if (!createdIdxs.has(i)) {
        // eslint-disable-next-line no-await-in-loop
        await handleCreateOne(i);
      }
    }
    toast.success('All agents created', {
      description: 'Redirecting to agents list...',
    });
    setTimeout(() => router.push('/dashboard/agents'), 1200);
  };

  const inputClasses = "w-full px-4 py-2.5 rounded-lg bg-[#1A1A1A] border border-zinc-800 text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/30 transition-all text-sm";
  const labelClasses = "block text-sm font-medium text-zinc-300 mb-1.5";
  const sectionClasses = "rounded-xl border border-white/[0.05] bg-white/[0.015] p-4 space-y-3";
  const sectionTitleClasses = "text-xs font-semibold text-zinc-300 uppercase tracking-wide flex items-center gap-2";

  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="max-w-3xl mx-auto px-4 py-8"
      >
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => router.push('/dashboard/agents')}
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors mb-4"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Agents
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Agent Builder</h1>
              <p className="text-sm text-zinc-500">
                Paste a job description — the builder suggests what agents to create
              </p>
            </div>
          </div>
        </div>

        {/* Step 1: Paste JD */}
        <div className={sectionClasses}>
          <div className={sectionTitleClasses}>
            <span className="w-1 h-3 rounded-full bg-orange-500" />
            <FileText className="w-3.5 h-3.5" />
            1. Paste your job description
          </div>
          <div>
            <label className={labelClasses}>Job Description <span className="text-orange-500">*</span></label>
            <textarea
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              placeholder="Paste the full job description here — responsibilities, requirements, what the role does. The builder will analyze it and suggest specialized agents."
              rows={10}
              className={inputClasses + ' resize-y font-mono text-xs'}
            />
            <p className="text-[11px] text-zinc-600 mt-1">
              {jd.length} characters {jd.length > 0 && jd.length < 50 && '(need at least 50)'}
            </p>
          </div>
          <div>
            <label className={labelClasses}>Industry (optional)</label>
            <input
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. Hospitality, E-commerce, Healthcare — helps the builder"
              className={inputClasses}
            />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing || jd.trim().length < 50}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
          >
            {isAnalyzing ? (
              <span className="inline-flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Analyzing...</span>
            ) : (
              <span className="inline-flex items-center gap-2"><Sparkles className="w-4 h-4" />Analyze &amp; Suggest Agents</span>
            )}
          </button>
        </div>

        {/* Step 2: Review Suggestions */}
        {suggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="mt-6 space-y-4"
          >
            <div className="flex items-center justify-between">
              <div className={sectionTitleClasses}>
                <span className="w-1 h-3 rounded-full bg-orange-500" />
                <Bot className="w-3.5 h-3.5" />
                2. Review suggested agents ({suggestions.length})
              </div>
              <button
                onClick={handleCreateAll}
                disabled={createdIdxs.size === suggestions.length}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-white/[0.06] text-white hover:bg-white/[0.1] border border-white/[0.08] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Plus className="w-3.5 h-3.5" />
                {createdIdxs.size === suggestions.length ? 'All Created' : `Create All (${suggestions.length - createdIdxs.size} left)`}
              </button>
            </div>

            {suggestions.map((s, idx) => {
              const isCreated = createdIdxs.has(idx);
              const isCreating = creatingIdx === idx;
              return (
                <div
                  key={idx}
                  className={`rounded-xl border p-5 transition-all ${
                    isCreated
                      ? 'border-emerald-500/30 bg-emerald-500/[0.03]'
                      : 'border-white/[0.06] bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                        isCreated ? 'bg-emerald-500/20' : 'bg-gradient-to-br from-orange-500/20 to-amber-400/20'
                      }`}>
                        {isCreated ? (
                          <Check className="w-4.5 h-4.5 text-emerald-400" />
                        ) : (
                          <Bot className="w-4.5 h-4.5 text-orange-400" />
                        )}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-white">{s.agent_name}</h3>
                        <p className="text-xs text-zinc-500 mt-0.5">{s.domain}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleCreateOne(idx)}
                      disabled={isCreated || isCreating}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                        isCreated
                          ? 'border-emerald-500/30 text-emerald-400'
                          : 'border-orange-500/30 text-orange-400 hover:bg-orange-500/10'
                      }`}
                    >
                      {isCreating ? (
                        <span className="inline-flex items-center gap-1.5"><Loader2 className="w-3 h-3 animate-spin" />Creating...</span>
                      ) : isCreated ? (
                        <span className="inline-flex items-center gap-1.5"><Check className="w-3 h-3" />Created</span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5"><Plus className="w-3 h-3" />Create</span>
                      )}
                    </button>
                  </div>

                  <div className="space-y-2.5 text-xs">
                    <div>
                      <span className="text-zinc-500 font-medium">Handles:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {s.capabilities.map((c, i) => (
                          <span key={i} className="px-2 py-0.5 rounded-md bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                    {s.instructions && (
                      <div>
                        <span className="text-zinc-500 font-medium">Instructions:</span>
                        <p className="text-zinc-300 mt-1 leading-relaxed">{s.instructions}</p>
                      </div>
                    )}
                    {s.restrictions && (
                      <div>
                        <span className="text-zinc-500 font-medium">Restrictions:</span>
                        <p className="text-zinc-400 mt-1 leading-relaxed">{s.restrictions}</p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            <div className="flex items-center gap-3 pt-4">
              <button
                onClick={() => router.push('/dashboard/agents')}
                className="px-5 py-2.5 rounded-lg text-sm font-medium bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] border border-zinc-800 transition-all"
              >
                Done — Go to Agents
              </button>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
