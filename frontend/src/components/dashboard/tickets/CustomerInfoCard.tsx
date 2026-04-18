'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import type { CustomerInfo } from '@/types/ticket';

interface CustomerInfoCardProps {
  customer: CustomerInfo;
  className?: string;
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 2_592_000) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function CustomerInfoCard({ customer, className }: CustomerInfoCardProps) {
  const initials = customer.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 space-y-3', className)}>
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-400 flex items-center justify-center text-white text-sm font-bold shrink-0">
          {initials}
        </div>
        <div className="min-w-0">
          <h4 className="text-sm font-semibold text-white truncate">{customer.name}</h4>
          {customer.company && (
            <p className="text-xs text-zinc-500 truncate">{customer.company}</p>
          )}
        </div>
      </div>

      {/* Contact info */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 text-xs">
          <svg className="w-3.5 h-3.5 text-zinc-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
          </svg>
          <span className="text-zinc-400 truncate">{customer.email}</span>
        </div>
        {customer.phone && (
          <div className="flex items-center gap-2 text-xs">
            <svg className="w-3.5 h-3.5 text-zinc-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25Z" />
            </svg>
            <span className="text-zinc-400">{customer.phone}</span>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.04]">
        <div className="text-center">
          <p className="text-sm font-semibold text-white">{customer.total_tickets}</p>
          <p className="text-[10px] text-zinc-500">Tickets</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-emerald-400">{customer.resolved_tickets}</p>
          <p className="text-[10px] text-zinc-500">Resolved</p>
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-amber-400">{customer.avg_csat ? customer.avg_csat.toFixed(1) : '—'}</p>
          <p className="text-[10px] text-zinc-500">CSAT</p>
        </div>
      </div>

      {/* Tags */}
      {customer.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {customer.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 rounded-md bg-white/[0.04] border border-white/[0.06] text-[10px] font-medium text-zinc-400"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Active info */}
      <div className="flex items-center justify-between text-[10px] text-zinc-600 pt-1">
        <span>First seen: {timeAgo(customer.first_seen)}</span>
        <span>Last active: {timeAgo(customer.last_active)}</span>
      </div>
    </div>
  );
}
