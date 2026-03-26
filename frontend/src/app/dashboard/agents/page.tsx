"use client";

import { useEffect, useState, useCallback } from "react";
import { Bot, Activity, Clock, Zap, AlertCircle, CheckCircle, PauseCircle, Play, FileText, RefreshCw, Loader2, } from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type AgentStatus = "active" | "idle" | "offline" | "paused";
type AgentVariant = "mini" | "parwa" | "parwa_high";

interface Agent { id: string; name: string; type: string; variant: AgentVariant; status: AgentStatus; current_task?: string; accuracy?: number; avg_response_time?: number; tickets_resolved_today?: number; last_activity?: string; }

const statusColors: Record<AgentStatus, string> = { active: "bg-green-100 text-green-700", idle: "bg-blue-100 text-blue-700", offline: "bg-gray-100 text-gray-700", paused: "bg-yellow-100 text-yellow-700", };
const statusIcons: Record<AgentStatus, React.ElementType> = { active: CheckCircle, idle: Activity, offline: AlertCircle, paused: PauseCircle, };
const variantNames: Record<AgentVariant, string> = { mini: "Mini PARWA", parwa: "PARWA Junior", parwa_high: "PARWA High", };
const variantColors: Record<AgentVariant, string> = { mini: "border-blue-500 bg-blue-50/50", parwa: "border-purple-500 bg-purple-50/50", parwa_high: "border-amber-500 bg-amber-50/50", };

export default function AgentsPage() {
  const { isAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try { const response = await apiClient.get<{ agents: Agent[] }>("/agents"); setAgents(response.data.agents || []); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load", variant: "error" }); }
    finally { setLoading(false); }
  }, [isAuthenticated, addToast]);

  useEffect(() => { fetchAgents(); }, [fetchAgents]);

  const handleToggleAgent = async (agentId: string, currentStatus: AgentStatus) => {
    const action = currentStatus === "paused" ? "resume" : "pause";
    setActionLoading(agentId);
    try { await apiClient.post(`/agents/${agentId}/${action}`); addToast({ title: "Success", description: `Agent ${action}d`, variant: "success" }); fetchAgents(); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : `Failed to ${action}`, variant: "error" }); }
    finally { setActionLoading(null); }
  };

  const agentsByVariant = agents.reduce((acc, agent) => { if (!acc[agent.variant]) acc[agent.variant] = []; acc[agent.variant].push(agent); return acc; }, {} as Record<AgentVariant, Agent[]>);
  const statusCounts = agents.reduce((acc, agent) => { acc[agent.status] = (acc[agent.status] || 0) + 1; return acc; }, {} as Record<AgentStatus, number>);
  const formatTimeAgo = (timestamp?: string) => { if (!timestamp) return "N/A"; const diffMs = Date.now() - new Date(timestamp).getTime(); const diffMins = Math.floor(diffMs / 60000); if (diffMins < 1) return "Just now"; if (diffMins < 60) return `${diffMins}m ago`; return `${Math.floor(diffMins / 60)}h ago`; };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">AI Agents</h1><p className="text-muted-foreground">Monitor and manage your AI workforce</p></div><Button onClick={fetchAgents} variant="outline" disabled={loading}><RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />Refresh</Button></div>
      <div className="grid gap-4 md:grid-cols-4">
        {(["active", "idle", "paused", "offline"] as AgentStatus[]).map((status) => {
          const Icon = statusIcons[status];
          return (<Card key={status}><CardContent className="flex items-center gap-4 p-4"><div className={cn("flex h-10 w-10 items-center justify-center rounded-lg", statusColors[status])}><Icon className="h-5 w-5" /></div><div><p className="text-2xl font-bold">{statusCounts[status] || 0}</p><p className="text-sm text-muted-foreground capitalize">{status}</p></div></CardContent></Card>);
        })}
      </div>
      {loading ? <div className="flex h-[40vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div> :
      <div className="space-y-8">{(["mini", "parwa", "parwa_high"] as AgentVariant[]).map((variant) => {
        const variantAgents = agentsByVariant[variant] || [];
        if (variantAgents.length === 0) return null;
        return (<div key={variant} className="space-y-4"><h2 className="text-lg font-semibold">{variantNames[variant]}</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{variantAgents.map((agent) => {
            const StatusIcon = statusIcons[agent.status];
            return (<Card key={agent.id} className={cn("border-l-4", variantColors[variant])}>
              <CardHeader className="pb-2"><div className="flex items-center justify-between"><CardTitle className="flex items-center gap-2 text-base"><Bot className="h-5 w-5" />{agent.name}</CardTitle><Badge className={cn("capitalize", statusColors[agent.status])}><StatusIcon className="mr-1 h-3 w-3" />{agent.status}</Badge></div></CardHeader>
              <CardContent className="space-y-4">
                {agent.current_task && <div className="rounded-lg bg-muted p-3"><p className="text-xs font-medium text-muted-foreground">Current Task</p><p className="text-sm">{agent.current_task}</p></div>}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div><p className="text-lg font-semibold">{agent.accuracy ? `${(agent.accuracy * 100).toFixed(0)}%` : "N/A"}</p><p className="text-xs text-muted-foreground">Accuracy</p></div>
                  <div><p className="text-lg font-semibold">{agent.avg_response_time ? `${agent.avg_response_time.toFixed(1)}s` : "N/A"}</p><p className="text-xs text-muted-foreground">Avg Time</p></div>
                  <div><p className="text-lg font-semibold">{agent.tickets_resolved_today ?? 0}</p><p className="text-xs text-muted-foreground">Today</p></div>
                </div>
                <div className="flex items-center justify-between border-t pt-4">
                  <p className="text-xs text-muted-foreground"><Clock className="h-3 w-3 inline mr-1" />{formatTimeAgo(agent.last_activity)}</p>
                  <Button variant="outline" size="sm" onClick={() => handleToggleAgent(agent.id, agent.status)} disabled={agent.status === "offline" || actionLoading === agent.id}>{actionLoading === agent.id ? <Loader2 className="h-4 w-4 animate-spin" /> : agent.status === "paused" ? <><Play className="mr-1 h-3 w-3" />Resume</> : <><PauseCircle className="mr-1 h-3 w-3" />Pause</>}</Button>
                </div>
              </CardContent>
            </Card>);
          })}</div>
        </div>);
      })}</div>}
    </div>
  );
}
