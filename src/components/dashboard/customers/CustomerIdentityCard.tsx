'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';

/**
 * CustomerIdentityCard - Shows customer identity resolution info
 *
 * Displays:
 * - Customer profile with linked channels
 * - Identity confidence score
 * - Potential duplicate warnings
 * - Quick actions (merge, link channel)
 */

export interface CustomerChannel {
  id: string;
  channel_type: 'email' | 'phone' | 'chat' | 'sms' | 'voice' | 'slack' | 'webchat';
  external_id: string;
  is_verified: boolean;
  verified_at?: string;
  created_at: string;
}

export interface CustomerIdentity {
  id: string;
  email?: string;
  phone?: string;
  name?: string;
  external_id?: string;
  is_verified: boolean;
  channels: CustomerChannel[];
  created_at: string;
  updated_at: string;
}

export interface PotentialDuplicate {
  customer_1_id: string;
  customer_1_email?: string;
  customer_1_phone?: string;
  customer_1_name?: string;
  customer_2_id: string;
  customer_2_email?: string;
  customer_2_phone?: string;
  customer_2_name?: string;
  confidence: number;
  match_method: string;
}

interface CustomerIdentityCardProps {
  customerId: string;
  className?: string;
  onMergeClick?: (duplicate: PotentialDuplicate) => void;
  onLinkChannelClick?: () => void;
}

const CHANNEL_ICONS: Record<string, React.ReactNode> = {
  email: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75" />
    </svg>
  ),
  phone: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25Z" />
    </svg>
  ),
  slack: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" />
    </svg>
  ),
  webchat: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582" />
    </svg>
  ),
  chat: (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z" />
    </svg>
  ),
};

const CHANNEL_COLORS: Record<string, string> = {
  email: 'text-blue-400',
  phone: 'text-green-400',
  slack: 'text-indigo-400',
  webchat: 'text-cyan-400',
  chat: 'text-violet-400',
  sms: 'text-purple-400',
  voice: 'text-amber-400',
};

export default function CustomerIdentityCard({
  customerId,
  className,
  onMergeClick,
  onLinkChannelClick,
}: CustomerIdentityCardProps) {
  const [customer, setCustomer] = useState<CustomerIdentity | null>(null);
  const [duplicates, setDuplicates] = useState<PotentialDuplicate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Fetch customer details
        const customerRes = await fetch(`/api/customers/${customerId}`);
        if (!customerRes.ok) throw new Error('Failed to fetch customer');
        const customerData = await customerRes.json();

        // Fetch channels
        const channelsRes = await fetch(`/api/customers/${customerId}/channels`);
        const channelsData = channelsRes.ok ? await channelsRes.json() : [];

        // Fetch potential duplicates
        const duplicatesRes = await fetch(`/api/identity/matches?customer_id=${customerId}`);
        const duplicatesData = duplicatesRes.ok ? await duplicatesRes.json() : { duplicates: [] };

        setCustomer({
          ...customerData,
          channels: channelsData,
        });
        setDuplicates(duplicatesData.duplicates || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load customer');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [customerId]);

  if (loading) {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4', className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-10 w-10 rounded-full bg-white/[0.06]" />
          <div className="h-4 w-32 bg-white/[0.06] rounded" />
          <div className="h-3 w-48 bg-white/[0.06] rounded" />
        </div>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className={cn('rounded-xl bg-[#1A1A1A] border border-red-500/30 p-4', className)}>
        <p className="text-sm text-red-400">{error || 'Customer not found'}</p>
      </div>
    );
  }

  const initials = (customer.name || '??').split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-4 space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-purple-400 flex items-center justify-center text-white text-sm font-bold">
            {initials}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-white">{customer.name || 'Unknown'}</h4>
              {customer.is_verified && (
                <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium">
                  Verified
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-500">ID: {customer.id.slice(0, 8)}...</p>
          </div>
        </div>
      </div>

      {/* Contact Info */}
      <div className="space-y-1.5">
        {customer.email && (
          <div className="flex items-center gap-2 text-xs">
            {CHANNEL_ICONS.email}
            <span className="text-zinc-400">{customer.email}</span>
          </div>
        )}
        {customer.phone && (
          <div className="flex items-center gap-2 text-xs">
            {CHANNEL_ICONS.phone}
            <span className="text-zinc-400">{customer.phone}</span>
          </div>
        )}
      </div>

      {/* Linked Channels */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h5 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Linked Channels</h5>
          <button
            onClick={onLinkChannelClick}
            className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
          >
            + Add
          </button>
        </div>

        {customer.channels.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {customer.channels.map((channel) => (
              <div
                key={channel.id}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1 rounded-md bg-white/[0.04] border border-white/[0.06]',
                  CHANNEL_COLORS[channel.channel_type] || 'text-zinc-400'
                )}
              >
                {CHANNEL_ICONS[channel.channel_type]}
                <span className="text-xs">{channel.external_id}</span>
                {channel.is_verified && (
                  <svg className="w-3 h-3 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-zinc-600">No channels linked yet</p>
        )}
      </div>

      {/* Potential Duplicates Warning */}
      {duplicates.length > 0 && (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <span className="text-sm font-medium text-amber-400">
              {duplicates.length} Potential Duplicate{duplicates.length > 1 ? 's' : ''} Found
            </span>
          </div>

          <div className="space-y-2">
            {duplicates.slice(0, 2).map((dup, index) => (
              <div
                key={index}
                className="flex items-center justify-between bg-black/20 rounded-md p-2"
              >
                <div className="min-w-0">
                  <p className="text-xs text-zinc-300 truncate">
                    {dup.customer_2_name || dup.customer_2_email || dup.customer_2_phone}
                  </p>
                  <p className="text-[10px] text-zinc-500">
                    {dup.match_method} - {(dup.confidence * 100).toFixed(0)}% match
                  </p>
                </div>
                <button
                  onClick={() => onMergeClick?.(dup)}
                  className="px-2 py-1 text-xs font-medium text-amber-400 hover:bg-amber-500/20 rounded transition-colors"
                >
                  Merge
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] text-zinc-600 pt-2 border-t border-white/[0.04]">
        <span>Created: {new Date(customer.created_at).toLocaleDateString()}</span>
        <span>Updated: {new Date(customer.updated_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
}
