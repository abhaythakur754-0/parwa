"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
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
      <Card>
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Available Tools */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Wrench className="h-4 w-4" />
            Available AI Tools
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tools.length === 0 ? (
            <div className="text-center py-6">
              <Bot className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">No tools available yet</p>
              <p className="text-xs text-muted-foreground">
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
                    <div key={tool.id} className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                        <Icon className="h-4 w-4 text-emerald-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{tool.name}</span>
                          <Badge variant="outline" className="text-[10px]">
                            {toolTypeLabels[tool.type] || tool.type}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{tool.description}</p>
                      </div>
                      <span className="text-xs text-muted-foreground">Priority {priorityOrder.indexOf(tool.type) + 1}</span>
                    </div>
                  );
                })}
            </div>
          )}

          {/* Tool Selection Priority */}
          <div className="mt-4 p-3 bg-muted/50 rounded-lg">
            <p className="text-xs font-medium mb-2">Tool Selection Priority:</p>
            <div className="flex items-center gap-1 text-xs">
              <Badge variant="secondary" className="text-[10px]">FAQ</Badge>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <Badge variant="secondary" className="text-[10px]">KB</Badge>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <Badge variant="secondary" className="text-[10px]">RAG</Badge>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <Badge variant="secondary" className="text-[10px]">External</Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Test Intent */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4" />
            Test Tool Selection
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Enter a ticket intent (e.g. 'Where is my order?')"
              value={testIntent}
              onChange={(e) => setTestIntent(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTestIntent()}
            />
            <Button onClick={handleTestIntent} disabled={testing || !testIntent.trim()}>
              {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </Button>
          </div>

          {selectedTools && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Selected tools for &quot;{testIntent}&quot;:</p>
              {selectedTools.length === 0 ? (
                <p className="text-xs text-muted-foreground">No tools selected for this intent.</p>
              ) : (
                selectedTools.map((st) => (
                  <div key={st.tool_id} className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-950/20 rounded-lg">
                    <Badge variant="default" className="text-xs">Priority {st.priority}</Badge>
                    <span className="text-sm font-medium">{st.tool_name}</span>
                    <span className="text-xs text-muted-foreground">{st.reason}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* System Prompt Preview */}
      {systemPrompt && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Bot className="h-4 w-4" />
              Dynamic System Prompt
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-muted/50 p-3 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap">
              {systemPrompt}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
