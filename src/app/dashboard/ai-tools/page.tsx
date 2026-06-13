/**
 * AI Tools Dashboard Page (/dashboard/ai-tools) — Phase 14
 *
 * Displays available AI tools, a tool selection panel,
 * and the generated system prompt.
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { get, post } from '@/lib/api';
import { toast } from 'sonner';
import {
  Loader2,
  Wrench,
  Crosshair,
  FileText,
  Sparkles,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';
import { MetricCard } from '@/components/jarvis-cc/MetricCard';

// ── Types ───────────────────────────────────────────────────────────

interface AITool {
  id: string;
  name: string;
  description: string;
  category?: string;
  enabled?: boolean;
}

interface ToolSelectionResult {
  selected_tools: AITool[];
  reason?: string;
}

interface PromptResult {
  system_prompt: string;
  tools_used?: string[];
}

// ── AI Tools Page ───────────────────────────────────────────────────

export default function AIToolsPage() {
  const [availableTools, setAvailableTools] = useState<AITool[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(true);

  // Tool selection state
  const [ticketIntent, setTicketIntent] = useState('');
  const [selectionResult, setSelectionResult] = useState<ToolSelectionResult | null>(null);
  const [isSelecting, setIsSelecting] = useState(false);

  // System prompt state
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);
  const [isLoadingPrompt, setIsLoadingPrompt] = useState(false);

  // ── Fetch available tools ──────────────────────────────────────────
  const fetchAvailableTools = useCallback(async () => {
    setIsLoadingTools(true);
    try {
      const result = await get<AITool[]>('/api/ai-tools/available');
      setAvailableTools(Array.isArray(result) ? result : []);
    } catch {
      // Endpoint unavailable — show empty state
      setAvailableTools([]);
    } finally {
      setIsLoadingTools(false);
    }
  }, []);

  // ── Fetch system prompt ────────────────────────────────────────────
  const fetchSystemPrompt = useCallback(async () => {
    setIsLoadingPrompt(true);
    try {
      const result = await get<PromptResult>('/api/ai-tools/prompt');
      setSystemPrompt(result.system_prompt || JSON.stringify(result, null, 2));
    } catch {
      setSystemPrompt(null);
    } finally {
      setIsLoadingPrompt(false);
    }
  }, []);

  useEffect(() => {
    fetchAvailableTools();
    fetchSystemPrompt();
  }, [fetchAvailableTools, fetchSystemPrompt]);

  // ── Tool selection handler ─────────────────────────────────────────
  const handleSelectTools = async () => {
    if (!ticketIntent.trim()) {
      toast.error('Please enter a ticket intent');
      return;
    }

    setIsSelecting(true);
    setSelectionResult(null);
    try {
      const result = await post<ToolSelectionResult>('/api/ai-tools/select', {
        ticket_intent: ticketIntent,
      });
      setSelectionResult(result);
      toast.success(`Selected ${result.selected_tools?.length || 0} tools`);
    } catch {
      toast.error('Failed to select tools');
    } finally {
      setIsSelecting(false);
    }
  };

  // Group tools by category
  const toolsByCategory = availableTools.reduce((acc, tool) => {
    const category = tool.category || 'General';
    if (!acc[category]) acc[category] = [];
    acc[category].push(tool);
    return acc;
  }, {} as Record<string, AITool[]>);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
        <div>
          <h1 className="text-xl font-bold text-white">AI Tools</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Manage and configure AI tools for ticket handling
          </p>
        </div>
        <button
          onClick={() => { fetchAvailableTools(); fetchSystemPrompt(); }}
          disabled={isLoadingTools}
          className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors disabled:opacity-50"
        >
          {isLoadingTools ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="Available Tools"
          value={availableTools.length}
          variant="default"
        />
        <MetricCard
          label="Enabled Tools"
          value={availableTools.filter(t => t.enabled !== false).length}
          variant="success"
        />
        <MetricCard
          label="Categories"
          value={Object.keys(toolsByCategory).length}
          variant="info"
        />
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          Available Tools Section
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Wrench className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Available Tools</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Phase 14</span>
        </div>
        <div className="p-4">
          {isLoadingTools ? (
            <div className="flex items-center gap-2 py-8 justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
              <span className="text-sm text-zinc-500">Loading tools...</span>
            </div>
          ) : availableTools.length === 0 ? (
            <div className="text-center py-10">
              <Wrench className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-sm text-zinc-500 mb-1">No AI tools available</p>
              <p className="text-xs text-zinc-600">Tools will appear here when the AI Tools service is configured</p>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(toolsByCategory).map(([category, tools]) => (
                <div key={category}>
                  <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">{category}</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {tools.map((tool) => (
                      <div
                        key={tool.id}
                        className={cn(
                          'px-3 py-2.5 rounded-lg border transition-all',
                          tool.enabled !== false
                            ? 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
                            : 'bg-white/[0.01] border-white/[0.03] opacity-50'
                        )}
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Sparkles className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
                          <span className="text-sm font-medium text-white truncate">{tool.name}</span>
                          {tool.enabled !== false && (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 flex-shrink-0 ml-auto" />
                          )}
                        </div>
                        <p className="text-[11px] text-zinc-500 line-clamp-2">{tool.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          Tool Selection Panel
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Select Tool</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Test</span>
        </div>
        <div className="p-4">
          <p className="text-xs text-zinc-500 mb-4">
            Enter a ticket intent to see which AI tools the system would select for handling it.
          </p>
          <div className="mb-4">
            <label className="text-xs text-zinc-500 mb-1.5 block">Ticket Intent</label>
            <input
              type="text"
              value={ticketIntent}
              onChange={(e) => setTicketIntent(e.target.value)}
              placeholder="e.g., Process a customer refund for a damaged product"
              className="w-full bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/30"
            />
          </div>
          <button
            onClick={handleSelectTools}
            disabled={isSelecting || !ticketIntent.trim()}
            className="inline-flex items-center gap-2 text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 transition-all disabled:opacity-50 shadow-sm"
          >
            {isSelecting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Crosshair className="w-3.5 h-3.5" />
            )}
            Select Tools
          </button>

          {/* Selection result */}
          {selectionResult && (
            <div className="mt-4 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <ArrowRight className="w-4 h-4 text-emerald-400" />
                <span className="text-sm text-white font-medium">
                  Selected {selectionResult.selected_tools?.length || 0} Tool{(selectionResult.selected_tools?.length || 0) !== 1 ? 's' : ''}
                </span>
              </div>
              {selectionResult.reason && (
                <p className="text-xs text-zinc-400 mb-3">{selectionResult.reason}</p>
              )}
              {selectionResult.selected_tools && selectionResult.selected_tools.length > 0 ? (
                <div className="space-y-2">
                  {selectionResult.selected_tools.map((tool, idx) => (
                    <div
                      key={tool.id || idx}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-orange-400 flex-shrink-0" />
                      <span className="text-sm text-white font-medium">{tool.name}</span>
                      {tool.description && (
                        <span className="text-[11px] text-zinc-500 truncate ml-auto">{tool.description}</span>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500">No tools matched this intent</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          System Prompt Section
         ══════════════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <FileText className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">System Prompt</h3>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 uppercase tracking-wider">Phase 14</span>
        </div>
        <div className="p-4">
          <p className="text-xs text-zinc-500 mb-4">
            The generated system prompt that guides the AI assistant based on the selected tools.
          </p>
          {isLoadingPrompt ? (
            <div className="flex items-center gap-2 py-8 justify-center">
              <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
              <span className="text-xs text-zinc-500">Loading prompt...</span>
            </div>
          ) : systemPrompt ? (
            <div className="relative">
              <pre className="p-4 rounded-lg bg-white/[0.02] border border-white/[0.04] text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed max-h-80 overflow-y-auto">
                {systemPrompt}
              </pre>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(systemPrompt);
                  toast.success('Prompt copied to clipboard');
                }}
                className="absolute top-2 right-2 text-[10px] px-2 py-1 rounded bg-white/[0.06] text-zinc-400 hover:text-white hover:bg-white/[0.12] transition-colors"
              >
                Copy
              </button>
            </div>
          ) : (
            <div className="text-center py-8">
              <FileText className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No system prompt available</p>
              <p className="text-xs text-zinc-600 mt-1">The prompt will appear once the AI Tools service is configured</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
