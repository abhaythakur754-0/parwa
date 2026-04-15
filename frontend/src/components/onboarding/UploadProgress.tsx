'use client';

import React from 'react';
import { Progress } from '@/components/ui/progress';
import { CheckCircle2, Loader2, XCircle, Loader2Icon } from 'lucide-react';
import type { KnowledgeDocument, DocumentStatus } from '@/types/onboarding';

interface UploadProgressProps {
  documents: KnowledgeDocument[];
  isUploading: boolean;
}

export function UploadProgress({ documents, isUploading }: UploadProgressProps) {
  const total = documents.length;
  if (total === 0) return null;

  const counts: Record<DocumentStatus, number> = {
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0,
  };
  for (const doc of documents) {
    counts[doc.status]++;
  }

  const completed = counts.completed;
  const failed = counts.failed;
  const processing = counts.processing;
  // D13-P15: Count processing docs as 50% progress so the bar isn't stuck at 0%
  const effective = completed + (processing * 0.5);
  const percentage = total > 0 ? (effective / total) * 100 : 0;

  const allDone = completed === total;
  const hasFailures = failed > 0;
  const hasInProgress = processing > 0 || isUploading;

  // Color coding: green = all complete, blue = in-progress, red if any failed
  const barColor = allDone
    ? 'bg-green-500'
    : hasFailures
      ? 'bg-red-500'
      : 'bg-blue-500';

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Documents ({total})</h3>
        <div className="flex items-center gap-2">
          {isUploading && (
            <Loader2Icon className="h-4 w-4 animate-spin text-blue-500" />
          )}
          <p className="text-sm text-muted-foreground">
            {completed}/{total} processed
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative">
        <Progress
          value={percentage}
          className={`h-2 [&>[data-slot=progress-indicator]]:${barColor} transition-all duration-500`}
        />
      </div>

      {/* Status breakdown */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          {completed} completed
        </span>

        {(processing > 0 || isUploading) && (
          <span className="inline-flex items-center gap-1">
            <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />
            {processing + (isUploading ? 1 : 0)} processing
          </span>
        )}

        {counts.pending > 0 && (
          <span className="inline-flex items-center gap-1">
            <div className="h-3.5 w-3.5 rounded-full border border-yellow-400 bg-yellow-100 dark:bg-yellow-900/40" />
            {counts.pending} pending
          </span>
        )}

        {failed > 0 && (
          <span className="inline-flex items-center gap-1">
            <XCircle className="h-3.5 w-3.5 text-red-500" />
            {failed} failed
          </span>
        )}
      </div>
    </div>
  );
}
