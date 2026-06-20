'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { connectSSE, SSEMessage } from '@/lib/sse';

export function useSSE(url: string) {
  const [messages, setMessages] = useState<SSEMessage[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const addMessage = useCallback((msg: SSEMessage) => {
    setMessages((prev) => [...prev.slice(-200), msg]);
  }, []);

  useEffect(() => {
    const source = connectSSE(
      url,
      (data) => {
        addMessage(data);
        if (!connected) setConnected(true);
      },
      () => {
        setConnected(false);
      }
    );
    sourceRef.current = source;

    return () => {
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [url, connected, addMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, connected, clearMessages };
}