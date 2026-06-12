"use client";

import { useState, useEffect } from "react";
import {
  Bot,
  Search,
  Loader2,
  Wrench,
  FileQuestion,
  BookOpen,
  Plug,
  Sparkles,
  ArrowRight,
  CheckCircle2,
} from "lucide-react";

interface Tool {
  id: string;
  name: string;
  type: string;
  description: string;
  integration_id?: string;
  auth_type?: string;
}

interface ToolSelection {
  tool_id: string;
  tool_name: string;
  priority: number;
  reason: string;
}

const toolTypeIcons: Record<string, typeof Bot> = {
  faq: FileQuestion,
  kb: BookOpen,
  rag: Sparkles,
  external_integration: Plug,
};

const toolTypeLabels: Record<string, string> = {
  faq: "FAQ Search",
  kb: "Knowledge Base",
  rag: "RAG Response",
  external_integration: "External Integration",
};

const priorityOrder = ["faq", "kb", "rag", "external_integration"];

export function AiToolSelector() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [testIntent, setTestIntent] = useState("");
  const [selectedTools, setSelectedTools] = useState<ToolSelection[] | null>(null);
  const [testing, setTesting] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState<string | null>(null);

  useEffect(() => {
    loadTools();
    loadPrompt();
  }, []);

  const loadTools = async () => {
    try {
      const res = await fetch("/api/ai-tools/available");
      if (res.ok) {
        const data = await res.json();
        setTools(data.tools || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const loadPrompt = async () => {
    try {
      const res = await fetch("/api/ai-tools/prompt");
      if (res.ok) {
        const data = await res.json();
        setSystemPrompt(data.system_prompt || null);
      }
    } catch {
      // Error handled silently
    }
  };

  const handleTestIntent = async () => {
    if (!testIntent.trim()) return;
    setTesting(true);
    setSelectedTools(null);
    try {
      const res = await fetch("/api/ai-tools/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket_intent: testIntent }),
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedTools(data.selected_tools || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Available Tools */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Wrench className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Available AI Tools</h3>
        </div>
        <div className="p-4">
          {tools.length === 0 ? (
            <div className="text-center py-8">
              <Bot className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No tools available yet</p>
              <p className="text-xs text-zinc-600">
                Connect integrations and upload knowledge base documents to enable tools.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {tools
                .sort((a, b) => {
                  const aIdx = priorityOrder.indexOf(a.type);
                  const bIdx = priorityOrder.indexOf(b.type);
                  return aIdx - bIdx;
                })
                .map((tool) => {
                  const Icon = toolTypeIcons[tool.type] || Bot;
                  return (
                    <div key={tool.id} className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                      <div className="h-8 w-8 rounded-lg bg-orange-500/10 flex items-center justify-center flex-shrink-0">
                        <Icon className="h-4 w-4 text-orange-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{tool.name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500 uppercase tracking-wider">
                            {toolTypeLabels[tool.type] || tool.type}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-500 truncate">{tool.description}</p>
                      </div>
                      <span className="text-xs text-zinc-500">Priority {priorityOrder.indexOf(tool.type) + 1}</span>
                    </div>
                  );
                })}
            </div>
          )}

          {/* Tool Selection Priority */}
          <div className="mt-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <p className="text-xs font-medium text-zinc-400 mb-2">Tool Selection Priority:</p>
            <div className="flex items-center gap-1 text-xs">
              <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px]">FAQ</span>
              <ArrowRight className="h-3 w-3 text-zinc-600" />
              <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px]">KB</span>
              <ArrowRight className="h-3 w-3 text-zinc-600" />
              <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px]">RAG</span>
              <ArrowRight className="h-3 w-3 text-zinc-600" />
              <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 text-[10px]">External</span>
            </div>
          </div>
        </div>
      </div>

      {/* Test Intent */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Search className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Test Tool Selection</h3>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <input
              placeholder="Enter a ticket intent (e.g. 'Where is my order?')"
              value={testIntent}
              onChange={(e) => setTestIntent(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTestIntent()}
              className="flex-1 bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2.5 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/30"
            />
            <button
              onClick={handleTestIntent}
              disabled={testing || !testIntent.trim()}
              className="inline-flex items-center gap-2 text-xs px-4 py-2 rounded-lg bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 transition-all disabled:opacity-50 shadow-sm"
            >
              {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </button>
          </div>

          {selectedTools && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-white">Selected tools for &quot;{testIntent}&quot;:</p>
              {selectedTools.length === 0 ? (
                <p className="text-xs text-zinc-500">No tools selected for this intent.</p>
              ) : (
                selectedTools.map((st) => (
                  <div key={st.tool_id} className="flex items-center gap-3 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400">Priority {st.priority}</span>
                    <span className="text-sm font-medium text-white">{st.tool_name}</span>
                    <span className="text-xs text-zinc-500 ml-auto">{st.reason}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* System Prompt Preview */}
      {systemPrompt && (
        <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
          <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
            <Bot className="w-4 h-4 text-orange-400" />
            <h3 className="text-sm font-semibold text-white">Dynamic System Prompt</h3>
          </div>
          <div className="p-4">
            <pre className="text-xs bg-white/[0.02] border border-white/[0.04] p-3 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap font-mono text-zinc-300">
              {systemPrompt}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
