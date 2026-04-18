'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

/**
 * ExportModal - Modal for exporting tickets
 *
 * Features:
 * - Multiple export formats (CSV, JSON, PDF)
 * - Filter options
 * - Progress indication
 * - Download link
 */

export interface ExportFilters {
  status?: string[];
  priority?: string[];
  category?: string[];
  date_from?: string;
  date_to?: string;
  assigned_to?: string;
}

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketIds?: string[];
  totalTickets?: number;
  className?: string;
}

type ExportFormat = 'csv' | 'json' | 'pdf';
type ExportStatus = 'idle' | 'exporting' | 'success' | 'error';

const EXPORT_FORMATS: { value: ExportFormat; label: string; description: string; icon: React.ReactNode }[] = [
  {
    value: 'csv',
    label: 'CSV',
    description: 'Spreadsheet-compatible format, best for data analysis',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 1.5v-1.5m0 0c0-.621.504-1.125 1.125-1.125m0 0h7.5" />
      </svg>
    ),
  },
  {
    value: 'json',
    label: 'JSON',
    description: 'Full data with messages, best for API integration',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    ),
  },
  {
    value: 'pdf',
    label: 'PDF',
    description: 'Printable document format, best for sharing',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
      </svg>
    ),
  },
];

export default function ExportModal({
  isOpen,
  onClose,
  ticketIds,
  totalTickets = 0,
  className,
}: ExportModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('csv');
  const [status, setStatus] = useState<ExportStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [filters, setFilters] = useState<ExportFilters>({});

  // Cleanup: revoke object URL to prevent memory leak
  useEffect(() => {
    return () => {
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl);
      }
    };
  }, [downloadUrl]);

  if (!isOpen) return null;

  const handleExport = async () => {
    setStatus('exporting');
    setError(null);
    setDownloadUrl(null);

    try {
      const endpoint = selectedFormat === 'pdf'
        ? `/api/tickets/export/${ticketIds?.[0]}/pdf`
        : `/api/tickets/export/${selectedFormat}`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_ids: ticketIds,
          filters,
          include_messages: selectedFormat === 'json',
        }),
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      if (selectedFormat === 'json') {
        // JSON response - trigger download
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
      } else {
        // CSV/PDF - get blob
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);
      }

      setStatus('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
      setStatus('error');
    }
  };

  const handleClose = () => {
    setStatus('idle');
    setError(null);
    setDownloadUrl(null);
    setSelectedFormat('csv');
    onClose();
  };

  const exportCount = ticketIds?.length || totalTickets;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className={cn(
        'relative w-full max-w-lg bg-[#1A1A1A] rounded-xl border border-white/[0.06] shadow-2xl',
        className
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.06]">
          <h2 className="text-lg font-semibold text-white">Export Tickets</h2>
          <button
            onClick={handleClose}
            className="p-1 rounded hover:bg-white/[0.06] text-zinc-400 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Export count */}
          <div className="text-sm text-zinc-400">
            Exporting <span className="text-white font-medium">{exportCount}</span> ticket{exportCount !== 1 ? 's' : ''}
          </div>

          {/* Format selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-400">Format</label>
            <div className="grid grid-cols-3 gap-2">
              {EXPORT_FORMATS.map((format) => (
                <button
                  key={format.value}
                  onClick={() => setSelectedFormat(format.value)}
                  disabled={format.value === 'pdf' && ticketIds && ticketIds.length > 1}
                  className={cn(
                    'p-3 rounded-lg border text-left transition-all',
                    selectedFormat === format.value
                      ? 'bg-violet-500/10 border-violet-500'
                      : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.1]',
                    format.value === 'pdf' && ticketIds && ticketIds.length > 1 && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <div className={cn(
                    'mb-2',
                    selectedFormat === format.value ? 'text-violet-400' : 'text-zinc-500'
                  )}>
                    {format.icon}
                  </div>
                  <p className={cn(
                    'text-sm font-medium',
                    selectedFormat === format.value ? 'text-white' : 'text-zinc-300'
                  )}>
                    {format.label}
                  </p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">{format.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Status messages */}
          {status === 'exporting' && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
              <svg className="w-5 h-5 text-violet-400 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm text-violet-400">Generating export...</span>
            </div>
          )}

          {status === 'success' && downloadUrl && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <p className="text-sm text-emerald-400 mb-2">Export ready!</p>
              <a
                href={downloadUrl}
                download={`tickets_export.${selectedFormat}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm font-medium text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Download {selectedFormat.toUpperCase()}
              </a>
            </div>
          )}

          {status === 'error' && error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t border-white/[0.06]">
          <button
            onClick={handleClose}
            className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={status === 'exporting'}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all',
              status === 'exporting'
                ? 'bg-zinc-700 text-zinc-400 cursor-not-allowed'
                : 'bg-violet-500 hover:bg-violet-600 text-white'
            )}
          >
            {status === 'exporting' ? 'Exporting...' : 'Export'}
          </button>
        </div>
      </div>
    </div>
  );
}
