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
  channel_type: 'email' | 'phone' | 'twitter' | 'messenger' | 'whatsapp' | 'telegram' | 'instagram' | 'chat';
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
  twitter: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),
  messenger: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 0C5.373 0 0 4.974 0 11.111c0 3.498 1.744 6.614 4.469 8.654V24l4.088-2.242c1.092.301 2.246.464 3.443.464 6.627 0 12-4.975 12-11.111S18.627 0 12 0zm1.191 14.963l-3.055-3.26-5.963 3.26L10.732 8l3.131 3.259L19.752 8l-6.561 6.963z" />
    </svg>
  ),
  whatsapp: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  ),
  telegram: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  ),
  instagram: (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
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
  twitter: 'text-sky-400',
  messenger: 'text-blue-500',
  whatsapp: 'text-green-500',
  telegram: 'text-sky-500',
  instagram: 'text-pink-400',
  chat: 'text-violet-400',
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
