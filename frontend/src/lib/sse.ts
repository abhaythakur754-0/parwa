export interface SSEMessage {
  type?: string;
  data?: any;
  timestamp?: string;
  [key: string]: any;
}

export function connectSSE(
  url: string,
  onMessage: (data: SSEMessage) => void,
  onError?: (err: Event) => void
): EventSource {
  const fullUrl = url.startsWith('http') ? url : `http://localhost:8100${url}`;
  const source = new EventSource(fullUrl);

  source.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      onMessage(parsed);
    } catch {
      onMessage({ data: event.data, timestamp: new Date().toISOString() });
    }
  };

  source.onerror = (err) => {
    if (onError) {
      onError(err);
    } else {
      console.error('[SSE] Connection error — will auto-reconnect');
    }
  };

  return source;
}