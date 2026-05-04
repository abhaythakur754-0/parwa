/**
 * PARWA ActionTicketCard (Week 6 — Day 4 Phase 6)
 *
 * Displays an action ticket with status indicator.
 * Statuses: pending → in_progress → completed / failed
 * Metadata: { ticket_type, status, result, created_at, completed_at }
 */

'use client';

import {
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  Ticket,
} from 'lucide-react';

interface ActionTicketCardProps {
  metadata: Record<string, unknown>;
}

const STATUS_CONFIG: Record<
  string,
  { icon: React.ReactNode; color: string; label: string }
> = {
  pending: {
    icon: <Clock className="w-4 h-4 text-amber-400" />,
    color: 'border-amber-500/15',
    label: 'Pending',
  },
  in_progress: {
    icon: <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />,
    color: 'border-blue-500/15',
    label: 'In Progress',
  },
  completed: {
    icon: <CheckCircle2 className="w-4 h-4 text-orange-400" />,
    color: 'border-orange-500/15',
    label: 'Completed',
  },
  failed: {
    icon: <XCircle className="w-4 h-4 text-red-400" />,
    color: 'border-red-500/15',
    label: 'Failed',
  },
};

const TYPE_LABELS: Record<string, string> = {
  otp_verification: 'Email Verification',
  otp_verified: 'Email Verified',
  payment_demo_pack: 'Demo Pack Payment',
  payment_variant: 'Variant Payment',
  payment_variant_completed: 'Variant Payment Done',
  demo_call: 'Demo Call',
  demo_call_completed: 'Demo Call Done',
  roi_import: 'ROI Import',
  handoff: 'Handoff to Customer Care',
};

export function ActionTicketCard({ metadata }: ActionTicketCardProps) {
  const status = (metadata.status as string) || 'pending';
  const ticketType = (metadata.ticket_type as string) || '';
  const result = metadata.result as Record<string, unknown> | null;
  const createdAt = metadata.created_at as string | null;
  const completedAt = metadata.completed_at as string | null;

  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const typeLabel = TYPE_LABELS[ticketType] || ticketType;

  return (
    <div className={`glass rounded-xl p-3 border ${config.color} max-w-sm w-full`}>
      <div className="flex items-center gap-2 mb-1.5">
        <Ticket className="w-3.5 h-3.5 text-white/40" />
        <span className="text-[11px] font-medium text-white/70">{typeLabel}</span>
        <div className="ml-auto flex items-center gap-1">
          {config.icon}
          <span className="text-[10px] text-white/40">{config.label}</span>
        </div>
      </div>

      {result && Object.keys(result).length > 0 && (
        <div className="mt-1.5 p-2 rounded-lg bg-white/[0.03] border border-white/5">
          <pre className="text-[10px] text-white/40 overflow-hidden whitespace-pre-wrap break-all">
            {JSON.stringify(result, null, 2).slice(0, 200)}
          </pre>
        </div>
      )}

      {createdAt && (
        <p className="text-[9px] text-white/20 mt-1.5">
          Created {new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          {completedAt && ` · Completed ${new Date(completedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        </p>
      )}
    </div>
  );
}
