'use client';

/**
 * Agent Building Step (Onboarding Step 4)
 *
 * After admin finishes:
 *   Step 1: Company details
 *   Step 2: Connect integrations (Shopify, Stripe, Brevo, etc.)
 *   Step 3: Upload KB (refund policy, SOPs, training manual)
 *
 * This step 4 triggers the Onboarding Builder Agent which:
 *   1. Reads the KB the admin just uploaded
 *   2. Reads the integrations they just connected
 *   3. Asks NVIDIA GLM-5.2: "What agents does this tenant need?"
 *   4. For each agent:
 *      a. Generates agent config (instructions include company-specific rules)
 *      b. Requests Superglue to generate multi-step tool (tenant-namespaced)
 *      c. Saves to DB
 *   5. Returns when done (~3-5 minutes)
 *
 * Per-tenant isolation: every Superglue tool is prefixed with tenant_{companyId}__
 * so each tenant's tools are completely separate on the shared Superglue server.
 */

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot, Sparkles, Loader2, CheckCircle2, XCircle, ArrowRight,
  FileText, Plug, Cpu, AlertCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';

type BuildState = 'idle' | 'building' | 'done' | 'error';

const BUILD_STAGES = [
  { id: 'read_kb', label: 'Reading your knowledge base', icon: FileText },
  { id: 'read_integ', label: 'Reading connected integrations', icon: Plug },
  { id: 'detect', label: 'Detecting what agents you need', icon: Cpu },
  { id: 'design', label: 'Designing agent configs (NVIDIA GLM-5.2)', icon: Bot },
  { id: 'superglue', label: 'Generating Superglue tools', icon: Sparkles },
  { id: 'save', label: 'Saving agents to your dashboard', icon: CheckCircle2 },
];

