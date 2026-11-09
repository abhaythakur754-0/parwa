/**
 * GhostwriterDraftsCard — the self-extending loop's human gate.
 *
 * Gap → AI drafts from YOUR own flagged conversations + YOUR own KB →
 * you approve → the approved article feeds the agent's knowledge store
 * (the live pipeline reads it on the next related question).
 *
 * Honesty rules enforced here:
 *  - Nothing publishes without the Approve click.
 *  - "In agent knowledge" only shows when the API confirmed published=true.
 *  - A failed publish is shown as a warning with a Retry Publish action —
 *    approval is never silently assumed to have gone live.
 */

'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import {
  PenLine,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  RefreshCw,
  BookOpenCheck,
  AlertTriangle,
} from 'lucide-react';
import { useGhostwriterDrafts } from '@/hooks/useGhostwriterDrafts';
import type { GhostwriterDraft } from '@/lib/ghostwriter-api';

// ── Status badge ─────────────────────────────────────────────────────

function StatusBadge({ status }: { status: GhostwriterDraft['status'] }) {
  if (status === 'approved') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
        <CheckCircle2 className="w-3 h-3" />
        Approved
      </span>
    );
  }
  if (status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-500/15 text-zinc-500 border border-zinc-500/30">
        <XCircle className="w-3 h-3" />
        Rejected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
      <PenLine className="w-3 h-3" />
      Draft
    </span>
  );
}

// ── Single draft row ─────────────────────────────────────────────────

