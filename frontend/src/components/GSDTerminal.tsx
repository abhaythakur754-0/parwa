'use client';

import { useSSE } from '@/hooks/useSSE';
import { useJarvisStatus } from '@/hooks/useJarvisStatus';
import { useRef, useEffect } from 'react';

interface TerminalLine {
  text: string;
  type: 'system' | 'init' | 'sense' | 'evaluate' | 'act' | 'notify' | 'complete' | 'error' | 'info';
  timestamp: string;
}

function classifyLine(data: any): TerminalLine {
  const raw = typeof data === 'string' ? data : JSON.stringify(data);
  const ts = data?.timestamp || new Date().toISOString();

  const lower = raw.toLowerCase();
  let type: TerminalLine['type'] = 'info';
  let text = raw;

  if (lower.includes('"type":"init"') || lower.includes('"phase":"init"') || lower.includes('init')) {
    type = 'init'; text = `[INIT] ${extractMessage(data) || 'System initialization...'}`;
  } else if (lower.includes('"type":"sense"') || lower.includes('"phase":"sense"') || lower.includes('sense') || lower.includes('analyzing')) {
    type = 'sense'; text = `[SENSE] ${extractMessage(data) || 'Analyzing input signals...'}`;
  } else if (lower.includes('"type":"evaluate"') || lower.includes('"phase":"evaluate"') || lower.includes('evaluate') || lower.includes('processing')) {
    type = 'evaluate'; text = `[EVALUATE] ${extractMessage(data) || 'Processing evaluation signals...'}`;
  } else if (lower.includes('"type":"act"') || lower.includes('"phase":"act"') || lower.includes('executing') || lower.includes('action')) {
    type = 'act'; text = `[ACT] ${extractMessage(data) || 'Executing action...'}`;
  } else if (lower.includes('"type":"notify"') || lower.includes('"phase":"notify"') || lower.includes('notify') || lower.includes('delivering')) {
    type = 'notify'; text = `[NOTIFY] ${extractMessage(data) || 'Delivering response...'}`;
  } else if (lower.includes('complete') || lower.includes('done') || lower.includes('finished')) {
    type = 'complete'; text = `[COMPLETE] ${extractMessage(data) || 'Operation complete.'}`;
  } else if (lower.includes('error') || lower.includes('fail') || lower.includes('critical')) {
    type = 'error'; text = `[ERROR] ${extractMessage(data) || 'An error occurred.'}`;
  } else {
    text = `> ${raw}`;
  }

  return { text, type, timestamp: ts };
}

function extractMessage(data: any): string {
  if (typeof data === 'string') return data;
  return data?.message || data?.description || data?.detail || data?.text || '';
}

function lineColor(type: TerminalLine['type']): string {
  switch (type) {
    case 'init': return 'text-jarvis-cyan';
    case 'sense': return 'text-jarvis-yellow';
    case 'evaluate': return 'text-purple-400';
    case 'act': return 'text-jarvis-green';
    case 'notify': return 'text-blue-400';
    case 'complete': return 'text-jarvis-green font-bold';
    case 'error': return 'text-jarvis-red';
    case 'system': return 'text-jarvis-cyan glow-cyan';
    default: return 'text-jarvis-muted';
  }
}

export default function GSDTerminal() {
  const { messages, connected, clearMessages } = useSSE('/api/jarvis/stream');
  const { data: status } = useJarvisStatus();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const lines: TerminalLine[] = [
    { text: 'JARVIS - OPERATING SYSTEM', type: 'system', timestamp: '' },
    { text: `SYSTEM STATUS: ${(status?.system_status || 'OPTIMAL').toUpperCase()}`, type: 'system', timestamp: '' },
    { text: `MODE: ${(status?.mode || 'SHADOW').toUpperCase()}`, type: 'system', timestamp: '' },
    { text: '─'.repeat(45), type: 'system', timestamp: '' },
    ...messages.map((msg) => classifyLine(msg)),
  ];

  return (
    <div className="jarvis-card flex flex-col h-80">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">GSD Terminal</h3>
          <span className={`inline-flex w-2 h-2 rounded-full ${
            connected ? 'bg-jarvis-green animate-pulse' : 'bg-jarvis-red'
          }`} />
          <span className="text-[10px] text-jarvis-muted">
            {connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>
        <button
          onClick={clearMessages}
          className="text-[10px] text-jarvis-muted hover:text-jarvis-text transition-colors"
        >
          CLEAR
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-black rounded-lg p-3 border border-jarvis-border/50 font-mono text-xs leading-relaxed"
      >
        {lines.map((line, idx) => (
          <div key={idx} className={`${lineColor(line.type)} fade-in`}>
            <span className="text-jarvis-muted/40">
              {line.timestamp ? new Date(line.timestamp).toLocaleTimeString('en', { hour12: false }) : '  '}
            </span>
            <span className="ml-2">{line.text}</span>
          </div>
        ))}
        {connected && messages.length === 0 && (
          <div className="text-jarvis-green/40 mt-2">
            {'>'} [INIT] Awaiting real-time events...
          </div>
        )}
        {!connected && (
          <div className="text-jarvis-red/60 mt-2">
            ⚠ SSE stream disconnected — attempting reconnection...
          </div>
        )}
      </div>
    </div>
  );
}