export function AgentBuildingStep({ onComplete }: { onComplete: () => void }) {
  const router = useRouter();
  const { user } = useAuth();
  const [buildState, setBuildState] = useState<BuildState>('idle');
  const [currentStage, setCurrentStage] = useState(0);
  const [agentCount, setAgentCount] = useState(0);
  const [error, setError] = useState<string>('');

  // Auto-start building when component mounts
  useEffect(() => {
    if (buildState === 'idle') {
      startBuild();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Simulate stage progression while building
  useEffect(() => {
    if (buildState !== 'building') return;
    const interval = setInterval(() => {
      setCurrentStage((prev) => Math.min(prev + 1, BUILD_STAGES.length - 1));
    }, 8000); // advance stage every 8s
    return () => clearInterval(interval);
  }, [buildState]);

  // Poll for completion while building
  useEffect(() => {
    if (buildState !== 'building') return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch('/api/ai/agents?limit=20', { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          const count = data?.agents?.length || data?.data?.length || 0;
          setAgentCount(count);
          // If we have 3+ agents and we're past stage 4, consider done
          if (count >= 3 && currentStage >= 4) {
            setBuildState('done');
            clearInterval(interval);
          }
        }
      } catch (err) {
        // ignore poll errors
      }
    }, 15000); // poll every 15s
    return () => clearInterval(interval);
  }, [buildState, currentStage]);

  const startBuild = async () => {
    setBuildState('building');
    setError('');
    try {
      const res = await fetch('/api/builder-agent/build-from-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ force_rebuild: false }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody?.detail || errBody?.message || `HTTP ${res.status}`);
      }

      const data = await res.json();

      // If already built, skip to done
      if (data.status === 'already_built') {
        toast.success('Agents already exist', {
          description: data.message,
        });
        setBuildState('done');
        return;
      }

      toast.success('Building started', {
        description: 'Reading your KB + integrations to design specialized agents',
      });
    } catch (err) {
      setBuildState('error');
      setError(err instanceof Error ? err.message : 'Unknown error');
      toast.error('Build failed', { description: err instanceof Error ? err.message : '' });
    }
  };

  const handleComplete = () => {
    toast.success('Onboarding complete!', {
      description: `${agentCount} agents ready to solve tickets`,
    });
    onComplete();
  };

  return (
    <div className="min-h-[600px] bg-[#0A0A0A] flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-2xl w-full"
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="text-center mb-10">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.2, type: 'spring' }}
            className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center"
          >
            {buildState === 'building' ? (
              <Loader2 className="w-8 h-8 text-white animate-spin" />
            ) : buildState === 'done' ? (
              <CheckCircle2 className="w-8 h-8 text-white" />
            ) : buildState === 'error' ? (
              <XCircle className="w-8 h-8 text-white" />
            ) : (
              <Sparkles className="w-8 h-8 text-white" />
            )}
          </motion.div>
          <h1 className="text-2xl font-bold text-white mb-2">
            {buildState === 'building' && 'Building your AI agents'}
            {buildState === 'done' && `${agentCount} agents ready!`}
            {buildState === 'error' && 'Build failed'}
            {buildState === 'idle' && 'Preparing to build...'}
          </h1>
          <p className="text-sm text-zinc-500">
            {buildState === 'building' && 'Reading your KB + integrations to design specialized agents'}
            {buildState === 'done' && 'Your AI workforce is ready to solve tickets'}
            {buildState === 'error' && error}
          </p>
        </div>

        {/* ── Build stages ───────────────────────────────────────── */}
        {buildState === 'building' && (
          <div className="space-y-3 mb-8">
            {BUILD_STAGES.map((stage, idx) => {
              const isDone = idx < currentStage;
              const isCurrent = idx === currentStage;
              const isPending = idx > currentStage;
              const Icon = stage.icon;
              return (
                <motion.div
                  key={stage.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                    isCurrent
                      ? 'bg-orange-500/[0.06] border-orange-500/30'
                      : isDone
                        ? 'bg-emerald-500/[0.04] border-emerald-500/20'
                        : 'bg-white/[0.02] border-white/[0.05]'
                  }`}
                >
                  <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${
                    isCurrent
                      ? 'bg-orange-500/20 text-orange-400'
                      : isDone
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-white/[0.04] text-zinc-600'
                  }`}>
                    {isCurrent ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : isDone ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <Icon className="w-4 h-4" />
                    )}
                  </div>
                  <span className={`text-sm ${
                    isCurrent ? 'text-orange-300' : isDone ? 'text-emerald-300' : 'text-zinc-500'
                  }`}>
                    {stage.label}
                  </span>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* ── Done state ─────────────────────────────────────────── */}
        {buildState === 'done' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-6 mb-6"
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-emerald-300 mb-1">
                  {agentCount > 0 ? `${agentCount} agents created` : 'Agents created'}
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  Each agent has been linked to a Superglue multi-step tool that runs
                  automatically when matching tickets arrive. You can view them in the dashboard.
                </p>
              </div>
            </div>
            <div className="text-[11px] text-zinc-500 mt-3 pt-3 border-t border-emerald-500/10">
              💡 The system will keep learning from your tickets — new patterns get
              turned into new agents weekly.
            </div>
          </motion.div>
        )}

        {/* ── Error state ─────────────────────────────────────────── */}
        {buildState === 'error' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl border border-red-500/30 bg-red-500/[0.04] p-6 mb-6"
          >
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-red-300 mb-1">Build failed</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">{error}</p>
              </div>
            </div>
            <button
              onClick={startBuild}
              className="w-full px-4 py-2 rounded-lg text-sm font-medium bg-white/[0.04] text-zinc-300 hover:bg-white/[0.08] border border-white/[0.08] transition-colors"
            >
              Try again
            </button>
          </motion.div>
        )}

        {/* ── Footer actions ─────────────────────────────────────── */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-800">
          {buildState === 'done' && (
            <button
              onClick={handleComplete}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
            >
              Go to Dashboard <ArrowRight className="w-4 h-4" />
            </button>
          )}
          {buildState === 'building' && (
            <span className="text-xs text-zinc-600">
              Estimated 3-5 minutes · Auto-refreshes
            </span>
          )}
        </div>
      </motion.div>
    </div>
  );
}
