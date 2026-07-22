/**
 * PARWA ConnectionStatus
 *
 * Small indicator showing the Socket.io connection state.
 * Green dot when connected, yellow when reconnecting, red when disconnected.
 * Auto-hides when connected for more than 5 seconds.
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useSocketContext } from '@/providers/SocketProvider';

export function ConnectionStatus() {
  const { isConnected, isReconnecting, connectionState } = useSocketContext();
  const [showWhenConnected, setShowWhenConnected] = useState(true);

  // Auto-hide the indicator when connected for a few seconds.
  // Also auto-hide when disconnected after 10 seconds — the red
  // "Disconnected" badge alarms users unnecessarily. Socket.io
  // will reconnect automatically when the backend is available.
  useEffect(() => {
    if (isConnected) {
      const timer = setTimeout(() => setShowWhenConnected(false), 5000);
      return () => clearTimeout(timer);
    } else {
      setShowWhenConnected(true);
      // Auto-hide "Disconnected" after 10 seconds — it's not critical
      const timer = setTimeout(() => setShowWhenConnected(false), 10000);
      return () => clearTimeout(timer);
    }
  }, [isConnected, connectionState]);

  // Don't show when auto-hidden
  if (!showWhenConnected) return null;

  const stateConfig = {
    connected: {
      color: 'bg-emerald-400',
      text: 'Connected',
      textColor: 'text-emerald-400',
    },
    connecting: {
      color: 'bg-amber-400 animate-pulse',
      text: isReconnecting ? 'Reconnecting...' : 'Connecting...',
      textColor: 'text-amber-400',
    },
    disconnected: {
      color: 'bg-red-400',
      text: 'Disconnected',
      textColor: 'text-red-400',
    },
    error: {
      color: 'bg-red-400 animate-pulse',
      text: 'Connection Error',
      textColor: 'text-red-400',
    },
  };

  const config = stateConfig[connectionState] || stateConfig.disconnected;

  return (
    <div className="flex items-center gap-1.5" title={config.text}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.color}`} />
      <span className={`text-[10px] ${config.textColor}`}>{config.text}</span>
    </div>
  );
}

export default ConnectionStatus;
