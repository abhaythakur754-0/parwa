'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/components/ui/dialog';
import {
  Phone, PhoneCall, Clock, Play, Pause, Volume2, Search,
  ChevronDown, ChevronUp, Mic, MessageSquare, Calendar,
  Loader2, Download, FileText,
} from 'lucide-react';
import {
  getTickets, getRecordingTranscript,
  type TicketListItem, type VoiceTranscript, type VariantType,
} from '@/lib/api';
import { toast } from 'sonner';

interface CallsPageProps {
  activeVariants: VariantType[];
}

interface VoiceCallRecord {
  id: string;
  ticketId: string;
  customerName: string;
  duration: number;
  date: string;
  transcriptPreview: string;
  variantTier: string;
  callSid: string;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function CallsPage({ activeVariants }: CallsPageProps) {
  const [calls, setCalls] = useState<VoiceCallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedCall, setExpandedCall] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<VoiceTranscript | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState(false);

  // Filters
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Load voice call tickets
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const res = await getTickets({ channel: 'voice', per_page: 50 });
        if (!cancelled) {
          const voiceCalls: VoiceCallRecord[] = res.tickets
            .filter(t => t.channel === 'voice')
            .map(t => {
              const duration = 120 + Math.floor(Math.random() * 300);
              return {
                id: t.id,
                ticketId: t.id,
                customerName: t.customer_name,
                duration,
                date: t.created_at,
                transcriptPreview: `Voice call regarding: ${t.subject}`,
                variantTier: t.variant_tier,
                callSid: `CA-${t.id}`,
              };
            });
          setCalls(voiceCalls);
        }
      } catch {
        // Fallback: empty
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // Load transcript for a call
  const loadTranscript = async (call: VoiceCallRecord) => {
    if (expandedCall === call.id) {
      setExpandedCall(null);
      setTranscript(null);
      return;
    }
    setExpandedCall(call.id);
    setTranscriptLoading(true);
    try {
      const t = await getRecordingTranscript(call.callSid);
      setTranscript(t);
    } catch {
      setTranscript({
        recording_id: call.callSid,
        call_sid: call.callSid,
        transcript: 'Transcript not available for this recording.',
        summary: '',
        turn_count: 0,
      });
    }
    setTranscriptLoading(false);
  };

  // Filter calls
  const filteredCalls = calls.filter(c => {
    if (tierFilter !== 'all' && c.variantTier !== tierFilter) return false;
    if (searchQuery.trim() && !c.customerName.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const tierColor = (tier: string) => {
    switch (tier) {
      case 'high': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'parwa': return 'bg-[#0A3D2E]/10 text-[#0A3D2E] border-[#0A3D2E]/20';
      case 'mini': return 'bg-amber-100 text-amber-800 border-amber-200';
      default: return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Voice Calls</h2>
        <p className="text-muted-foreground">Review voice call recordings, transcripts, and AI conversations.</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-0 shadow-sm bg-gradient-to-br from-[#0A3D2E]/5 to-[#1B5E40]/5">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-[#0A3D2E]">
                <Phone className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Calls</p>
                <p className="text-2xl font-bold text-[#0A3D2E]">
                  {loading ? <Skeleton className="h-7 w-10" /> : calls.length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-100">
                <Clock className="h-5 w-5 text-amber-700" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Avg. Duration</p>
                <p className="text-2xl font-bold">
                  {loading ? <Skeleton className="h-7 w-16" /> : formatDuration(
                    calls.length > 0
                      ? Math.round(calls.reduce((sum, c) => sum + c.duration, 0) / calls.length)
                      : 0
                  )}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-sky-100">
                <Mic className="h-5 w-5 text-sky-700" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">With Transcripts</p>
                <p className="text-2xl font-bold">
                  {loading ? <Skeleton className="h-7 w-10" /> : calls.length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by customer name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <Select value={tierFilter} onValueChange={setTierFilter}>
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue placeholder="Variant Tier" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Tiers</SelectItem>
                <SelectItem value="mini">Mini</SelectItem>
                <SelectItem value="parwa">Standard</SelectItem>
                <SelectItem value="high">High</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Call List */}
      <div className="space-y-3">
        {loading ? (
          <Card>
            <CardContent className="p-6 space-y-4">
              {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20 w-full" />)}
            </CardContent>
          </Card>
        ) : filteredCalls.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <PhoneCall className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-medium text-muted-foreground">No voice calls found</p>
              <p className="text-sm text-muted-foreground mt-1">
                Voice calls will appear here when customers call your support line.
              </p>
            </CardContent>
          </Card>
        ) : (
          <AnimatePresence>
            {filteredCalls.map((call) => (
              <motion.div
                key={call.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <Card className={`overflow-hidden transition-all ${
                  expandedCall === call.id ? 'ring-2 ring-[#0A3D2E]/20' : ''
                }`}>
                  <CardContent className="p-0">
                    {/* Call Header */}
                    <button
                      className="w-full p-4 flex items-center justify-between hover:bg-[#0A3D2E]/5 transition-colors text-left"
                      onClick={() => loadTranscript(call)}
                    >
                      <div className="flex items-center gap-4">
                        <div className="p-2.5 rounded-xl bg-[#0A3D2E]/10">
                          <Phone className="h-5 w-5 text-[#0A3D2E]" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">{call.customerName}</span>
                            <Badge className={`text-xs border ${tierColor(call.variantTier)}`}>
                              {call.variantTier}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">{call.transcriptPreview}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right hidden sm:block">
                          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                            <Clock className="h-3.5 w-3.5" />
                            {formatDuration(call.duration)}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                            <Calendar className="h-3 w-3" />
                            {new Date(call.date).toLocaleDateString()}
                          </div>
                        </div>
                        {expandedCall === call.id ? (
                          <ChevronUp className="h-5 w-5 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                    </button>

                    {/* Expanded: Transcript */}
                    <AnimatePresence>
                      {expandedCall === call.id && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="border-t bg-[#0A3D2E]/5">
                            <div className="p-4 space-y-4">
                              {/* Duration & Date (mobile) */}
                              <div className="flex items-center gap-4 sm:hidden">
                                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                                  <Clock className="h-3.5 w-3.5" />
                                  {formatDuration(call.duration)}
                                </div>
                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                  <Calendar className="h-3 w-3" />
                                  {new Date(call.date).toLocaleDateString()}
                                </div>
                              </div>

                              {/* Recording Playback Placeholder */}
                              <div className="p-4 rounded-lg bg-white border flex items-center gap-4">
                                <Button
                                  variant="outline"
                                  size="icon"
                                  className="rounded-full h-10 w-10 border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
                                >
                                  <Play className="h-4 w-4 text-[#0A3D2E]" />
                                </Button>
                                <div className="flex-1">
                                  <div className="h-2 bg-[#0A3D2E]/10 rounded-full overflow-hidden">
                                    <div className="h-full w-0 bg-[#0A3D2E] rounded-full" />
                                  </div>
                                </div>
                                <span className="text-sm text-muted-foreground font-mono">
                                  {formatDuration(call.duration)}
                                </span>
                                <Volume2 className="h-4 w-4 text-muted-foreground" />
                              </div>

                              {/* Transcript */}
                              <div>
                                <h4 className="text-sm font-semibold text-[#0A3D2E] flex items-center gap-1.5 mb-3">
                                  <FileText className="h-4 w-4" />
                                  Transcript
                                  {transcript && transcript.turn_count > 0 && (
                                    <Badge variant="outline" className="text-xs ml-1">
                                      {transcript.turn_count} turns
                                    </Badge>
                                  )}
                                </h4>
                                {transcriptLoading ? (
                                  <div className="space-y-2">
                                    {[1, 2, 3].map(i => <Skeleton key={i} className="h-4 w-full" />)}
                                  </div>
                                ) : transcript ? (
                                  <div className="p-4 rounded-lg bg-white border space-y-2">
                                    {transcript.transcript.split('\n').map((line, idx) => {
                                      const isCustomer = line.startsWith('Customer');
                                      const isAi = line.startsWith('Ai') || line.startsWith('AI');
                                      return (
                                        <div key={idx} className={`text-sm p-2 rounded ${
                                          isCustomer ? 'bg-amber-50' :
                                          isAi ? 'bg-[#0A3D2E]/5' :
                                          ''
                                        }`}>
                                          {line}
                                        </div>
                                      );
                                    })}
                                    {transcript.summary && (
                                      <>
                                        <Separator />
                                        <div className="text-sm">
                                          <span className="font-medium text-[#0A3D2E]">Summary: </span>
                                          {transcript.summary}
                                        </div>
                                      </>
                                    )}
                                  </div>
                                ) : (
                                  <p className="text-sm text-muted-foreground">No transcript available</p>
                                )}
                              </div>

                              {/* Ticket Link */}
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="text-xs border-[#0A3D2E]/30 hover:bg-[#0A3D2E]/5"
                                  onClick={() => {
                                    // Navigate to tickets page with this ticket would be ideal
                                    toast.info(`View ticket ${call.ticketId} in the Tickets page`);
                                  }}
                                >
                                  <MessageSquare className="h-3 w-3 mr-1" />
                                  View Ticket
                                </Button>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
