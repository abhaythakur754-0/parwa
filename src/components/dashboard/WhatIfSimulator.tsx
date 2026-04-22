'use client';

import React, { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import { getErrorMessage } from '@/lib/api';
import { cn } from '@/lib/utils';
import { shadowApi, type SystemMode, type RiskEvaluation } from '@/lib/shadow-api';

// ── Skeleton Helper ────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/[0.06]', className)} />;
}

// ── Inline SVG Icons ───────────────────────────────────────────────────────

function BeakerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
    </svg>
  );
}

function PlayIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
    </svg>
  );
}

function ChevronDownIcon({ className, open }: { className?: string; open?: boolean }) {
  return (
    <svg className={cn(className, open && 'rotate-180')} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
    </svg>
  );
}

function ExclamationTriangleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

// ── Action Types with Dynamic Fields ───────────────────────────────────────

const ACTION_TYPES = [
  { key: 'refund', label: 'Refund', fields: [
    { key: 'amount', label: 'Amount ($)', type: 'number', placeholder: '50.00' },
    { key: 'customer_id', label: 'Customer ID', type: 'text', placeholder: 'cust_123' },
    { key: 'reason', label: 'Reason', type: 'text', placeholder: 'Customer request' },
  ]},
  { key: 'email_reply', label: 'Email Reply', fields: [
    { key: 'recipient', label: 'Recipient Email', type: 'text', placeholder: 'customer@example.com' },
    { key: 'subject', label: 'Subject', type: 'text', placeholder: 'Re: Support ticket' },
    { key: 'content', label: 'Email Content', type: 'textarea', placeholder: 'Write the email reply content...' },
  ]},
  { key: 'sms_reply', label: 'SMS Reply', fields: [
    { key: 'phone', label: 'Phone Number', type: 'text', placeholder: '+1234567890' },
    { key: 'content', label: 'SMS Content', type: 'textarea', placeholder: 'Write the SMS reply...' },
  ]},
  { key: 'voice_reply', label: 'Voice Reply', fields: [
    { key: 'call_id', label: 'Call ID', type: 'text', placeholder: 'call_abc123' },
    { key: 'response_text', label: 'Response Text', type: 'textarea', placeholder: 'Voice response transcript...' },
  ]},
  { key: 'ticket_close', label: 'Close Ticket', fields: [
    { key: 'ticket_id', label: 'Ticket ID', type: 'text', placeholder: 'TKT-001' },
    { key: 'resolution', label: 'Resolution Note', type: 'textarea', placeholder: 'How was this resolved?' },
  ]},
  { key: 'account_change', label: 'Account Change', fields: [
    { key: 'customer_id', label: 'Customer ID', type: 'text', placeholder: 'cust_123' },
    { key: 'change_type', label: 'Change Type', type: 'text', placeholder: 'email_update' },
    { key: 'new_value', label: 'New Value', type: 'text', placeholder: 'new@email.com' },
  ]},
  { key: 'integration_action', label: 'Integration', fields: [
    { key: 'integration_name', label: 'Integration Name', type: 'text', placeholder: 'slack' },
    { key: 'action', label: 'Action', type: 'text', placeholder: 'send_notification' },
    { key: 'data', label: 'Payload', type: 'textarea', placeholder: 'JSON payload...' },
  ]},
];

// ── Mode Config ────────────────────────────────────────────────────────────

const MODE_CONFIG: Record<SystemMode, { label: string; color: string; bgColor: string; borderColor: string; dotColor: string }> = {
  shadow: { label: 'Shadow', color: 'text-orange-400', bgColor: 'bg-orange-500/15', borderColor: 'border-orange-500/25', dotColor: 'bg-orange-400' },
  supervised: { label: 'Supervised', color: 'text-blue-400', bgColor: 'bg-blue-500/15', borderColor: 'border-blue-500/25', dotColor: 'bg-blue-400' },
  graduated: { label: 'Graduated', color: 'text-emerald-400', bgColor: 'bg-emerald-500/15', borderColor: 'border-emerald-500/25', dotColor: 'bg-emerald-400' },
};

// ════════════════════════════════════════════════════════════════════════════
// WhatIfSimulator Component
// ════════════════════════════════════════════════════════════════════════════

interface SimulationResult {
  timestamp: string;
  actionType: string;
  result: RiskEvaluation;
}

