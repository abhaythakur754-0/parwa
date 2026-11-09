'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Gauge,
  FileWarning,
  TrendingUp,
  FileQuestion,
  Languages,
  BarChart3,
  ClipboardCheck,
  ShieldCheck,
  ChevronDown,
  PenLine,
  Check,
  X,
  Loader2,
} from 'lucide-react';

/**
 * QaDashboardPreview — "The Report Card" section.
 *
 * Markets the AI QA feature (CEO-approved build):
 * every conversation is graded by a pure-code 5-point checklist (0 LLM calls),
 * hard evidence is recorded, and only the flagged minority gets one cheap
 * background review. This screen is what the client opens.
 *
 * The Knowledge-gaps panel also demos the GHOSTWRITER (approved build #2):
 * "Draft this gap" writes an article from the client's own data. In this
 * preview the flow is simulated with sample data; the real backend is
 * POST /api/ghostwriter/drafts + approve/reject (human approval only —
 * nothing auto-publishes).
 *
 * HONESTY RULES (standing):
 * - This is a LIVE PRODUCT PREVIEW WITH SAMPLE DATA — labelled as such.
 * - No escalation, no shadow mode, no competitor claims.
 * - Cost transparency is part of the pitch (grading = $0; reviews capped).
 *
 * In the product, panels are fed by GET /api/qa/summary and
 * GET /api/qa/conversations?flagged=true (locked to the caller's company).
 */

const kpis = [
  {
    icon: <Gauge className="w-4 h-4 text-orange-300" />,
    label: 'Average quality',
    value: '91.3',
    unit: '/ 100',
    note: 'every conversation graded',
  },
  {
    icon: <ClipboardCheck className="w-4 h-4 text-emerald-300" />,
    label: 'Conversations graded',
    value: '18,412',
    unit: 'this month',
    note: '100% coverage, not 2%',
  },
  {
    icon: <FileWarning className="w-4 h-4 text-rose-300" />,
    label: 'Flagged for review',
    value: '214',
    unit: '(1.2%)',
    note: 'each with the reason why',
  },
  {
    icon: <ShieldCheck className="w-4 h-4 text-amber-300" />,
    label: 'Double-checks ran',
    value: '208',
    unit: 'capped at 500/day',
    note: 'grading itself: $0',
  },
];

const problems = [
  {
    reason: 'Invented a policy',
    detail: 'Promised a 45-day return window — store policy says 30.',
    score: 62,
    meta: 'Refund chat · channel: email',
  },
  {
    reason: 'Missed the real question',
    detail: 'Customer asked about payout timing; reply described tracking.',
    score: 71,
    meta: 'Payout chat · channel: chat',
  },
  {
    reason: 'Tone mismatch',
    detail: 'Frustrated customer got a rushed, template-like answer.',
    score: 78,
    meta: 'Delay complaint · channel: sms',
  },
];

const techniques = [
  { name: 'Step-Back Reasoning', wins: 94, use: 'Refunds & billing' },
  { name: 'Empathy-First', wins: 88, use: 'Frustrated customers' },
  { name: 'Chain-of-Thought', wins: 91, use: 'Shipping & logistics' },
  { name: 'Reverse-Thinking', wins: 84, use: 'Edge cases' },
];

const gaps = [
  {
    topic: 'EU warranty claims',
    fails: 31,
    note: 'no help article exists',
    draft: {
      title: 'EU warranty claims — what is covered and how to file',
      body: 'EU warranty claims follow the 2-year statutory guarantee. To file: reply to your order email with your order number and a short description of the fault. Our team responds within one business day. Note: wear-and-tear and accidental damage are not covered — the article flags this for policy confirmation.',
      sources: ['your EU terms of sale (uploaded doc)', '31 flagged conversations'],
      basedOn: '31 flagged conversations · 8 sample questions',
    },
  },
  {
    topic: 'UK payout timing',
    fails: 19,
    note: 'article is outdated',
    draft: {
      title: 'UK payout timing — the current schedule',
      body: 'UK payouts are processed every Friday and arrive within 3 business days. If your payout is later than 5 business days, contact support with your payout reference. This draft replaces the outdated 2023 schedule — flagged for your confirmation.',
      sources: ['your payouts policy (uploaded doc)', '19 flagged conversations'],
      basedOn: '19 flagged conversations · 6 sample questions',
    },
  },
  {
    topic: 'Bulk-order discounts',
    fails: 12,
    note: 'article is thin',
    draft: {
      title: 'Bulk-order discounts — tiers and how to request one',
      body: 'Orders above 50 units qualify for tiered discounts. Request a quote by contacting sales with quantities and delivery postcode. The draft notes that exact tier percentages need your confirmation before publishing.',
      sources: ['your pricing sheet (uploaded doc)', '12 flagged conversations'],
      basedOn: '12 flagged conversations · 5 sample questions',
    },
  },
];

