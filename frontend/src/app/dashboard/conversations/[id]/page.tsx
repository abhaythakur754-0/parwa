'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { dashboardApi, type TicketMessage } from '@/lib/dashboard-api';

export default function ConversationDetailPage() {
  const params = useParams();
  const ticketId = params.id as string;
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [ticket, setTicket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true); setError(null);
      try {
        const [msgsData, tixData] = await Promise.all([
          dashboardApi.getConversationMessages(ticketId, { pageSize: 100 }),
          dashboardApi.getConversationMessages(ticketId, { pageSize: 1 }).catch(() => null),
        ]);
        setMessages(msgsData.messages || []);
        if (msgsData.messages && msgsData.messages.length > 0) {
          setTicket({
            id: ticketId,
            channel: msgsData.messages[0]?.channel,
          });
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load conversation');
      } finally { setLoading(false); }
    };
    load();
  }, [ticketId]);

  if (loading) return <div className="min-h-screen bg-[#0a0a0a] p-6"><p className="text-zinc-500">Loading conversation...</p></div>;
  if (error) return <div className="min-h-screen bg-[#0a0a0a] p-6"><p className="text-red-400">{error}</p></div>;

  return (
    <div className="min-h-screen bg-[#0a0a0a] p-6">
      <Link href="/dashboard/conversations" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-300 mb-6 transition-colors">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" /></svg>
        Back to Conversations
      </Link>

      <div className="flex gap-6">
        {/* Transcript */}
        <div className="flex-1">
          <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-lg font-semibold text-zinc-100">Conversation #{ticketId.slice(0, 8)}</h1>
                {ticket?.channel && <span className="text-xs text-zinc-500 capitalize mt-1">{ticket.channel} channel</span>}
              </div>
              <div className="flex gap-2">
                <button className="px-3 py-1.5 text-xs bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors">Escalate</button>
                <button className="px-3 py-1.5 text-xs bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors">Reassign</button>
                <button className="px-3 py-1.5 text-xs bg-orange-500/10 text-orange-400 rounded-lg hover:bg-orange-500/20 transition-colors">Export</button>
              </div>
            </div>

            {messages.length === 0 ? (
              <p className="text-center text-zinc-500 py-12">No messages in this conversation</p>
            ) : (
              <div className="space-y-4">
                {messages.map((msg) => {
                  const isCustomer = msg.role === 'customer';
                  const isAi = msg.role === 'ai' || msg.role === 'agent';
                  const isSystem = msg.role === 'system';
                  const isInternal = msg.is_internal;

                  return (
                    <div key={msg.id} className={`flex ${isCustomer ? 'justify-start' : 'justify-end'}`}>
                      <div className={`max-w-[70%] ${isCustomer ? '' : ''}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium text-zinc-500">
                            {isCustomer ? 'Customer' : isAi ? 'PARWA AI' : isSystem ? 'System' : 'Agent'}
                          </span>
                          {msg.ai_confidence !== null && msg.ai_confidence !== undefined && (
                            <span className={`text-xs font-medium ${msg.ai_confidence >= 75 ? 'text-emerald-400' : msg.ai_confidence >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
                              {msg.ai_confidence}%
                            </span>
                          )}
                          {isInternal && <span className="text-xs px-1.5 py-0.5 bg-amber-500/10 text-amber-400 rounded">Internal</span>}
                          <span className="text-xs text-zinc-600">{new Date(msg.created_at).toLocaleTimeString()}</span>
                        </div>
                        <div className={`rounded-2xl px-4 py-3 ${
                          isSystem ? 'bg-zinc-800/50 text-zinc-500 text-center text-xs italic' :
                          isInternal ? 'bg-amber-500/5 border border-amber-500/10 text-zinc-300' :
                          isCustomer ? 'bg-zinc-800 text-zinc-200' :
                          'bg-gradient-to-br from-orange-500/20 to-orange-600/10 text-zinc-100 border border-orange-500/10'
                        }`}>
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Reply Box */}
            <div className="mt-6 pt-4 border-t border-white/[0.06]">
              <textarea placeholder="Type a reply..." rows={3} className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/50 resize-none" />
              <div className="flex justify-end mt-2">
                <button className="px-4 py-2 text-sm bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors">Send Reply</button>
              </div>
            </div>
          </div>
        </div>

        {/* Metadata Panel */}
        <div className="w-72 shrink-0 space-y-4">
          <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-4">
            <h3 className="text-sm font-semibold text-zinc-200 mb-3">Details</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-zinc-500">Channel</dt><dd className="text-zinc-300 capitalize">{ticket?.channel || '\u2014'}</dd></div>
              <div className="flex justify-between"><dt className="text-zinc-500">Messages</dt><dd className="text-zinc-300">{messages.length}</dd></div>
              <div className="flex justify-between"><dt className="text-zinc-500">Duration</dt><dd className="text-zinc-300">{formatDuration(messages)}</dd></div>
              <div className="flex justify-between"><dt className="text-zinc-500">Customer msgs</dt><dd className="text-zinc-300">{messages.filter(m => m.role === 'customer').length}</dd></div>
              <div className="flex justify-between"><dt className="text-zinc-500">AI msgs</dt><dd className="text-zinc-300">{messages.filter(m => m.role === 'ai' || m.role === 'agent').length}</dd></div>
            </dl>
          </div>

          <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-4">
            <h3 className="text-sm font-semibold text-zinc-200 mb-3">AI Confidence</h3>
            <div className="space-y-2">
              {(() => {
                const aiMsgs = messages.filter(m => m.ai_confidence !== null && m.ai_confidence !== undefined);
                const avg = aiMsgs.length > 0 ? aiMsgs.reduce((s, m) => s + (m.ai_confidence || 0), 0) / aiMsgs.length : 0;
                const color = avg >= 75 ? 'text-emerald-400' : avg >= 50 ? 'text-amber-400' : 'text-red-400';
                const barColor = avg >= 75 ? 'bg-emerald-500' : avg >= 50 ? 'bg-amber-500' : 'bg-red-500';
                return (
                  <>
                    <p className={`text-2xl font-bold ${color}`}>{aiMsgs.length > 0 ? `${avg.toFixed(1)}%` : 'N/A'}</p>
                    <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${avg}%` }} />
                    </div>
                    <p className="text-xs text-zinc-500">Average across {aiMsgs.length} AI responses</p>
                  </>
                );
              })()}
            </div>
          </div>

          <div className="bg-zinc-900/50 rounded-xl border border-white/[0.06] p-4">
            <h3 className="text-sm font-semibold text-zinc-200 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <button className="w-full px-3 py-2 text-sm text-left bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors">Add Internal Note</button>
              <button className="w-full px-3 py-2 text-sm text-left bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors">Escalate to Human</button>
              <button className="w-full px-3 py-2 text-sm text-left bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors">Export as PDF</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatDuration(messages: TicketMessage[]): string {
  if (messages.length < 2) return '\u2014';
  const first = new Date(messages[0].created_at).getTime();
  const last = new Date(messages[messages.length - 1].created_at).getTime();
  const diffSec = Math.round((last - first) / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  if (diffSec < 3600) return `${Math.round(diffSec / 60)}m`;
  return `${Math.round(diffSec / 3600)}h ${Math.round((diffSec % 3600) / 60)}m`;
}
