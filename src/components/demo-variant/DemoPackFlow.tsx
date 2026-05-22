/**
 * PARWA Demo Pack Flow — Main Container Component
 *
 * Step-by-step flow: Select Variant → Select Industry → Start Demo
 * Integrates usage tracking, billing, and knowledge base selection.
 * Matches ORANGE (#FF7F11) design system.
 */

'use client';

import { useState, useEffect } from 'react';
import { ArrowRight, ArrowLeft, Play, Loader2, Sparkles, CreditCard, Phone, BookOpen } from 'lucide-react';
import { useDemoVariant } from '@/hooks/useDemoVariant';
import { DemoVariantSelector } from './DemoVariantSelector';
import { DemoIndustryPicker } from './DemoIndustryPicker';
import { DemoUsageTracker } from './DemoUsageTracker';
import { DemoBillCard } from './DemoBillCard';
import { DemoKnowledgeBasePanel } from './DemoKnowledgeBasePanel';
import { listKnowledgeBases } from '@/lib/demo-variant-api';
import type { DemoKnowledgeBase } from '@/types/demo-variant';

type DemoStep = 'variant' | 'industry' | 'knowledge' | 'start';

export function DemoPackFlow() {
  const {
    variants,
    selectedVariant,
    selectedIndustry,
    demoSession,
    isSessionLoading,
    usage,
    billSummary,
    selectedKBs,
    isLoading,
    error,
    selectVariant,
    selectIndustry,
    startDemo,
    refreshUsage,
    selectKB,
    deselectKB,
    clearError,
  } = useDemoVariant();

  const [step, setStep] = useState<DemoStep>('variant');
  const [prebuiltKBs, setPrebuiltKBs] = useState<DemoKnowledgeBase[]>([]);
  const [uploadedKBs, setUploadedKBs] = useState<DemoKnowledgeBase[]>([]);

  // Load KBs when step changes
  useEffect(() => {
    if (step === 'knowledge') {
      listKnowledgeBases()
        .then((data) => {
          setPrebuiltKBs(data.prebuilt);
          setUploadedKBs(data.uploaded);
        })
        .catch(() => {});
    }
  }, [step]);

  // Auto-refresh usage when session is active
  useEffect(() => {
    if (!demoSession?.id) return;
    const interval = setInterval(() => {
      refreshUsage();
    }, 5000);
    return () => clearInterval(interval);
  }, [demoSession?.id, refreshUsage]);

  const steps: { id: DemoStep; label: string; icon: React.ReactNode }[] = [
    { id: 'variant', label: 'Choose Agent', icon: <Sparkles className="w-4 h-4" /> },
    { id: 'industry', label: 'Industry', icon: <CreditCard className="w-4 h-4" /> },
    { id: 'knowledge', label: 'Knowledge', icon: <BookOpen className="w-4 h-4" /> },
    { id: 'start', label: 'Start Demo', icon: <Play className="w-4 h-4" /> },
  ];

  const stepIndex = steps.findIndex((s) => s.id === step);

  const goNext = () => {
    const next = steps[stepIndex + 1];
    if (next) setStep(next.id);
  };

  const goBack = () => {
    const prev = steps[stepIndex - 1];
    if (prev) setStep(prev.id);
  };

  const canGoNext = () => {
    switch (step) {
      case 'variant': return !!selectedVariant;
      case 'industry': return !!selectedIndustry;
      case 'knowledge': return true;
      case 'start': return false;
    }
  };

  const handleStartDemo = async () => {
    await startDemo();
  };

  // If session is active, show the demo view
  if (demoSession && demoSession.status === 'active') {
    return (
      <div className="space-y-4">
        <div className="glass rounded-xl p-4 border border-orange-500/15">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Demo Active!</h2>
              <p className="text-[11px] text-white/40">
                {selectedVariant?.name} · {selectedIndustry}
              </p>
            </div>
          </div>

          {/* Usage + Billing side by side */}
          <div className="flex flex-col sm:flex-row gap-3 mt-3">
            <DemoUsageTracker usage={usage} />
            <DemoBillCard billSummary={billSummary} />
          </div>

          {/* Quick actions */}
          <div className="flex gap-2 mt-3">
            <a
              href="/dashboard/jarvis"
              className="btn-primary text-xs flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Chat with Jarvis
            </a>
            <a
              href="/dashboard/calls"
              className="btn-secondary text-xs flex items-center gap-1.5"
            >
              <Phone className="w-3.5 h-3.5" />
              Try Demo Call
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {steps.map((s, idx) => (
          <div key={s.id} className="flex items-center gap-2">
            <button
              onClick={() => setStep(s.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
                idx <= stepIndex
                  ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20'
                  : 'bg-white/[0.02] text-white/20 border border-white/[0.04]'
              }`}
            >
              {s.icon}
              <span className="hidden sm:inline">{s.label}</span>
            </button>
            {idx < steps.length - 1 && (
              <div className={`w-6 h-px ${idx < stepIndex ? 'bg-orange-500/30' : 'bg-white/[0.06]'}`} />
            )}
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/10">
          <span className="text-xs text-red-300">{error}</span>
          <button onClick={clearError} className="text-[10px] text-red-400 hover:text-red-300 ml-auto">
            Dismiss
          </button>
        </div>
      )}

      {/* Step content */}
      {step === 'variant' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">Choose your AI Agent</h2>
            <p className="text-sm text-white/30">Which variant would you like to demo?</p>
          </div>
          <DemoVariantSelector
            variants={variants}
            selectedVariant={selectedVariant}
            onSelect={selectVariant}
            isLoading={isLoading}
          />
        </div>
      )}

      {step === 'industry' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">What&apos;s your industry?</h2>
            <p className="text-sm text-white/30">We&apos;ll customize the demo for your business.</p>
          </div>
          <DemoIndustryPicker
            selectedIndustry={selectedIndustry}
            onSelect={selectIndustry}
          />
        </div>
      )}

      {step === 'knowledge' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">Set up Knowledge Base</h2>
            <p className="text-sm text-white/30">Upload your docs or use pre-built industry knowledge.</p>
          </div>
          <DemoKnowledgeBasePanel
            prebuiltKBs={prebuiltKBs}
            uploadedKBs={uploadedKBs}
            selectedKBs={selectedKBs}
            onSelectKB={selectKB}
            onDeselectKB={deselectKB}
            onUploadComplete={() => {
              listKnowledgeBases().then((data) => {
                setPrebuiltKBs(data.prebuilt);
                setUploadedKBs(data.uploaded);
              }).catch(() => {});
            }}
          />
        </div>
      )}

      {step === 'start' && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold text-white mb-1">Ready to start!</h2>
            <p className="text-sm text-white/30">Review your demo configuration and launch.</p>
          </div>

          {/* Summary */}
          <div className="glass rounded-xl p-5 border border-orange-500/15 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Agent</span>
              <span className="text-sm font-semibold text-orange-300">{selectedVariant?.name}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Industry</span>
              <span className="text-sm font-semibold text-white/60">{selectedIndustry}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Price</span>
              <span className="text-sm font-semibold text-gradient">${selectedVariant?.price_per_month.toLocaleString()}/mo</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-white/40">Demo includes</span>
              <span className="text-xs text-white/50">40 messages + 3-min call</span>
            </div>
            {selectedKBs.length > 0 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-white/40">Knowledge Bases</span>
                <span className="text-xs text-white/50">{selectedKBs.length} selected</span>
              </div>
            )}
          </div>

          {/* Bill preview */}
          <DemoBillCard billSummary={billSummary} />

          {/* Start button */}
          <button
            onClick={handleStartDemo}
            disabled={isSessionLoading}
            className="w-full btn-primary btn-lg flex items-center justify-center gap-2"
          >
            {isSessionLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Starting Demo...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Start $1 Demo Pack
              </>
            )}
          </button>

          <p className="text-[10px] text-white/20 text-center">
            40 messages + 3-min AI voice call · No commitment · Cancel anytime
          </p>
        </div>
      )}

      {/* Navigation */}
      {step !== 'start' && (
        <div className="flex items-center justify-between pt-4 border-t border-white/[0.04]">
          <button
            onClick={goBack}
            disabled={stepIndex === 0}
            className="btn-ghost text-xs flex items-center gap-1.5 disabled:opacity-30"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back
          </button>
          <button
            onClick={goNext}
            disabled={!canGoNext()}
            className="btn-primary text-xs flex items-center gap-1.5 disabled:opacity-30"
          >
            Continue
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
