'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { dashboardApi, type Conversation } from '@/lib/dashboard-api';

const PAGE_SIZE = 25;
const CHANNEL_TABS = ['all', 'email', 'chat', 'sms', 'voice', 'slack', 'webchat'];

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [channelFilter, setChannelFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await dashboardApi.getConversations({
        page, pageSize: PAGE_SIZE,
        channel: channelFilter !== 'all' ? channelFilter : undefined,
        search: search || undefined,
      });
      setConversations(data.items || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to load conversations');
    } finally { setLoading(false); }
  }, [page, search, channelFilter]);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);
  useEffect(() => { const t = setTimeout(() => setSearch(searchInput), 300); return () => clearTimeout(t); }, [searchInput]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const channelIcon = (ch: string) => {
    const map: Record<string, string> = { email: 'E', chat: 'C', sms: 'S', voice: 'V', slack: 'Sl', webchat: 'W' };
    return map[ch.toLowerCase()] || ch.charAt(0).toUpperCase();
  };

  const channelColor = (ch: string) => {
    const map: Record<string, string> = { email: 'bg-blue-500/10 text-blue-400', chat: 'bg-emerald-500/10 text-emerald-400', sms: 'bg-purple-500/10 text-purple-400', voice: 'bg-amber-500/10 text-amber-400', slack: 'bg-indigo-500/10 text-indigo-400', webchat: 'bg-cyan-500/10 text-cyan-400' };
    return map[ch.toLowerCase()] || 'bg-zinc-800 text-zinc-400';
  };

  const priorityBadge = (p: string | null) => {
    if (!p) return null;
    const colors: Record<string, string> = { critical: 'bg-red-500/10 text-red-400', high: 'bg-amber-500/10 text-amber-400', medium: 'bg-blue-500/10 text-blue-400', low: 'bg-zinc-800 text-zinc-400' };
    return <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${colors[p.toLowerCase()] || 'bg-zinc-800 text-zinc-400'}`}>{p}</span>;
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = { open: 'bg-emerald-500/10 text-emerald-400', assigned: 'bg-blue-500/10 text-blue-400', in_progress: 'bg-amber-500/10 text-amber-400', awaiting_human: 'bg-red-500/10 text-red-400', resolved: 'bg-zinc-800 text-zinc-400', closed: 'bg-zinc-800 text-zinc-500' };
    return <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${colors[s] || 'bg-zinc-800 text-zinc-400'}`}>{s.replace(/_/g, ' ')}</span>;
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Conversations</h1>
          <p className="text-sm text-zinc-500 mt-1">{total} conversations across all channels</p>
        </div>
        {/* TODO: Implement conversation export — needs backend export endpoint */}
        <button disabled className="px-4 py-2 text-sm bg-zinc-800 text-zinc-200 rounded-lg hover:bg-zinc-700 transition-colors opacity-50 cursor-not-allowed">Export</button>
      </div>

      {/* Channel Tabs */}
      <div className="flex gap-1 mb-4 flex-wrap">
        {CHANNEL_TABS.map(ch => (
          <button key={ch} onClick={() => { setChannelFilter(ch); setPage(1); }} className={`px-3 py-1.5 text-xs font-medium rounded-lg capitalize transition-colors ${channelFilter === ch ? 'bg-orange-500 text-white' : 'bg-zinc-900 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'}`}>
            {ch}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" /></svg>
          <input type="text" placeholder="Search conversations..." value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }} className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50" />
        </div>
      </div>

      {/* Table */}
      <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] overflow-hidden overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Ticket</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Subject</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Channel</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Priority</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Category</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">SLA</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase">Age</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {loading ? <tr><td colSpan={8} className="px-4 py-12 text-center text-zinc-500">Loading...</td></tr> : error ? <tr><td colSpan={8} className="px-4 py-12 text-center text-red-400">{error}</td></tr> : conversations.length === 0 ? <tr><td colSpan={8} className="px-4 py-12 text-center text-zinc-500">No conversations found</td></tr> : conversations.map(conv => (
              <tr key={conv.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3"><Link href={`/dashboard/conversations/${conv.id}`} className="text-sm text-orange-400 hover:underline">#{conv.id.slice(0, 8)}</Link></td>
                <td className="px-4 py-3 text-sm text-zinc-200 max-w-[200px] truncate">{conv.subject || conv.classification_intent || '\u2014'}</td>
                <td className="px-4 py-3"><span className={`text-xs px-2 py-1 rounded-full font-medium capitalize ${channelColor(conv.channel)}`}>{channelIcon(conv.channel)} {conv.channel}</span></td>
                <td className="px-4 py-3">{statusBadge(conv.status)}</td>
                <td className="px-4 py-3">{priorityBadge(conv.priority)}</td>
                <td className="px-4 py-3 text-sm text-zinc-400 capitalize">{conv.category ? conv.category.replace(/_/g, ' ') : '\u2014'}</td>
                <td className="px-4 py-3">{conv.sla_breached ? <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400">Breached</span> : <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">OK</span>}</td>
                <td className="px-4 py-3 text-sm text-zinc-500">{conv.time_since_created || (conv.created_at ? new Date(conv.created_at).toLocaleDateString() : '\u2014')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-zinc-500">Showing {(page - 1) * PAGE_SIZE + 1}\u2013{Math.min(page * PAGE_SIZE, total)} of {total}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 disabled:opacity-40">Prev</button>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => Math.max(1, Math.min(page - 2, totalPages - 4)) + i).filter(p => p <= totalPages).map(p => (
              <button key={p} onClick={() => setPage(p)} className={`px-3 py-1.5 text-sm rounded-lg ${p === page ? 'bg-orange-500 text-white' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}>{p}</button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 text-sm bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
