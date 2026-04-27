'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { dashboardApi, type Customer, type CustomerChannel, type TicketResponse } from '@/lib/dashboard-api';

export default function CustomerDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [channels, setChannels] = useState<CustomerChannel[]>([]);
  const [tickets, setTickets] = useState<TicketResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'tickets' | 'channels' | 'notes'>('tickets');

  useEffect(() => {
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const [cust, chs, tix] = await Promise.all([
          dashboardApi.getCustomer(id),
          dashboardApi.getCustomerChannels(id).catch(() => []),
          dashboardApi.getCustomerTickets(id).catch(() => ({ items: [], total: 0, page: 1, page_size: 25, pages: 0 })),
        ]);
        setCustomer(cust);
        setChannels(Array.isArray(chs) ? chs : []);
        setTickets(tix.items || []);
      } catch (err: any) {
        setError(err.message || 'Failed to load customer');
      } finally { setLoading(false); }
    };
    load();
  }, [id]);

  if (loading) return <div className="min-h-screen bg-[#0a0a0a] p-6"><p className="text-zinc-500">Loading...</p></div>;
  if (error || !customer) return <div className="min-h-screen bg-[#0a0a0a] p-6"><p className="text-red-400">{error || 'Customer not found'}</p></div>;

  const channelIcon = (type: string) => {
    const icons: Record<string, string> = { email: 'E', chat: 'C', sms: 'S', voice: 'V', phone: 'P', slack: 'Sl', webchat: 'W' };
    return icons[type.toLowerCase()] || type.charAt(0).toUpperCase();
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6">
      <Link href="/dashboard/customers" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-300 mb-6 transition-colors">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" /></svg>
        Back to Customers
      </Link>

      {/* Profile Header */}
      <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-6 mb-6">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-white text-xl font-semibold shrink-0">
            {(customer.name || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-zinc-100">{customer.name || 'Unnamed Customer'}</h1>
            <div className="flex flex-wrap gap-x-6 gap-y-1 mt-2 text-sm text-zinc-400">
              {customer.email && <span>{customer.email}</span>}
              {customer.phone && <span>{customer.phone}</span>}
              {customer.external_id && <span className="text-zinc-600">ID: {customer.external_id}</span>}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${customer.is_verified ? 'bg-emerald-500/10 text-emerald-400' : 'bg-zinc-800 text-zinc-400'}`}>
                {customer.is_verified ? 'Verified' : 'Unverified'}
              </span>
              <span className="text-xs text-zinc-600">Created {new Date(customer.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-white/[0.06]">
        {(['tickets', 'channels', 'notes'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === tab ? 'text-orange-400 border-orange-500' : 'text-zinc-500 border-transparent hover:text-zinc-300'}`}>
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'tickets' && <span className="ml-2 text-xs bg-zinc-800 px-1.5 py-0.5 rounded">{tickets.length}</span>}
            {tab === 'channels' && <span className="ml-2 text-xs bg-zinc-800 px-1.5 py-0.5 rounded">{channels.length}</span>}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'tickets' && (
        <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] overflow-hidden overflow-x-auto">
          {tickets.length === 0 ? <p className="p-8 text-center text-zinc-500">No tickets from this customer</p> : (
            <table className="w-full">
              <thead><tr className="border-b border-white/[0.06]">
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Ticket</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Subject</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Priority</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Channel</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Date</th>
              </tr></thead>
              <tbody className="divide-y divide-white/[0.04]">
                {tickets.map((t) => (
                  <tr key={t.id} className="hover:bg-white/[0.02]">
                    <td className="px-4 py-3"><Link href={`/dashboard/tickets/${t.id}`} className="text-sm text-orange-400 hover:underline">#{t.id.slice(0, 8)}</Link></td>
                    <td className="px-4 py-3 text-sm text-zinc-300">{t.subject || t.classification_intent || '\u2014'}</td>
                    <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 capitalize">{(t.status || '').replace(/_/g, ' ')}</span></td>
                    <td className="px-4 py-3"><span className={`text-xs px-2 py-0.5 rounded-full ${t.priority === 'critical' ? 'bg-red-500/10 text-red-400' : t.priority === 'high' ? 'bg-amber-500/10 text-amber-400' : 'bg-zinc-800 text-zinc-400'} capitalize`}>{t.priority || '\u2014'}</span></td>
                    <td className="px-4 py-3 text-sm text-zinc-400 capitalize">{t.channel || '\u2014'}</td>
                    <td className="px-4 py-3 text-sm text-zinc-500">{t.created_at ? new Date(t.created_at).toLocaleDateString() : '\u2014'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === 'channels' && (
        <div className="space-y-3">
          {channels.length === 0 ? <p className="text-zinc-500">No linked channels</p> : channels.map(ch => (
            <div key={ch.id} className="flex items-center gap-4 bg-zinc-900/50 rounded-xl border border-white/[0.06] p-4">
              <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center text-sm font-bold text-zinc-400">{channelIcon(ch.channel_type)}</div>
              <div className="flex-1">
                <p className="text-sm font-medium text-zinc-200 capitalize">{ch.channel_type}</p>
                <p className="text-xs text-zinc-500">{ch.external_id}</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${ch.is_verified ? 'bg-emerald-500/10 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`}>
                {ch.is_verified ? 'Verified' : 'Not Verified'}
              </span>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'notes' && (
        <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-6">
          {/* TODO: Implement customer notes — needs backend endpoint for storing/retrieving notes */}
          <textarea placeholder="Add internal note about this customer..." rows={3} className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 resize-none" />
          <div className="flex justify-end mt-3">
            <button disabled className="px-4 py-2 text-sm bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors opacity-50 cursor-not-allowed">Add Note</button>
          </div>
        </div>
      )}
    </div>
  );
}