export default function WhatIfSimulator() {
  // ── State ───────────────────────────────────────────────────────────────
  const [selectedAction, setSelectedAction] = useState('');
  const [payload, setPayload] = useState<Record<string, string>>({});
  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<RiskEvaluation | null>(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [history, setHistory] = useState<SimulationResult[]>([]);

  // ── Derived ─────────────────────────────────────────────────────────────
  const actionConfig = ACTION_TYPES.find(a => a.key === selectedAction);

  // ── Handlers ───────────────────────────────────────────────────────────
  const handleActionChange = (key: string) => {
    setSelectedAction(key);
    setPayload({});
    setResult(null);
    setShowExplanation(false);
  };

  const handleEvaluate = useCallback(async () => {
    if (!selectedAction) {
      toast.error('Please select an action type');
      return;
    }
    setEvaluating(true);
    setResult(null);
    setShowExplanation(false);
    try {
      const evalResult = await shadowApi.evaluate(selectedAction, payload);
      setResult(evalResult);
      setHistory(prev => [{
        timestamp: new Date().toISOString(),
        actionType: selectedAction,
        result: evalResult,
      }, ...prev.slice(0, 9)]);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setEvaluating(false);
    }
  }, [selectedAction, payload]);

  const clearResult = () => {
    setResult(null);
    setShowExplanation(false);
  };

  // ── Risk Color Helpers ─────────────────────────────────────────────────
  const getRiskColor = (score: number) => {
    if (score >= 0.7) return { bar: 'bg-red-500', text: 'text-red-400', bg: 'bg-red-500/15' };
    if (score >= 0.4) return { bar: 'bg-yellow-500', text: 'text-yellow-400', bg: 'bg-yellow-500/15' };
    return { bar: 'bg-emerald-500', text: 'text-emerald-400', bg: 'bg-emerald-500/15' };
  };

  // ════════════════════════════════════════════════════════════════════════
  // Render
  // ════════════════════════════════════════════════════════════════════════

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <span className="text-[#FF7F11]">
          <BeakerIcon className="h-5 w-5" />
        </span>
        <h3 className="text-base font-semibold text-white">What-If Simulator</h3>
        <span className="text-[10px] text-zinc-600 bg-white/[0.04] px-2 py-0.5 rounded-md font-medium uppercase tracking-wider ml-1">
          Preview
        </span>
      </div>

      {/* ── Simulator Form ───────────────────────────────────────────── */}
      <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-5">
        <div className="space-y-4">
          {/* Action Type Selector */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Action Type</label>
            <select
              value={selectedAction}
              onChange={e => handleActionChange(e.target.value)}
              className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-2.5 text-sm text-white focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 appearance-none cursor-pointer"
            >
              <option value="">Select an action type...</option>
              {ACTION_TYPES.map(a => (
                <option key={a.key} value={a.key}>{a.label}</option>
              ))}
            </select>
          </div>

          {/* Dynamic Fields */}
          {actionConfig && (
            <div className="space-y-3 pt-1 border-t border-white/[0.04]">
              {actionConfig.fields.map(field => (
                <div key={field.key}>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">
                    {field.label}
                  </label>
                  {field.type === 'textarea' ? (
                    <textarea
                      value={payload[field.key] || ''}
                      onChange={e => setPayload(prev => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 resize-none transition-colors"
                      rows={3}
                    />
                  ) : (
                    <input
                      type={field.type}
                      value={payload[field.key] || ''}
                      onChange={e => setPayload(prev => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                      className="w-full rounded-lg border border-white/[0.08] bg-[#141414] px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:border-[#FF7F11]/50 focus:outline-none focus:ring-1 focus:ring-[#FF7F11]/30 transition-colors"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Evaluate Button */}
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleEvaluate}
              disabled={!selectedAction || evaluating}
              className="inline-flex items-center gap-2 rounded-xl bg-[#FF7F11] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#FF7F11]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {evaluating ? <SpinnerIcon className="w-4 h-4 animate-spin" /> : <PlayIcon className="w-4 h-4" />}
              {evaluating ? 'Evaluating...' : 'Evaluate'}
            </button>
            {result && (
              <button
                onClick={clearResult}
                className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-2 text-xs font-medium text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                <XMarkIcon className="w-3 h-3" />
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Result Display ────────────────────────────────────────────── */}
      {evaluating ? (
        <Skeleton className="h-48" />
      ) : result ? (
        <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] overflow-hidden">
          {/* Result Header */}
          <div className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-sm font-semibold text-white">Evaluation Result</h4>
              <div className="flex items-center gap-2">
                {result.requires_approval ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-yellow-500/15 border border-yellow-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-yellow-400">
                    <ExclamationTriangleIcon className="w-3 h-3" />
                    Requires Approval
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                    <ShieldCheckIcon className="w-3 h-3" />
                    {result.auto_execute ? 'Auto-Execute' : 'Safe'}
                  </span>
                )}
              </div>
            </div>

            {/* Mode & Risk */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              {/* Predicted Mode */}
              <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-4">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Predicted Mode</p>
                <div className="flex items-center gap-2">
                  <span className={cn('w-2.5 h-2.5 rounded-full', MODE_CONFIG[result.mode].dotColor)} />
                  <span className={cn('text-lg font-bold', MODE_CONFIG[result.mode].color)}>
                    {MODE_CONFIG[result.mode].label}
                  </span>
                </div>
              </div>

              {/* Risk Score */}
              <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-4">
                <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-2">Risk Score</p>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2.5 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={cn('h-full rounded-full transition-all duration-500', getRiskColor(result.risk_score).bar)}
                      style={{ width: `${Math.min(100, Math.max(0, result.risk_score * 100))}%` }}
                    />
                  </div>
                  <span className={cn('text-xl font-mono font-bold w-16 text-right', getRiskColor(result.risk_score).text)}>
                    {(result.risk_score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Reason */}
            <div className="rounded-lg bg-[#141414] border border-white/[0.04] p-4">
              <p className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Decision Reason</p>
              <p className="text-sm text-zinc-300 leading-relaxed">{result.reason}</p>
            </div>
          </div>

          {/* ── Why This Result? ──────────────────────────────────────── */}
          <div className="border-t border-white/[0.06]">
            <button
              onClick={() => setShowExplanation(!showExplanation)}
              className="w-full flex items-center justify-between px-5 py-3 text-sm text-zinc-400 hover:text-zinc-300 hover:bg-white/[0.02] transition-colors"
            >
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
                </svg>
                Why this result?
              </span>
              <ChevronDownIcon className="w-4 h-4" open={showExplanation} />
            </button>
            {showExplanation && (
              <div className="px-5 pb-4 space-y-3">
                <div className="rounded-lg bg-[#0A0A0A] border border-white/[0.04] p-4 space-y-3">
                  {/* Layer 1 */}
                  <div>
                    <p className="text-[10px] font-semibold text-[#FF7F11] uppercase tracking-wider mb-1">Layer 1: Per-Category Preference</p>
                    <p className="text-xs text-zinc-400">
                      {ACTION_TYPES.find(a => a.key === selectedAction)?.label || selectedAction} actions are configured to run in{' '}
                      <span className={cn('font-semibold', MODE_CONFIG[result.mode].color)}>
                        {MODE_CONFIG[result.mode].label}
                      </span>{' '}
                      mode. This can be overridden by the global mode setting.
                    </p>
                  </div>
                  {/* Layer 2 */}
                  <div className="border-t border-white/[0.04] pt-3">
                    <p className="text-[10px] font-semibold text-[#FF7F11] uppercase tracking-wider mb-1">Layer 2: Risk Score Evaluation</p>
                    <p className="text-xs text-zinc-400">
                      The risk score of <span className={cn('font-mono font-semibold', getRiskColor(result.risk_score).text)}>{(result.risk_score * 100).toFixed(1)}%</span>{' '}
                      was calculated based on action type, payload content, customer history, and policy rules.
                    </p>
                  </div>
                  {/* Layer 3 */}
                  <div className="border-t border-white/[0.04] pt-3">
                    <p className="text-[10px] font-semibold text-[#FF7F11] uppercase tracking-wider mb-1">Layer 3: Global Mode Check</p>
                    <p className="text-xs text-zinc-400">
                      The current global shadow mode determines the maximum autonomy. Shadow mode blocks all execution, Supervised requires approval, Graduated allows auto-execution for low-risk actions.
                    </p>
                  </div>
                  {/* Layer 4 */}
                  <div className="border-t border-white/[0.04] pt-3">
                    <p className="text-[10px] font-semibold text-[#FF7F11] uppercase tracking-wider mb-1">Layer 4: Safety Floor</p>
                    <p className="text-xs text-zinc-400">
                      Hard safety rules are always enforced regardless of mode. Refunds over $1,000, account deletions, and bulk operations always require human approval.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* ── Simulation History ────────────────────────────────────────── */}
      {history.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[#FF7F11]">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
              </svg>
            </span>
            <h4 className="text-sm font-semibold text-white">Recent Simulations</h4>
            <span className="text-[10px] text-zinc-600">({history.length})</span>
          </div>
          <div className="space-y-1.5">
            {history.map((sim, i) => {
              const rc = getRiskColor(sim.result.risk_score);
              return (
                <div
                  key={`${sim.timestamp}-${i}`}
                  className="flex items-center gap-3 rounded-lg bg-[#141414] border border-white/[0.04] px-4 py-2.5"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-zinc-300">
                        {ACTION_TYPES.find(a => a.key === sim.actionType)?.label || sim.actionType}
                      </span>
                      <span className={cn('w-1.5 h-1.5 rounded-full', MODE_CONFIG[sim.result.mode].dotColor)} />
                    </div>
                  </div>
                  <span className={cn('text-xs font-mono font-medium', rc.text)}>
                    {(sim.result.risk_score * 100).toFixed(0)}%
                  </span>
                  {sim.result.requires_approval ? (
                    <ExclamationTriangleIcon className="w-3.5 h-3.5 text-yellow-500" />
                  ) : (
                    <CheckIcon className="w-3.5 h-3.5 text-emerald-500" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
