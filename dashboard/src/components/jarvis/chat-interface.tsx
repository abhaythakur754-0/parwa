'use client';

import { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppStore } from '@/lib/store';
import { fetchChatMessages, sendChatMessage } from '@/lib/api';
import type { ChatMessage, VariantType } from '@/lib/types';
import { Bot, Send, Plus, Brain, Sparkles, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { motion } from 'framer-motion';

export function ChatInterface() {
  const { chatVariant, setChatVariant, chatSessionId, startNewChat } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sessionId = chatSessionId || 'cs_001';
    fetchChatMessages(sessionId).then(d => { setMessages(d); setLoading(false); });
  }, [chatSessionId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || sending) return;

    const userMsg: ChatMessage = {
      id: `cm_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);

    // Simulate streaming
    const aiMsg: ChatMessage = {
      id: `cm_${Date.now()}_ai`,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      variant: chatVariant,
      isStreaming: true,
    };
    setMessages(prev => [...prev, aiMsg]);

    const response = await sendChatMessage(input, chatVariant);
    setMessages(prev => prev.map(m => m.id === aiMsg.id ? { ...response, isStreaming: false } : m));
    setSending(false);
  };

  const variantColors: Record<VariantType, string> = {
    mini_parwa: 'text-emerald-600 dark:text-emerald-400',
    parwa: 'text-amber-600 dark:text-amber-400',
    parwa_high: 'text-red-600 dark:text-red-400',
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)]">
      {/* Chat Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Select value={chatVariant} onValueChange={v => setChatVariant(v as VariantType)}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="mini_parwa">Starter (mini_parwa)</SelectItem>
              <SelectItem value="parwa">Growth (parwa)</SelectItem>
              <SelectItem value="parwa_high">High (parwa_high)</SelectItem>
            </SelectContent>
          </Select>
          <Badge variant="outline" className={`border-0 text-xs ${variantColors[chatVariant]}`}>
            {chatVariant === 'mini_parwa' ? 'Tier 1' : chatVariant === 'parwa' ? 'Tier 1+2' : 'Tier 1+2+3'}
          </Badge>
        </div>
        <Button variant="outline" size="sm" onClick={startNewChat}>
          <Plus className="h-3 w-3 mr-1" /> New Chat
        </Button>
      </div>

      {/* Chat Messages */}
      <Card className="flex-1 flex flex-col min-h-0">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-12 w-3/4" />
              <Skeleton className="h-12 w-1/2 ml-auto" />
              <Skeleton className="h-12 w-2/3" />
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map(msg => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <Avatar className="h-8 w-8 flex-shrink-0">
                    <AvatarFallback className={msg.role === 'assistant' ? 'bg-emerald-600 text-white text-xs' : 'bg-gray-200 dark:bg-gray-700 text-xs'}>
                      {msg.role === 'assistant' ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
                    </AvatarFallback>
                  </Avatar>
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'text-right' : ''}`}>
                    <div className={`inline-block rounded-xl px-4 py-2.5 text-sm ${
                      msg.role === 'user'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-muted'
                    }`}>
                      {msg.role === 'assistant' ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                          {msg.isStreaming && <span className="animate-pulse">▊</span>}
                        </div>
                      ) : (
                        msg.content
                      )}
                    </div>
                    {msg.role === 'assistant' && (msg.technique || msg.confidence) && (
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                        {msg.technique && (
                          <span className="flex items-center gap-1"><Brain className="h-2.5 w-2.5" /> {msg.technique}</span>
                        )}
                        {msg.confidence && (
                          <span className="flex items-center gap-1"><Sparkles className="h-2.5 w-2.5" /> {(msg.confidence * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    )}
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Input */}
        <div className="border-t border-border p-4">
          <form
            onSubmit={e => { e.preventDefault(); handleSend(); }}
            className="flex gap-2"
          >
            <Input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Type your message..."
              disabled={sending}
              className="flex-1"
            />
            <Button type="submit" disabled={sending || !input.trim()} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
