'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { fetchTicketById } from '@/lib/api';
import type { Ticket } from '@/lib/types';
import { useAppStore } from '@/lib/store';
import { Skeleton } from '@/components/ui/skeleton';
import { X, User, Bot, ArrowRight, Clock, Brain, Tag } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const statusColors: Record<string, string> = {
  open: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  in_progress: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  resolved: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
  closed: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-500',
  escalated: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

export function TicketDetail() {
  const { selectedTicketId, setSelectedTicketId } = useAppStore();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedTicketId) {
      let cancelled = false;
      fetchTicketById(selectedTicketId).then(d => {
        if (!cancelled) { setTicket(d || null); setLoading(false); }
      });
      return () => { cancelled = true; };
    }
  }, [selectedTicketId]);

  // Reset ticket when deselected
  const displayTicket = selectedTicketId ? ticket : null;

  if (!selectedTicketId) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
      >
        <Card className="h-full">
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">
              {loading ? <Skeleton className="h-5 w-32" /> : displayTicket?.id}
            </CardTitle>
            <Button variant="ghost" size="icon" onClick={() => setSelectedTicketId(null)}>
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-32 w-full" />
              </div>
            ) : displayTicket ? (
              <div className="space-y-4">
                {/* Header Info */}
                <div>
                  <h3 className="font-semibold">{displayTicket.subject}</h3>
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 border-0 ${statusColors[displayTicket.status]}`}>
                      {displayTicket.status.replace('_', ' ')}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      {displayTicket.variant}
                    </Badge>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 capitalize">
                      {displayTicket.channel}
                    </Badge>
                  </div>
                </div>

                {/* Customer Info */}
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Customer</p>
                  <p className="text-sm font-medium">{displayTicket.customerName}</p>
                  <p className="text-xs text-muted-foreground">{displayTicket.customerEmail}</p>
                </div>

                {/* AI Analysis */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">AI Analysis</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 rounded bg-emerald-50 dark:bg-emerald-950/20 text-center">
                      <p className="text-[10px] text-muted-foreground">Quality</p>
                      <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">{displayTicket.qualityScore}%</p>
                    </div>
                    <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/20 text-center">
                      <p className="text-[10px] text-muted-foreground">Confidence</p>
                      <p className="text-sm font-bold text-amber-600 dark:text-amber-400">{(displayTicket.confidenceScore * 100).toFixed(0)}%</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <Brain className="h-3 w-3 text-muted-foreground" />
                    <span className="text-muted-foreground">Technique:</span>
                    <span className="font-medium">{displayTicket.techniqueUsed}</span>
                  </div>
                  {displayTicket.resolutionTime && (
                    <div className="flex items-center gap-2 text-xs">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                      <span className="text-muted-foreground">Resolution:</span>
                      <span className="font-medium">{displayTicket.resolutionTime}s</span>
                    </div>
                  )}
                </div>

                <Separator />

                {/* Tags */}
                {displayTicket.tags.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <Tag className="h-3 w-3 text-muted-foreground" />
                    {displayTicket.tags.map(tag => (
                      <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                    ))}
                  </div>
                )}

                {/* Conversation */}
                {displayTicket.messages.length > 0 && (
                  <div className="space-y-3 max-h-64 overflow-y-auto">
                    <p className="text-xs font-medium text-muted-foreground">Conversation</p>
                    {displayTicket.messages.map(msg => (
                      <div key={msg.id} className={`flex gap-2 ${msg.sender === 'customer' ? '' : ''}`}>
                        <div className={`flex-shrink-0 h-6 w-6 rounded-full flex items-center justify-center ${
                          msg.sender === 'customer' ? 'bg-gray-200 dark:bg-gray-700' : 'bg-emerald-100 dark:bg-emerald-900/30'
                        }`}>
                          {msg.sender === 'customer' ? (
                            <User className="h-3 w-3" />
                          ) : (
                            <Bot className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium capitalize">{msg.sender === 'ai' ? 'AI' : msg.sender}</span>
                            <span className="text-[10px] text-muted-foreground">
                              {new Date(msg.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-xs mt-0.5 whitespace-pre-wrap">{msg.content}</p>
                          {msg.metadata && (
                            <div className="flex gap-2 mt-1 text-[9px] text-muted-foreground">
                              {msg.metadata.technique && <span>🔧 {msg.metadata.technique}</span>}
                              {msg.metadata.confidence && <span>📊 {(msg.metadata.confidence * 100).toFixed(0)}%</span>}
                              {msg.metadata.latency && <span>⏱ {msg.metadata.latency}s</span>}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {displayTicket.escalationReason && (
                  <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/20 text-xs text-red-700 dark:text-red-400">
                    <span className="font-medium">Escalation Reason:</span> {displayTicket.escalationReason}
                  </div>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
}