function DraftRow({
  draft,
  publishOk,
  publishFailure,
  onApprove,
  onReject,
  isActing,
}: {
  draft: GhostwriterDraft;
  publishOk: boolean;
  publishFailure: string | null;
  onApprove: (id: string) => Promise<{ published: boolean } | null>;
  onReject: (id: string) => void;
  isActing: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  const sourceCount = Array.isArray(draft.sources) ? draft.sources.length : 0;
  const flaggedCount = draft.based_on?.flagged_count ?? 0;

  const handleApproveOrRetry = async () => {
    setIsRetrying(true);
    await onApprove(draft.id);
    setIsRetrying(false);
  };

  const busy = isActing || isRetrying;
  const showActions =
    draft.status === 'draft' ||
    (draft.status === 'approved' && publishFailure !== null);

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02]">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-start justify-between gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors rounded-t-xl"
        aria-expanded={expanded}
      >
        <div className="min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {draft.title || draft.gap_topic}
          </p>
          <div className="flex flex-wrap items-center gap-2 mt-1">
            <StatusBadge status={draft.status} />
            {publishOk && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                <BookOpenCheck className="w-3 h-3" />
                In agent knowledge
              </span>
            )}
            <span className="text-[10px] text-zinc-600">
              {flaggedCount > 0 && `${flaggedCount} flagged conversation${flaggedCount === 1 ? '' : 's'}`}
              {flaggedCount > 0 && sourceCount > 0 && ' · '}
              {sourceCount > 0 && `${sourceCount} source${sourceCount === 1 ? '' : 's'}`}
              {flaggedCount === 0 && sourceCount === 0 && 'No sources found'}
              {draft.created_at && ` · ${new Date(draft.created_at).toLocaleDateString()}`}
            </span>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-zinc-600 shrink-0 mt-1" />
        ) : (
          <ChevronDown className="w-4 h-4 text-zinc-600 shrink-0 mt-1" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-white/[0.06]">
          {publishFailure && (
            <div className="flex items-start gap-2 mt-3 rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-300">
                <p className="font-medium">Approved, but NOT yet in agent knowledge.</p>
                <p className="text-amber-400/80 mt-0.5">{publishFailure}</p>
                <p className="text-amber-400/60 mt-0.5">
                  Your approval is recorded. Retry publish — it is safe to try again.
                </p>
              </div>
            </div>
          )}

          <div className="mt-3 rounded-lg bg-black/20 border border-white/[0.04] p-3 max-h-64 overflow-y-auto">
            <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">
              {draft.content || 'No article content.'}
            </pre>
          </div>

          {showActions && (
            <div className="flex flex-wrap items-center gap-2 mt-3">
              {draft.status === 'draft' ? (
                <>
                  <Button
                    size="sm"
                    onClick={handleApproveOrRetry}
                    disabled={busy}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
                  >
                    {busy ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    )}
                    Approve &amp; publish
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onReject(draft.id)}
                    disabled={busy}
                    className="text-zinc-400 hover:text-white hover:bg-white/5"
                  >
                    Reject
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  onClick={handleApproveOrRetry}
                  disabled={busy}
                  className="bg-amber-600/80 hover:bg-amber-500 text-white gap-1.5"
                >
                  {busy ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5" />
                  )}
                  Retry publish
                </Button>
              )}
            </div>
          )}

          {draft.status === 'draft' && (
            <p className="text-[10px] text-zinc-600 mt-2">
              Approving publishes this article to your agent&apos;s knowledge store. Nothing goes live without this click.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main card ────────────────────────────────────────────────────────

export function GhostwriterDraftsCard() {
  const {
    drafts,
    total,
    isLoading,
    isCreating,
    actingDraftId,
    error,
    createDraft,
    approveDraft,
    rejectDraft,
    refresh,
  } = useGhostwriterDrafts();

  const [topic, setTopic] = useState('');
  // Per-row publish feedback, keyed by draft id (cleared on refresh changes)
  const [publishOkIds, setPublishOkIds] = useState<Record<string, boolean>>({});
  const [publishFailures, setPublishFailures] = useState<Record<string, string>>({});

  const handleCreate = async () => {
    const trimmed = topic.trim();
    if (trimmed.length < 3) {
      toast.error('Topic is too short', {
        description: 'Describe the gap in a few words, e.g. "UK payout timing".',
      });
      return;
    }
    const created = await createDraft(trimmed);
    if (created) {
      setTopic('');
      toast.success('Draft ready for review', {
        description: 'Drafted from your own data. Nothing is published until you approve.',
      });
    } else {
      toast.error('Could not draft the article', {
        description: 'One AI call is made per draft — please try again in a moment.',
      });
    }
  };

  const handleApprove = async (draftId: string) => {
    const result = await approveDraft(draftId);
    if (!result) return null;
    if (result.published) {
      setPublishOkIds((prev) => ({ ...prev, [draftId]: true }));
      setPublishFailures((prev) => {
        const next = { ...prev };
        delete next[draftId];
        return next;
      });
      toast.success('Published to your agent\'s knowledge', {
        description: 'The next customer question on this topic is answered from this article.',
      });
    } else {
      setPublishFailures((prev) => ({
        ...prev,
        [draftId]: result.publish_error || 'Publish failed for an unknown reason.',
      }));
      toast.warning('Approved — but not published yet', {
        description: 'The article is approved. Retry publish from the draft row.',
      });
    }
    return result;
  };

  const handleReject = async (draftId: string) => {
    const ok = await rejectDraft(draftId);
    if (ok) {
      toast.info('Draft rejected', { description: 'Nothing was published.' });
    }
  };

  const pendingCount = drafts.filter((d) => d.status === 'draft').length;

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#2C2C31] p-4 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 border-b border-white/[0.06]">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-orange-500/15 flex items-center justify-center">
              <PenLine className="w-4 h-4 text-orange-400" />
            </span>
            Ghostwriter Drafts
          </h2>
          <p className="text-xs text-zinc-500 mt-1.5 max-w-xl">
            Close knowledge gaps: the AI drafts an article from your own flagged
            conversations and knowledge base. You approve — then it feeds your
            agent&apos;s knowledge. Nothing publishes without your click.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {pendingCount > 0 && (
            <span className="text-[10px] px-2 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
              {pendingCount} awaiting review
            </span>
          )}
          <button
            onClick={() => refresh()}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Draft-this-gap input */}
      <div className="flex flex-col sm:flex-row gap-2 pt-4">
        <Input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !isCreating) handleCreate(); }}
          placeholder="Describe a knowledge gap — e.g. &quot;UK payout timing&quot;"
          className="bg-white/[0.03] border-white/10 text-white placeholder:text-zinc-600 focus:border-orange-500/50 focus:ring-orange-500/20"
          maxLength={255}
          aria-label="Knowledge gap topic"
        />
        <Button
          onClick={handleCreate}
          disabled={isCreating || topic.trim().length < 3}
          className="bg-orange-500 hover:bg-orange-600 text-white gap-2 shrink-0 min-h-[40px]"
        >
          {isCreating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Drafting… (up to a minute)
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Draft this gap
            </>
          )}
        </Button>
      </div>
      <p className="text-[10px] text-zinc-600 mt-1.5">
        Drafting makes one AI call using only your company&apos;s data. Daily cap applies.
      </p>

      {/* List */}
      <div className="mt-4 max-h-96 overflow-y-auto space-y-2 pr-1">
        {isLoading ? (
          <>
            <Skeleton className="h-16 w-full bg-white/[0.04]" />
            <Skeleton className="h-16 w-full bg-white/[0.04]" />
          </>
        ) : drafts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center mb-3">
              <PenLine className="w-5 h-5 text-orange-400" />
            </div>
            <p className="text-sm text-zinc-400">No drafts yet</p>
            <p className="text-xs text-zinc-600 mt-1 max-w-sm">
              When the QA Report Card flags a repeated knowledge gap, draft an
              article here — or type a topic above to close it now.
            </p>
          </div>
        ) : (
          drafts.map((draft) => (
            <DraftRow
              key={draft.id}
              draft={draft}
              publishOk={publishOkIds[draft.id] === true}
              publishFailure={publishFailures[draft.id] || null}
              onApprove={handleApprove}
              onReject={handleReject}
              isActing={actingDraftId === draft.id}
            />
          ))
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 mt-3">{error}</p>
      )}
      {total > drafts.length && (
        <p className="text-[10px] text-zinc-600 mt-2">
          Showing {drafts.length} of {total} drafts
        </p>
      )}
    </div>
  );
}
