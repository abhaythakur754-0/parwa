'use client';

/**
 * Phase 2 — "Learn from CRM history" card (Knowledge page).
 *
 * One button, one batch at a time: pulls 50 resolved tickets from the
 * tenant's CRM, distills how the team solved them into AI-wiki patterns,
 * and shows the progress. "Import next batch" continues until the CRM
 * history is exhausted. Requires a Zendesk/HubSpot connection (a
 * webhook-only CRM has no read API).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
  BookOpenCheck,
  CheckCircle2,
  Database,
  GraduationCap,
  Loader2,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';

interface BackfillState {
  status?: string;
  provider?: string;
  batches_done?: number;
  tickets_fetched?: number;
  patterns_learned?: number;
  duplicates_skipped?: number;
  cursor?: string | null;
  error?: string | null;
  last_run_at?: string;
}

interface StatusResponse {
  supported: boolean;
  provider: string | null;
  reason: string | null;
  state: BackfillState | null;
}

const POLL_MS = 2500;

export function CrmHistoryBackfillCard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/integrations/crm-history/status');
      if (res.ok) {
        setStatus((await res.json()) as StatusResponse);
      } else {
        setStatus({ supported: false, provider: null, reason: 'unavailable', state: null });
      }
    } catch {
      setStatus({ supported: false, provider: null, reason: 'unavailable', state: null });
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [loadStatus]);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/integrations/crm-history/status');
        if (!res.ok) return;
        const data = (await res.json()) as StatusResponse;
        const st = data.state?.status;
        if (st !== 'running') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setIsRunning(false);
          setStatus(data);
          if (st === 'done' || st === 'complete') {
            toast.success(
              st === 'complete'
                ? 'CRM history fully learned.'
                : 'Batch learned. Import the next batch to continue.'
            );
          } else if (st === 'error') {
            toast.error(data.state?.error || 'Backfill failed. Try again.');
          }
        } else {
          setStatus(data);
        }
      } catch {
        /* keep polling through transient errors */
      }
    }, POLL_MS);
  }, []);

  const startBackfill = useCallback(async () => {
    setIsRunning(true);
    try {
      const res = await fetch('/api/integrations/crm-history/backfill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_size: 50 }),
      });
      const data = await res.json();
      if (!res.ok || data.status === 'unsupported') {
        setIsRunning(false);
        toast.error(data.reason === 'no_crm_integration'
          ? 'Connect Zendesk or HubSpot first.'
          : (data.error || data.reason || 'Could not start the import.'));
        return;
      }
      toast.success('Import started — learning from your CRM history…');
      startPolling();
    } catch {
      setIsRunning(false);
      toast.error('Could not start the import. Please try again.');
    }
  }, [startPolling]);

  if (isLoading) {
    return (
      <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-4 animate-pulse h-[104px]" />
    );
  }

  const supported = status?.supported;
  const state = status?.state;
  const st = state?.status || 'idle';
  const busy = isRunning || st === 'running';

  return (
    <div className="bg-[#1A1A1A] rounded-xl border border-white/[0.06] p-4">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg bg-orange-500/10 flex items-center justify-center shrink-0">
          <GraduationCap className="w-5 h-5 text-orange-400" aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-white">Learn from CRM history</h3>
            {status?.provider && (
              <Badge variant="outline" className="text-[10px] border-white/10 text-zinc-400 capitalize">
                {status.provider}
              </Badge>
            )}
          </div>
          <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
            Teach PARWA from how your team solved past tickets. Each import reads 50
            resolved tickets from your CRM (read-only) and stores the solutions — the
            AI then answers similar tickets on its own.
          </p>

          {!supported && (
            <div className="flex items-center gap-2 mt-3 text-xs text-zinc-500">
              <Database className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              {status?.reason === 'webhook_only_crm_no_read_api'
                ? 'Your CRM is connected webhook-only (no read API) — history import needs Zendesk or HubSpot.'
                : 'Connect Zendesk or HubSpot in Integrations to enable history import.'}
            </div>
          )}

          {supported && (
            <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
              <Button
                size="sm"
                onClick={startBackfill}
                disabled={busy}
                className="bg-orange-500 hover:bg-orange-600 text-white h-8 disabled:opacity-60"
              >
                {busy ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
                    Learning…
                  </>
                ) : st === 'complete' ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
                    Re-scan history
                  </>
                ) : st === 'done' ? (
                  <>
                    <BookOpenCheck className="w-3.5 h-3.5" aria-hidden="true" />
                    Import next batch
                  </>
                ) : (
                  <>
                    <BookOpenCheck className="w-3.5 h-3.5" aria-hidden="true" />
                    Learn from CRM history
                  </>
                )}
              </Button>

              {state && state.batches_done ? (
                <div className="flex items-center gap-2 text-xs text-zinc-400 flex-wrap">
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
                    <strong className="text-emerald-400">{state.patterns_learned ?? 0}</strong> learned
                  </span>
                  <span aria-hidden="true">·</span>
                  <span>{state.tickets_fetched ?? 0} tickets read</span>
                  {(state.duplicates_skipped ?? 0) > 0 && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{state.duplicates_skipped} already known</span>
                    </>
                  )}
                  {st === 'done' && (
                    <>
                      <span aria-hidden="true">·</span>
                      <span className="text-orange-400">more history available</span>
                    </>
                  )}
                </div>
              ) : null}

              {st === 'error' && state?.error && (
                <span className="inline-flex items-center gap-1 text-xs text-red-400">
                  <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
                  {state.error}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
