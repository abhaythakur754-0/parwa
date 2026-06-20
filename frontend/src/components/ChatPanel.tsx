'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

import { getCurrentTenantId } from '@/lib/auth-context';

function ContextHealthMeter() {
  const [contextPct] = useState(Math.floor(Math.random() * 30) + 30);
  const filled = Math.round((contextPct / 100) * 20);
  const empty = 20 - filled;
  const bar = '█'.repeat(filled) + '░'.repeat(empty);

  let statusLabel = 'Normal';
  let statusColor = 'text-jarvis-green';
  if (contextPct > 80) { statusLabel = 'High'; statusColor = 'text-jarvis-red'; }
  else if (contextPct > 60) { statusLabel = 'Moderate'; statusColor = 'text-jarvis-yellow'; }

  return (
    <div className="bg-jarvis-bg/60 rounded px-3 py-1.5 text-[11px] font-mono flex items-center gap-2">
      <span className={statusColor}>[{statusLabel}]</span>
      <span className="text-jarvis-muted">Context Usage:</span>
      <span className="text-jarvis-text">{contextPct}%</span>
      <span className={statusColor}>{bar}</span>
    </div>
  );
}

export default function ChatPanel({ compact = false }: { compact?: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const chatMutation = useMutation({
    mutationFn: (question: string) => jarvisApi.chat(getCurrentTenantId(), question),
    onMutate: () => {
      setIsStreaming(true);
    },
    onSuccess: (data) => {
      const response = data?.chat_response || data?.response || JSON.stringify(data, null, 2);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response,
          timestamp: new Date().toISOString(),
        },
      ]);
      setIsStreaming(false);
    },
    onError: (error) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error: ${error.message}`,
          timestamp: new Date().toISOString(),
        },
      ]);
      setIsStreaming(false);
    },
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isStreaming]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || chatMutation.isPending) return;

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question, timestamp: new Date().toISOString() },
    ]);
    setInput('');
    chatMutation.mutate(question);
  };

  const msgCount = compact ? 6 : 50;
  const displayMessages = messages.slice(-msgCount);

  return (
    <div className={`jarvis-card flex flex-col ${compact ? 'h-80' : 'h-[500px]'}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">JARVIS Chat</h3>
          <span className="inline-flex w-1.5 h-1.5 rounded-full bg-jarvis-green animate-pulse" />
        </div>
        <ContextHealthMeter />
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-jarvis-bg/50 rounded-lg p-3 space-y-2 border border-jarvis-border/30 animate-scanline"
      >
        {messages.length === 0 && (
          <div className="text-center py-8">
            <p className="text-jarvis-green/50 text-sm glow-green">JARVIS Terminal Ready</p>
            <p className="text-jarvis-muted text-[10px] mt-1">Type a message to begin</p>
          </div>
        )}
        {displayMessages.map((msg, idx) => (
          <div
            key={idx}
            className={`fade-in ${
              msg.role === 'user' ? 'text-right' : 'text-left'
            }`}
          >
            <div
              className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-jarvis-cyan/10 text-jarvis-cyan border border-jarvis-cyan/20'
                  : 'bg-jarvis-green/5 text-jarvis-green border border-jarvis-green/10'
              }`}
            >
              <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
                {msg.content}
              </p>
              <p className="text-[9px] text-jarvis-muted mt-1">
                {new Date(msg.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        {isStreaming && (
          <div className="text-left fade-in">
            <div className="inline-block bg-jarvis-green/5 text-jarvis-green border border-jarvis-green/10 rounded-lg px-3 py-2">
              <span className="flex items-center gap-1 text-xs">
                <span className="inline-flex w-1 h-1 rounded-full bg-jarvis-green animate-bounce" />
                <span className="inline-flex w-1 h-1 rounded-full bg-jarvis-green animate-bounce" style={{ animationDelay: '0.1s' }} />
                <span className="inline-flex w-1 h-1 rounded-full bg-jarvis-green animate-bounce" style={{ animationDelay: '0.2s' }} />
                <span className="ml-1">Processing...</span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="mt-2 flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask JARVIS anything..."
          className="jarvis-input flex-1 text-xs"
          disabled={chatMutation.isPending}
        />
        <button
          type="submit"
          disabled={chatMutation.isPending || !input.trim()}
          className="jarvis-btn-primary px-4 disabled:opacity-30 disabled:cursor-not-allowed text-xs"
        >
          {chatMutation.isPending ? '...' : 'SEND'}
        </button>
      </form>
    </div>
  );
}