type DraftState =
  | { phase: 'idle' }
  | { phase: 'drafting'; topic: string }
  | { phase: 'ready'; topic: string }
  | { phase: 'approved'; topic: string }
  | { phase: 'rejected'; topic: string };

const languages = [
  { lang: 'English', score: 92 },
  { lang: 'Spanish', score: 91 },
  { lang: 'French', score: 90 },
  { lang: 'German', score: 84 },
];

const volume = [
  { day: 'Mon', n: 2410 },
  { day: 'Tue', n: 2530 },
  { day: 'Wed', n: 2380 },
  { day: 'Thu', n: 2610 },
  { day: 'Fri', n: 2470 },
  { day: 'Sat', n: 1980 },
  { day: 'Sun', n: 2030 },
];

const howItRuns = [
  'Every reply passes a 5-point checklist — pure code, 0 AI calls, $0.',
  'Facts are recorded: same question asked twice, angry words, return within 7 days.',
  'Only the suspicious few get one cheap double-check (capped daily).',
  'You open one screen and see the grades. That is the whole feature.',
];

function scoreColor(score: number): string {
  if (score >= 85) return 'text-emerald-300';
  if (score >= 75) return 'text-amber-300';
  return 'text-rose-300';
}

export default function QaDashboardPreview() {
  const [isInView, setIsInView] = useState(false);
  const [openProblem, setOpenProblem] = useState<number | null>(0);
  const [draftState, setDraftState] = useState<DraftState>({ phase: 'idle' });
  const sectionRef = useRef<HTMLElement>(null);

  const startDraft = (topic: string) => {
    setDraftState({ phase: 'drafting', topic });
    window.setTimeout(() => {
      setDraftState({ phase: 'ready', topic });
    }, 1200);
  };

  const activeGap =
    draftState.phase !== 'idle'
      ? gaps.find((g) => g.topic === draftState.topic)
      : undefined;

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsInView(true);
      },
      { threshold: 0.1 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  const reveal = (_delayMs = 0) =>
    `transition-all duration-700 motion-reduce:transition-none ${
      isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
    }`;

  const maxVolume = Math.max(...volume.map((v) => v.n));

  return (
    <section
      ref={sectionRef}
      id="qa-report-card"
      className="relative overflow-hidden py-16 sm:py-20 lg:py-24"
      aria-labelledby="qa-heading"
    >
      {/* Ambient glow — house orange */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute top-1/3 left-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-[140px]" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-orange-600/8 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className={`text-center mb-10 sm:mb-14 ${reveal(0)}`}>
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/25 text-orange-300 text-xs font-semibold mb-5">
            <Gauge className="w-3.5 h-3.5" />
            AI QA — The Report Card
          </span>
          <h2
            id="qa-heading"
            className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-5"
          >
            &ldquo;How do I know it still works?&rdquo;{' '}
            <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">
              Open the screen.
            </span>
          </h2>
          <p className="text-base sm:text-lg text-gray-400 max-w-2xl mx-auto">
            Every conversation is graded the moment it ends — 100% coverage, not a
            2% sample. This is the report card your team checks every Monday.
          </p>
          <p className="text-xs text-gray-500 mt-3">
            Live product preview with sample data — your own numbers appear once
            your agent runs.
          </p>
        </div>

        {/* KPI row */}
        <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5 mb-6 ${reveal(80)}`}>
          {kpis.map((k) => (
            <div
              key={k.label}
              className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5"
            >
              <div className="flex items-center gap-2 mb-2">
                {k.icon}
                <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  {k.label}
                </span>
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl sm:text-3xl font-bold text-white">{k.value}</span>
                <span className="text-xs text-gray-500">{k.unit}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1.5">{k.note}</p>
            </div>
          ))}
        </div>

        {/* Main grid */}
        <div className={`grid lg:grid-cols-3 gap-4 sm:gap-5 ${reveal(140)}`}>
          {/* Problem list — wide */}
          <div className="lg:col-span-2 rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="flex items-center gap-2 text-sm sm:text-base font-bold text-white mb-4">
              <FileWarning className="w-4 h-4 text-rose-300" />
              Problems caught this week
            </h3>
            <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
              {problems.map((p, i) => (
                <div
                  key={p.reason}
                  className="rounded-lg border border-white/10 bg-white/[0.03]"
                >
                  <button
                    type="button"
                    onClick={() => setOpenProblem(openProblem === i ? null : i)}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left min-h-[44px] hover:bg-white/[0.04] transition-colors rounded-lg"
                    aria-expanded={openProblem === i}
                  >
                    <span className="flex items-center gap-3 min-w-0">
                      <span className="shrink-0 rounded-md bg-rose-500/15 border border-rose-400/25 text-rose-300 text-[11px] font-semibold px-2 py-0.5">
                        {p.reason}
                      </span>
                      <span className="text-xs text-gray-500 truncate">{p.meta}</span>
                    </span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className={`text-sm font-bold ${scoreColor(p.score)}`}>{p.score}</span>
                      <ChevronDown
                        className={`w-4 h-4 text-gray-500 transition-transform ${openProblem === i ? 'rotate-180' : ''}`}
                      />
                    </span>
                  </button>
                  {openProblem === i && (
                    <p className="px-4 pb-3 text-sm text-gray-400">{p.detail}</p>
                  )}
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              Click a row to see why it was flagged. Every flag names its reason —
              never just a number.
            </p>
          </div>

          {/* Technique report card */}
          <div className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="flex items-center gap-2 text-sm sm:text-base font-bold text-white mb-4">
              <TrendingUp className="w-4 h-4 text-orange-300" />
              Technique report card
            </h3>
            <div className="space-y-3.5">
              {techniques.map((t) => (
                <div key={t.name}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-gray-200">{t.name}</span>
                    <span className="text-emerald-300 font-bold">{t.wins}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-orange-400 to-emerald-400"
                      style={{ width: `${t.wins}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5">{t.use}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-4">
              Which problem-solving style wins, per problem type. No other platform
              can show this.
            </p>
          </div>

          {/* Knowledge gaps — with the Ghostwriter demo */}
          <div className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="flex items-center gap-2 text-sm sm:text-base font-bold text-white mb-4">
              <FileQuestion className="w-4 h-4 text-amber-300" />
              Knowledge gaps found
            </h3>
            <div className="space-y-3">
              {gaps.map((g) => (
                <div key={g.topic} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-200">{g.topic}</p>
                    <p className="text-[11px] text-gray-500">{g.note}</p>
                    <button
                      type="button"
                      onClick={() => startDraft(g.topic)}
                      disabled={draftState.phase === 'drafting'}
                      className="mt-1.5 inline-flex min-h-[32px] items-center gap-1.5 rounded-md border border-orange-400/30 bg-orange-500/10 px-2.5 py-1 text-[11px] font-semibold text-orange-300 hover:bg-orange-500/20 transition-colors disabled:opacity-50 focus-visible-ring"
                      aria-label={`Draft an article for ${g.topic}`}
                    >
                      <PenLine className="w-3 h-3" />
                      Draft this gap
                    </button>
                  </div>
                  <span className="shrink-0 rounded-md bg-amber-500/15 border border-amber-400/25 text-amber-300 text-[11px] font-bold px-2 py-1">
                    {g.fails}×
                  </span>
                </div>
              ))}
            </div>

            {/* Ghostwriter draft drawer — simulated preview flow */}
            {draftState.phase === 'drafting' && activeGap && (
              <div className="mt-4 rounded-lg border border-orange-400/25 bg-orange-500/[0.06] p-4">
                <p className="flex items-center gap-2 text-sm font-semibold text-orange-200">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Reading your flagged conversations and documents…
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Drafting &ldquo;{activeGap.topic}&rdquo; from your own data — one cheap AI call, no background burn.
                </p>
              </div>
            )}
            {(draftState.phase === 'ready' || draftState.phase === 'approved' || draftState.phase === 'rejected') && activeGap && (
              <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.04] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-bold uppercase tracking-wide text-orange-300">
                      Draft — waiting for your approval
                    </p>
                    <p className="text-sm font-bold text-white mt-1">{activeGap.draft.title}</p>
                  </div>
                  {draftState.phase === 'approved' && (
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-md bg-emerald-500/15 border border-emerald-400/25 text-emerald-300 text-[11px] font-bold px-2 py-1">
                      <Check className="w-3 h-3" /> Approved
                    </span>
                  )}
                  {draftState.phase === 'rejected' && (
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-md bg-rose-500/15 border border-rose-400/25 text-rose-300 text-[11px] font-bold px-2 py-1">
                      <X className="w-3 h-3" /> Rejected
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-300 leading-relaxed mt-2">{activeGap.draft.body}</p>
                <p className="text-[11px] text-gray-500 mt-2">
                  Based on: {activeGap.draft.basedOn} · Sources: {activeGap.draft.sources.join(', ')}
                </p>
                {draftState.phase === 'ready' && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button
                      type="button"
                      onClick={() => setDraftState({ phase: 'approved', topic: activeGap.topic })}
                      className="inline-flex min-h-[36px] items-center gap-1.5 rounded-md bg-emerald-500/20 border border-emerald-400/30 px-3 py-1.5 text-xs font-bold text-emerald-300 hover:bg-emerald-500/30 transition-colors focus-visible-ring"
                    >
                      <Check className="w-3.5 h-3.5" /> Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => setDraftState({ phase: 'rejected', topic: activeGap.topic })}
                      className="inline-flex min-h-[36px] items-center gap-1.5 rounded-md bg-rose-500/15 border border-rose-400/30 px-3 py-1.5 text-xs font-bold text-rose-300 hover:bg-rose-500/25 transition-colors focus-visible-ring"
                    >
                      <X className="w-3.5 h-3.5" /> Needs work
                    </button>
                  </div>
                )}
                {draftState.phase === 'approved' && (
                  <p className="text-[11px] text-emerald-300/80 mt-3">
                    Approved — ready for your team to publish to the help center.
                  </p>
                )}
                {draftState.phase === 'rejected' && (
                  <p className="text-[11px] text-rose-300/80 mt-3">
                    Rejected — the gap stays on your list. Nothing was published.
                  </p>
                )}
                <p className="text-[10px] text-gray-600 mt-3">
                  Live product preview with sample data — in the product this draft is
                  written from your real conversations and your own documents, and
                  nothing publishes without your approval.
                </p>
              </div>
            )}

            <p className="text-xs text-gray-500 mt-4">
              Where the agent kept failing = where your help center is missing a
              page. Ghostwriter drafts the fix from your own data — you approve
              before anything goes live.
            </p>
          </div>

          {/* Language breakdown */}
          <div className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="flex items-center gap-2 text-sm sm:text-base font-bold text-white mb-4">
              <Languages className="w-4 h-4 text-emerald-300" />
              Quality per language
            </h3>
            <div className="space-y-2.5">
              {languages.map((l) => (
                <div key={l.lang} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">{l.lang}</span>
                  <span className={`text-sm font-bold ${scoreColor(l.score)}`}>{l.score}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-4">
              Spot a dip before your customers do — German fails here were all
              tone-related.
            </p>
          </div>

          {/* Volume */}
          <div className="rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6">
            <h3 className="flex items-center gap-2 text-sm sm:text-base font-bold text-white mb-4">
              <BarChart3 className="w-4 h-4 text-orange-300" />
              Conversations graded
            </h3>
            <div className="flex items-end justify-between gap-1.5 h-24" aria-hidden="true">
              {volume.map((v) => (
                <div key={v.day} className="flex-1 h-full flex flex-col justify-end items-center gap-1">
                  <div
                    className="w-full rounded-t-md bg-orange-400/60 hover:bg-orange-400 transition-colors"
                    style={{ height: `${Math.round((v.n / maxVolume) * 100)}%` }}
                    title={`${v.n} conversations`}
                  />
                  <span className="text-[10px] text-gray-500">{v.day}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-3">
              Every single one graded. Filters by date, language and channel in the
              product.
            </p>
          </div>
        </div>

        {/* How it runs — transparency strip */}
        <div className={`mt-6 rounded-xl border border-white/10 bg-white/[0.05] backdrop-blur-sm p-5 sm:p-6 ${reveal(200)}`}>
          <h3 className="text-sm sm:text-base font-bold text-white mb-3">
            How the grading runs — the honest version
          </h3>
          <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {howItRuns.map((step, i) => (
              <li key={step} className="flex items-start gap-2.5">
                <span className="shrink-0 w-6 h-6 rounded-md bg-orange-500/15 border border-orange-400/25 text-orange-300 text-xs font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <span className="text-xs sm:text-sm text-gray-400">{step}</span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-gray-500 mt-4">
            Monthly double-check cost at this sample volume: about $2. Grading
            itself: $0. A hard daily cap keeps it predictable — and your screen
            shows exactly how many ran.
          </p>
        </div>
      </div>
    </section>
  );
}
