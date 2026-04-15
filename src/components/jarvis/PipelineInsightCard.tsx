/**
 * PARWA PipelineInsightCard (Week 8-11 Integration)
 *
 * Rich card showing the full AI pipeline analysis for a Jarvis response.
 * Displays: classification, sentiment, technique, model routing, PII status,
 * hallucination risk, CLARA quality, and RAG sources — all from Week 8-11 backend.
 *
 * Renders as a collapsible card inside the chat message area.
 */

'use client';

import { useState } from 'react';
import {
  Brain, ShieldCheck, Search, Eye, Sparkles, Cpu, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle2, XCircle, BookOpen,
} from 'lucide-react';
import type {
  PipelineResult,
  PIIResult,
  HallucinationResult,
  ClassificationResult,
  EscalationTrigger,
  TechniqueMappingResult,
  ModelRoutingResult,
  RAGMetadata,
} from '@/lib/ai-pipeline';

interface PipelineInsightCardProps {
  pipeline: Partial<PipelineResult>;
}

// ── Confidence Badge ────────────────────────────────────────────

function ConfidenceBadge({ overall, level }: { overall: number; level: string }) {
  const color =
    level === 'high'
      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
      : level === 'medium'
        ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
        : 'text-red-400 bg-red-500/10 border-red-500/20';

  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${color}`}>
      {overall}%
    </span>
  );
}

// ── Mini Progress Bar ───────────────────────────────────────────

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="h-1 w-full rounded-full bg-white/5 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

// ── CLARA Stage Row ─────────────────────────────────────────────

function CLARARow({ name, passed, score }: { name: string; passed: boolean; score: number }) {
  return (
    <div className="flex items-center justify-between gap-2 py-0.5">
      <span className="text-[10px] text-white/40 truncate">{name}</span>
      <div className="flex items-center gap-1.5 shrink-0">
        <MiniBar value={score} max={100} color={passed ? 'bg-emerald-400' : 'bg-red-400'} />
        <span className="text-[9px] text-white/25 w-6 text-right">{score}</span>
        {passed ? (
          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400/50" />
        ) : (
          <XCircle className="w-2.5 h-2.5 text-red-400/50" />
        )}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────

export function PipelineInsightCard({ pipeline }: PipelineInsightCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const p = pipeline;
  const hasPII = p.pii?.detected;
  const hasHallucination = p.hallucination?.risk && p.hallucination.risk !== 'none';
  const hasEscalation = p.escalation?.triggered;
  const hasClassification = p.classification?.primary && p.classification.primary !== 'general';
  const hasRAG = (p.ragMetadata?.sources?.length ?? 0) > 0;
  const hasCLARA = (p.clara?.stages?.length ?? 0) > 0;

  // If nothing interesting to show, don't render
  if (!hasPII && !hasHallucination && !hasEscalation && !hasClassification && !hasRAG && !hasCLARA) {
    return null;
  }

  const isNegative = p.escalation?.triggered || p.hallucination?.risk === 'high';

  return (
    <div
      className={`rounded-xl border overflow-hidden ${
        isNegative
          ? 'bg-amber-500/[0.03] border-amber-500/10'
          : 'bg-white/[0.02] border-white/[0.06]'
      }`}
    >
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left cursor-pointer hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className={`w-5 h-5 rounded flex items-center justify-center ${
            isNegative
              ? 'bg-amber-500/10'
              : 'bg-emerald-500/10'
          }`}>
            <Brain className="w-3 h-3 text-emerald-400" />
          </div>
          <span className="text-[11px] font-medium text-white/50">
            AI Pipeline
            {p.processingTime !== undefined && p.processingTime > 0 && (
              <span className="text-white/20 ml-1">({p.processingTime}ms)</span>
            )}
          </span>
          {/* Tags */}
          <div className="flex items-center gap-1 ml-1">
            {hasPII && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400/70 border border-amber-500/15">
                PII
              </span>
            )}
            {hasEscalation && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400/70 border border-red-500/15">
                Escalate
              </span>
            )}
            {hasHallucination && p.hallucination!.risk === 'high' && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400/70 border border-red-500/15">
                Risk
              </span>
            )}
            {p.confidence?.overall && p.confidence.overall > 0 && (
              <ConfidenceBadge overall={p.confidence.overall} level={p.confidence.level} />
            )}
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-3.5 h-3.5 text-white/20" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-white/20" />
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-2.5">
          {/* Classification */}
          {hasClassification && p.classification && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <Cpu className="w-2.5 h-2.5 text-emerald-400/40" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Classification</span>
              </div>
              <div className="flex flex-wrap gap-1 ml-4">
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300/70 border border-emerald-500/15">
                  {p.classification.primary}
                </span>
                {p.classification.secondary.map(s => (
                  <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/40 border border-white/5">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Sentiment + Technique */}
          {p.techniqueMapping && (
            <div className="flex items-center justify-between gap-2 ml-4">
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-2.5 h-2.5 text-emerald-400/40" />
                <span className="text-[10px] text-white/30">{p.techniqueMapping.primaryTechnique}</span>
              </div>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/5 text-white/30 border border-white/5">
                {p.techniqueMapping.tierAccess}
              </span>
            </div>
          )}

          {/* Model Routing */}
          {p.modelRouting && p.modelRouting.provider !== 'unknown' && (
            <div className="flex items-center justify-between gap-2 ml-4">
              <div className="flex items-center gap-1.5">
                <Cpu className="w-2.5 h-2.5 text-white/20" />
                <span className="text-[10px] text-white/30">
                  {p.modelRouting.provider} / {p.modelRouting.tier}
                  {p.modelRouting.failoverUsed && (
                    <span className="text-red-400/50 ml-1">(failover)</span>
                  )}
                </span>
              </div>
            </div>
          )}

          {/* PII Detection */}
          {hasPII && p.pii && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <Eye className="w-2.5 h-2.5 text-amber-400/50" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">PII Detected</span>
              </div>
              <div className="flex flex-wrap gap-1 ml-4">
                {p.pii.types.map(t => (
                  <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300/70 border border-amber-500/15">
                    {t}
                  </span>
                ))}
                <span className="text-[9px] text-white/20 ml-1">
                  {p.pii.redactedCount} item{p.pii.redactedCount !== 1 ? 's' : ''} redacted
                </span>
              </div>
            </div>
          )}

          {/* RAG Sources */}
          {hasRAG && p.ragMetadata && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <BookOpen className="w-2.5 h-2.5 text-blue-400/50" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Knowledge Sources</span>
              </div>
              <div className="flex flex-wrap gap-1 ml-4">
                {p.ragMetadata.sources.map((s, i) => (
                  <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300/60 border border-blue-500/15">
                    {s.replace(/_/g, ' ')}
                  </span>
                ))}
                {p.ragMetadata.reranked && (
                  <span className="text-[9px] text-white/20 ml-1">
                    {p.ragMetadata.afterRerank}/{p.ragMetadata.totalRetrieved} after rerank
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Escalation */}
          {hasEscalation && p.escalation && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="w-2.5 h-2.5 text-red-400/60" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Escalation Triggered</span>
              </div>
              <div className="flex items-center gap-2 ml-4">
                <span className="text-[10px] text-red-300/60">{p.escalation.reason.replace(/_/g, ' ')}</span>
                <MiniBar
                  value={p.escalation.sentimentScore}
                  max={100}
                  color="bg-red-400"
                />
                <span className="text-[9px] text-white/20">
                  {p.escalation.sentimentScore}/100
                </span>
              </div>
            </div>
          )}

          {/* Hallucination */}
          {hasHallucination && p.hallucination && p.hallucination.risk !== 'none' && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <AlertTriangle className="w-2.5 h-2.5 text-amber-400/60" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">Hallucination Check</span>
                <span className={`text-[9px] px-1 py-0.5 rounded ml-1 ${
                  p.hallucination.risk === 'high'
                    ? 'bg-red-500/10 text-red-400/70'
                    : p.hallucination.risk === 'medium'
                      ? 'bg-amber-500/10 text-amber-400/70'
                      : 'bg-white/5 text-white/30'
                }`}>
                  {p.hallucination.risk}
                </span>
              </div>
              {p.hallucination.patterns.length > 0 && (
                <div className="flex flex-wrap gap-1 ml-4">
                  {p.hallucination.patterns.map(pat => (
                    <span key={pat} className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/30 border border-white/5">
                      {pat}
                    </span>
                  ))}
                </div>
              )}
              <p className="text-[9px] text-white/20 mt-1 ml-4 italic">
                {p.hallucination.recommendation}
              </p>
            </div>
          )}

          {/* CLARA Quality Gate */}
          {hasCLARA && p.clara && (
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldCheck className="w-2.5 h-2.5 text-emerald-400/50" />
                <span className="text-[10px] text-white/30 uppercase tracking-wider">CLARA Quality Gate</span>
                <span className={`text-[9px] px-1 py-0.5 rounded ml-1 ${
                  p.clara.passed
                    ? 'bg-emerald-500/10 text-emerald-400/70'
                    : 'bg-red-500/10 text-red-400/70'
                }`}>
                  {p.clara.passed ? 'PASSED' : 'FAILED'}
                </span>
              </div>
              <div className="ml-4 space-y-0.5">
                {p.clara.stages.map((stage, i) => (
                  <CLARARow key={i} name={stage.name} passed={stage.passed} score={stage.score} />
                ))}
              </div>
              {p.clara.suggestions.length > 0 && !p.clara.passed && (
                <div className="mt-1 ml-4">
                  {p.clara.suggestions.slice(0, 2).map((s, i) => (
                    <p key={i} className="text-[9px] text-amber-300/50">
                      • {s}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PipelineInsightCard;
