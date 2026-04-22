'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  FileText,
  CheckCircle2,
  Loader2,
  XCircle,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react';
import type { KnowledgeDocument, DocumentStatus } from '@/types/onboarding';

interface FileListProps {
  documents: KnowledgeDocument[];
  onRetry: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  // D13-P13: Record<string, boolean> to support multiple concurrent deletes
  isRetrying?: Record<string, boolean>;
  isDeleting?: Record<string, boolean>;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return d.toLocaleDateString();
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  switch (status) {
    case 'completed':
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 border-0">
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Completed
        </Badge>
      );
    case 'processing':
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-0">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          Processing
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="destructive" className="border-0">
          <XCircle className="h-3 w-3 mr-1" />
          Failed
        </Badge>
      );
    case 'pending':
    default:
      return (
        <Badge
          variant="secondary"
          className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 border-0"
        >
          Pending
        </Badge>
      );
  }
}

export function FileList({
  documents,
  onRetry,
  onDelete,
  isRetrying = {},
  isDeleting = {},
}: FileListProps) {
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  // D13-P19: Force re-render every 60s to update relative timestamps
  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(timer);
  }, []);

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <Upload className="h-10 w-10 text-muted-foreground mb-3" />
        <p className="text-sm text-muted-foreground">No documents uploaded yet</p>
        <p className="text-xs text-muted-foreground mt-1">
          Upload files using the drop zone above
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-2" role="list" aria-label="Uploaded documents">
      {documents.map((doc) => {
        const isRetryingThis = !!isRetrying[doc.id];
        const isDeletingThis = !!isDeleting[doc.id];
        const isConfirmingDelete = confirmDeleteId === doc.id;

        return (
          <li key={doc.id}>
            <Card>
              <CardContent className="flex items-center justify-between py-3 px-4">
                {/* File info */}
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{doc.filename}</p>
                      {doc.status === 'failed' && doc.error_message && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <XCircle className="h-4 w-4 text-destructive shrink-0 cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs">
                            <p className="text-xs">{doc.error_message}</p>
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(doc.file_size)}
                      {doc.chunk_count != null && doc.status === 'completed' && (
                        <span className="ml-1">
                          &middot; {doc.chunk_count} chunks
                        </span>
                      )}
                      <span className="ml-1">&middot; {formatTimestamp(doc.created_at)}</span>
                    </p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  <StatusBadge status={doc.status} />

                  {doc.status === 'failed' && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => onRetry(doc.id)}
                      disabled={isRetryingThis}
                      aria-label={`Retry ${doc.filename}`}
                    >
                      <RefreshCw
                        className={`h-4 w-4 ${isRetryingThis ? 'animate-spin' : ''}`}
                      />
                    </Button>
                  )}

                  {isConfirmingDelete ? (
                    <div className="flex items-center gap-1">
                      <span className="text-xs text-destructive mr-1">Delete?</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                        onClick={() => {
                          onDelete(doc.id);
                          setConfirmDeleteId(null);
                        }}
                        disabled={isDeletingThis}
                        aria-label={`Confirm delete ${doc.filename}`}
                      >
                        Yes
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => setConfirmDeleteId(null)}
                        aria-label="Cancel delete"
                      >
                        No
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0"
                      onClick={() => setConfirmDeleteId(doc.id)}
                      disabled={isDeletingThis}
                      aria-label={`Delete ${doc.filename}`}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
