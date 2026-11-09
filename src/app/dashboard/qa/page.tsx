/**
 * AI Quality — The Report Card (/dashboard/qa)
 *
 * One screen that shows the grades: every conversation the AI handled gets
 * scored the moment it ends. Screen mirrors documents/QA_Dashboard_OnePager.md:
 *
 *   ┌ KPI row ────────────────────────────────────────────────────┐
 *   │ Average quality │ Conversations graded │ Flagged │ Checks   │
 *   └─────────────────────────────────────────────────────────────┘
 *   ┌ Problems panel (flagged conversations, each with the reason)┐
 *   ┌ Quality breakdown: volume, channels, top flag reasons       ┐
 *   ┌ "How the grading runs" honesty strip                        ┘
 *
 * Data source: GET /api/qa/summary + /api/qa/conversations (both
 * company-locked server-side — a tenant can never see another tenant's
 * grades). Read-only screen: grades are written by the pipeline hook.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import KPICard from '@/components/dashboard/KPICard';
import {
  qaApi,
  type QaSummary,
  type QaFlaggedConversation,
} from '@/lib/qa-api';
import { ghostwriterApi } from '@/lib/ghostwriter-api';
import { getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';
import {
  Gauge,
  MessagesSquare,
  Flag,
  ShieldCheck,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Info,
  ListChecks,
  FilePlus2,
} from 'lucide-react';

// ── Small building blocks ─────────────────────────────────────────────

function SectionCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 sm:p-6">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>
          {subtitle && <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function ReasonChip({ reason }: { reason: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/25">
      {reason.replace(/_/g, ' ')}
    </span>
  );
}

function ChannelChip({ channel }: { channel: string | null }) {
  if (!channel) return <span className="text-xs text-zinc-600">—</span>;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/25">
      {channel}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-zinc-600">—</span>;
  }
  const tone =
    score >= 85
      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
      : score >= 70
        ? 'bg-amber-500/10 text-amber-400 border-amber-500/25'
        : 'bg-red-500/10 text-red-400 border-red-500/25';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${tone}`}>
      {Math.round(score)}/100
    </span>
  );
}

/** Simple vertical-scaled bar strip for volume_by_day (last N days). */
function VolumeBars({ volumeByDay }: { volumeByDay: Record<string, number> }) {
  const days = Object.entries(volumeByDay)
    .filter(([d]) => d !== 'unknown')
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-14);
  const max = Math.max(1, ...days.map(([, v]) => v));

  if (days.length === 0) {
    return <p className="text-xs text-zinc-600">No graded conversations in this window yet.</p>;
  }

  return (
    <div className="flex items-end gap-1.5 h-24" aria-label="Conversations graded per day">
      {days.map(([day, v]) => (
        <div key={day} className="flex-1 flex flex-col items-center gap-1 group">
          <span className="text-[9px] text-zinc-500 opacity-0 group-hover:opacity-100 transition-opacity">
            {v}
          </span>
          <div
            className="w-full rounded-t bg-orange-500/60 group-hover:bg-orange-400 transition-colors"
            style={{ height: `${Math.max(4, (v / max) * 72)}px` }}
            title={`${day}: ${v}`}
          />
          <span className="text-[8px] text-zinc-600">{day.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Derive a Ghostwriter topic from a flagged conversation.
 *
 * The customer's own question is the honest topic — it's the thing the
 * knowledge base failed to answer. Falls back to the flag reasons when no
 * excerpt was recorded (older rows). Backend accepts 3-255 chars.
 */
function topicFromConvo(convo: QaFlaggedConversation): string {
  const excerpt = (convo.question_excerpt || '').trim();
  if (excerpt.length >= 3) return excerpt.slice(0, 255);
  const reasons = (convo.flag_reasons || []).map((r) => r.replace(/_/g, ' ')).join(', ');
  const fallback = reasons
    ? `Knowledge gap: ${reasons}`
    : 'Knowledge gap from a flagged conversation';
  return fallback.slice(0, 255);
}

/** Expandable row in the Problems panel. */
function FlaggedRow({ convo }: { convo: QaFlaggedConversation }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const hasDetails =
    (convo.evidence && convo.evidence.length > 0) ||
    convo.officer_notes ||
    convo.officer_verdict;

  /**
   * Close the loop: flagged conversation → Ghostwriter draft → human
   * approves → article lands in the knowledge store. The draft is ONE
   * cheap LLM call over this company's own evidence — can take tens of
   * seconds, so the button stays disabled with a spinner meanwhile.
   */
  const draftGap = async () => {
    if (drafting) return;
    setDrafting(true);
    try {
      const draft = await ghostwriterApi.createDraft(topicFromConvo(convo));
      toast.success('Draft ready for your review', {
        description: draft.title || draft.gap_topic,
        action: {
          label: 'Open drafts',
          onClick: () => router.push('/dashboard/knowledge'),
        },
      });
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDrafting(false);
    }
  };

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] flex items-stretch">
      <button
        type="button"
        onClick={() => hasDetails && setOpen(!open)}
        className={`flex-1 min-w-0 text-left px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 ${
          hasDetails ? 'cursor-pointer hover:bg-white/[0.03]' : 'cursor-default'
        }`}
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm text-zinc-200 truncate">
            {convo.question_excerpt || '(no excerpt recorded)'}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
            <ChannelChip channel={convo.channel} />
            {(convo.flag_reasons || []).slice(0, 3).map((r) => (
              <ReasonChip key={r} reason={r} />
            ))}
            {(convo.flag_reasons || []).length > 3 && (
              <span className="text-[10px] text-zinc-500">
                +{(convo.flag_reasons || []).length - 3} more
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {convo.officer_verdict === 'pass' ? (
            <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400">
              <CheckCircle2 className="w-3 h-3" /> Officer: pass
            </span>
          ) : convo.officer_verdict === 'fail' ? (
            <span className="inline-flex items-center gap-1 text-[10px] text-red-400">
              <AlertTriangle className="w-3 h-3" /> Officer: fail
            </span>
          ) : null}
          <ScoreBadge score={convo.score} />
          {hasDetails && (
            <span className="text-zinc-500">
              {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </span>
          )}
        </div>
      </button>
      <div className="shrink-0 flex items-center pr-3 pl-1 border-l border-white/[0.04]">
        <button
          type="button"
          onClick={draftGap}
          disabled={drafting}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-zinc-400 hover:text-orange-400 hover:bg-orange-500/10 disabled:opacity-60 disabled:pointer-events-none transition-colors"
          title="Have Ghostwriter draft an article for this gap from your own docs — you approve before anything is used"
          aria-label={`Draft article for gap: ${convo.question_excerpt || convo.flag_reasons?.join(', ') || 'flagged conversation'}`}
        >
          {drafting ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
              Drafting…
            </>
          ) : (
            <>
              <FilePlus2 className="w-3.5 h-3.5" aria-hidden />
              Draft this gap
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

type RangeKey = 7 | 30 | 90;

export default function QaReportCardPage() {
  const [days, setDays] = useState<RangeKey>(30);
  const [summary, setSummary] = useState<QaSummary | null>(null);
  const [flagged, setFlagged] = useState<QaFlaggedConversation[]>([]);
  const [flaggedTotal, setFlaggedTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (range: RangeKey) => {
    setIsLoading(true);
    setError(null);
    try {
      const [s, c] = await Promise.all([
        qaApi.getSummary(range),
        qaApi.getFlaggedConversations(50, 0),
      ]);
      setSummary(s);
      setFlagged(c.conversations || []);
      setFlaggedTotal(c.total ?? 0);
    } catch (err) {
      const msg = getErrorMessage(err);
      setError(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load(days);
  }, [days, load]);

  const avg = summary?.average_score;

  return (
    <div className="space-y-6 p-4 sm:p-6" role="main" aria-label="AI Quality Report Card">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <Gauge className="w-5 h-5 text-orange-400" />
            AI Quality — The Report Card
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Every conversation the AI handles gets graded the moment it ends. 100% coverage — not a sample.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-white/[0.08] overflow-hidden" role="group" aria-label="Date range">
            {([7, 30, 90] as RangeKey[]).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  days === d
                    ? 'bg-orange-500/15 text-orange-400'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
                aria-pressed={days === d}
              >
                {d}d
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => load(days)}
            className="p-2 rounded-lg border border-white/[0.08] text-zinc-400 hover:text-zinc-200 hover:border-white/[0.15] transition-colors"
            aria-label="Refresh report card"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && !summary && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <p className="text-sm text-red-300 mb-3">{error}</p>
          <button
            type="button"
            onClick={() => load(days)}
            className="px-4 py-2 rounded-lg bg-orange-500/15 text-orange-400 text-sm font-medium hover:bg-orange-500/25 transition-colors"
          >
            Try again
          </button>
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPICard
          title="Average quality"
          value={avg === null || avg === undefined ? '—' : `${Math.round(avg)}/100`}
          subtitle="Recomputed after every conversation"
          icon={<Gauge className="w-5 h-5" />}
          variant={avg !== null && avg !== undefined ? (avg >= 85 ? 'success' : avg >= 70 ? 'warning' : 'danger') : 'default'}
          isLoading={isLoading}
        />
        <KPICard
          title="Conversations graded"
          value={summary ? summary.graded_total.toLocaleString() : '—'}
          subtitle={`Last ${days} days · 100% coverage, not a 2% sample`}
          icon={<MessagesSquare className="w-5 h-5" />}
          isLoading={isLoading}
        />
        <KPICard
          title="Flagged for review"
          value={summary ? summary.flagged_count.toLocaleString() : '—'}
          subtitle={summary ? `${summary.flagged_rate}% of graded — each with the reason why` : 'The suspicious few'}
          icon={<Flag className="w-5 h-5" />}
          variant={summary && summary.flagged_rate > 20 ? 'danger' : summary && summary.flagged_rate > 10 ? 'warning' : 'default'}
          isLoading={isLoading}
        />
        <KPICard
          title="Double-checks ran"
          value={summary ? `${summary.double_checks_ran.toLocaleString()} / ${summary.daily_cap}` : '—'}
          subtitle={`Officer reviews vs daily cap · grading cost $${summary ? summary.grading_cost_usd.toFixed(0) : '0'}`}
          icon={<ShieldCheck className="w-5 h-5" />}
          isLoading={isLoading}
        />
      </div>

      {/* Problems panel */}
      <SectionCard
        title="Problems caught"
        subtitle={`${flaggedTotal} flagged conversation${flaggedTotal === 1 ? '' : 's'} — click a row to see why, or draft the missing article`}
      >
        {isLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-white/[0.03] animate-pulse" />
            ))}
          </div>
        ) : flagged.length === 0 ? (
          <div className="text-center py-8">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
            <p className="text-sm text-zinc-400">No flagged conversations.</p>
            <p className="text-xs text-zinc-600 mt-1">
              When in doubt a conversation is flagged — silence here means the checklist found nothing suspicious.
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1 scrollbar-premium">
            {flagged.map((c) => (
              <FlaggedRow key={c.id} convo={c} />
            ))}
          </div>
        )}
      </SectionCard>

      {/* Quality breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SectionCard title="Volume" subtitle="Conversations graded per day">
          {isLoading ? (
            <div className="h-24 rounded bg-white/[0.03] animate-pulse" />
          ) : (
            <VolumeBars volumeByDay={summary?.volume_by_day || {}} />
          )}
        </SectionCard>

        <SectionCard title="Channels" subtitle="Where the graded conversations happened">
          {isLoading ? (
            <div className="h-24 rounded bg-white/[0.03] animate-pulse" />
          ) : summary && Object.keys(summary.by_channel).length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {Object.entries(summary.by_channel)
                .sort(([, a], [, b]) => b - a)
                .map(([ch, n]) => (
                  <span
                    key={ch}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-white/[0.04] text-zinc-300 border border-white/[0.08]"
                  >
                    {ch}
                    <span className="text-zinc-500">{n}</span>
                  </span>
                ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-600">No channel data yet.</p>
          )}
        </SectionCard>

        <SectionCard title="Top flag reasons" subtitle="What the checklist caught most">
          {isLoading ? (
            <div className="h-24 rounded bg-white/[0.03] animate-pulse" />
          ) : summary && summary.top_flag_reasons.length > 0 ? (
            <ul className="space-y-2">
              {summary.top_flag_reasons.slice(0, 6).map(([reason, n]) => (
                <li key={reason} className="flex items-center justify-between text-xs">
                  <span className="text-zinc-300 capitalize">{reason.replace(/_/g, ' ')}</span>
                  <span className="text-zinc-500 font-mono">{n}×</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-zinc-600">Nothing caught yet in this window.</p>
          )}
        </SectionCard>
      </div>

      {/* Honesty strip */}
      <SectionCard
        title="How the grading runs"
        subtitle="The honest version — no overclaims"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center gap-2 mb-2">
              <ListChecks className="w-4 h-4 text-emerald-400" />
              <h3 className="text-xs font-semibold text-zinc-200">Layer 1 — the checklist ($0)</h3>
            </div>
            <p className="text-xs text-zinc-500">
              Every reply passes a pure-code 5-point checklist (structure, logic, brand voice, tone, PII).
              No AI calls. No cost. Milliseconds.
            </p>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Info className="w-4 h-4 text-amber-400" />
              <h3 className="text-xs font-semibold text-zinc-200">Hard evidence ($0)</h3>
            </div>
            <p className="text-xs text-zinc-500">
              Facts are recorded: the same question asked twice, angry wording, repeat visits.
              When in doubt, the conversation is flagged — never silently passed.
            </p>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck className="w-4 h-4 text-orange-400" />
              <h3 className="text-xs font-semibold text-zinc-200">Layer 2 — the officer (capped)</h3>
            </div>
            <p className="text-xs text-zinc-500">
              Only flagged conversations (typically ~10%) get ONE cheap background review, capped at{' '}
              {summary ? summary.daily_cap : 500}/day. The customer never waits — the check happens after.
            </p>
          </div>
        </div>
        <p className="text-[11px] text-zinc-600 mt-4 flex items-center gap-1.5">
          <Loader2 className="w-3 h-3" aria-hidden />
          Fail-open by design: if QA is ever down, support works exactly as before. Nothing here can break a conversation.
        </p>
      </SectionCard>
    </div>
  );
}
