"use client";

/**
 * JarvisTerminalFeed — Terminal-Style GSD Step Visualization (A-004)
 * ==================================================================
 * Renders Jarvis GSD (Goal-Step-Do) steps in a terminal-like feed,
 * showing the AI's thinking process in real-time:
 *   INIT → INPUT → THINKING → TOOL → OUTPUT
 *
 * Each step type has a distinct icon, color, and formatting.
 * Steps arrive via the `jarvis:terminal` Socket.io event.
 *
 * Phase 20: Real-Time Feature Completion
 */

import React, { useState, useEffect, useCallback, useRef } from "react";
import { socketClient } from "@/lib/socket-client";

// ── Types ─────────────────────────────────────────────────────────────

export type GSDStepType = "INIT" | "INPUT" | "THINKING" | "TOOL" | "OUTPUT" | "ERROR";

export interface GSDStep {
  id: string;
  type: GSDStepType;
  label: string;
  detail?: string;
  timestamp: string;
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

interface JarvisTerminalFeedProps {
  /** Maximum steps to display (default: 50) */
  maxSteps?: number;
  /** Auto-scroll to bottom on new steps */
  autoScroll?: boolean;
  /** Show timestamps */
  showTimestamps?: boolean;
  /** Compact mode (less padding) */
  compact?: boolean;
  /** Additional CSS class */
  className?: string;
}

// ── Step Type Config ──────────────────────────────────────────────────

const STEP_CONFIG: Record<GSDStepType, { icon: string; color: string; label: string }> = {
  INIT: { icon: "⚡", color: "text-blue-400", label: "INIT" },
  INPUT: { icon: "📥", color: "text-cyan-400", label: "INPUT" },
  THINKING: { icon: "🧠", color: "text-yellow-400", label: "THINKING" },
  TOOL: { icon: "🔧", color: "text-purple-400", label: "TOOL" },
  OUTPUT: { icon: "📤", color: "text-green-400", label: "OUTPUT" },
  ERROR: { icon: "❌", color: "text-red-400", label: "ERROR" },
};

// ── Component ─────────────────────────────────────────────────────────

export default function JarvisTerminalFeed({
  maxSteps = 50,
  autoScroll = true,
  showTimestamps = true,
  compact = false,
  className = "",
}: JarvisTerminalFeedProps) {
  const [steps, setSteps] = useState<GSDStep[]>([]);
  const [isLive, setIsLive] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  // ── Socket.io Event Handler ────────────────────────────────────────

  useEffect(() => {
    const handleTerminalStep = (data: GSDStep) => {
      if (!data?.type) return;

      setSteps((prev) => {
        const updated = [...prev, data];
        // Trim to maxSteps
        return updated.length > maxSteps ? updated.slice(-maxSteps) : updated;
      });
    };

    const handleTerminalBatch = (data: { steps: GSDStep[] }) => {
      if (!data?.steps || !Array.isArray(data.steps)) return;
      setSteps((prev) => {
        const updated = [...prev, ...data.steps];
        return updated.length > maxSteps ? updated.slice(-maxSteps) : updated;
      });
    };

    socketClient.on("jarvis:terminal", handleTerminalStep as (...args: unknown[]) => void);
    socketClient.on("jarvis:terminal:batch", handleTerminalBatch as (...args: unknown[]) => void);

    // Check if socket is connected
    const checkConnection = () => {
      setIsLive(socketClient.isConnected());
    };
    checkConnection();
    const interval = setInterval(checkConnection, 5000);

    return () => {
      socketClient.off("jarvis:terminal", handleTerminalStep as (...args: unknown[]) => void);
      socketClient.off("jarvis:terminal:batch", handleTerminalBatch as (...args: unknown[]) => void);
      clearInterval(interval);
    };
  }, [maxSteps]);

  // ── Auto-scroll ────────────────────────────────────────────────────

  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [steps, autoScroll]);

  // ── Clear ──────────────────────────────────────────────────────────

  const handleClear = useCallback(() => {
    setSteps([]);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────

  const px = compact ? "px-2" : "px-4";
  const py = compact ? "py-2" : "py-4";
  const stepPx = compact ? "px-2 py-1" : "px-3 py-2";
  const textSize = compact ? "text-xs" : "text-sm";

  return (
    <div
      className={`bg-gray-950 rounded-lg border border-gray-800 overflow-hidden ${className}`}
      role="log"
      aria-label="Jarvis terminal feed"
      aria-live="polite"
    >
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between bg-gray-900 px-4 py-2 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500" aria-hidden="true" />
            <div className="w-3 h-3 rounded-full bg-yellow-500" aria-hidden="true" />
            <div className="w-3 h-3 rounded-full bg-green-500" aria-hidden="true" />
          </div>
          <span className="text-gray-400 text-xs font-mono ml-2">jarvis-terminal</span>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs font-mono ${isLive ? "text-green-400" : "text-gray-500"}`}
            role="status"
            aria-label={isLive ? "Live connection" : "Disconnected"}
          >
            {isLive ? "● LIVE" : "○ OFFLINE"}
          </span>
          <button
            onClick={handleClear}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Clear terminal"
          >
            Clear
          </button>
        </div>
      </div>

      {/* ── Feed ────────────────────────────────────────────────── */}
      <div
        ref={feedRef}
        className={`${px} ${py} font-mono ${textSize} overflow-y-auto`}
        style={{ maxHeight: compact ? "200px" : "400px" }}
      >
        {steps.length === 0 ? (
          <div className="text-gray-600 text-center py-8">
            <p className="text-gray-500">Waiting for Jarvis steps...</p>
            <p className="text-gray-600 text-xs mt-1">
              Steps will appear here when Jarvis processes requests
            </p>
          </div>
        ) : (
          steps.map((step, index) => {
            const config = STEP_CONFIG[step.type] || STEP_CONFIG.INIT;
            const time = showTimestamps
              ? new Date(step.timestamp).toLocaleTimeString("en-US", {
                  hour12: false,
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })
              : null;

            return (
              <div
                key={step.id || index}
                className={`${stepPx} rounded mb-1 hover:bg-gray-900/50 transition-colors`}
              >
                <div className="flex items-start gap-2">
                  <span aria-hidden="true">{config.icon}</span>
                  <span className={`${config.color} font-bold min-w-[80px]`}>
                    [{config.label}]
                  </span>
                  <span className="text-gray-300 flex-1">{step.label}</span>
                  {time && (
                    <span className="text-gray-600 text-xs ml-2" aria-hidden="true">
                      {time}
                    </span>
                  )}
                  {step.duration_ms !== undefined && (
                    <span className="text-gray-600 text-xs ml-1" aria-hidden="true">
                      ({step.duration_ms}ms)
                    </span>
                  )}
                </div>
                {step.detail && (
                  <div className="ml-6 mt-0.5 text-gray-500 text-xs truncate">
                    {step.detail}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between bg-gray-900 px-4 py-1 border-t border-gray-800">
        <span className="text-gray-600 text-xs font-mono">
          {steps.length} step{steps.length !== 1 ? "s" : ""}
        </span>
        <span className="text-gray-700 text-xs font-mono">
          GSD Pipeline: INIT → INPUT → THINKING → TOOL → OUTPUT
        </span>
      </div>
    </div>
  );
}
