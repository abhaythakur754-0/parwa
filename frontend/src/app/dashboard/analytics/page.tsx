"use client";

import { useEffect, useState, useCallback } from "react";
import { BarChart3, TrendingUp, Clock, Users, Download, FileText, Calendar, RefreshCw, Loader2, } from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell, } from "recharts";

interface CompanyStats { total_tickets: number; open_tickets: number; resolved_tickets: number; avg_response_time: number; sla_compliance_rate: number; }
interface TicketMetricItem { date: string | null; tickets_created: number; tickets_resolved: number; avg_resolution_time: number; }
interface AgentPerformanceItem { agent_id: string; agent_name: string; tickets_assigned: number; tickets_resolved: number; avg_resolution_time: number; customer_satisfaction: number; }
interface SLACompliance { compliance_rate: number; total_tickets: number; breached_tickets: number; }

const PIE_COLORS = ["#22c55e", "#ef4444"];
const TIME_RANGES = [{ value: "7d", label: "Last 7 Days" }, { value: "30d", label: "Last 30 Days" }, { value: "90d", label: "Last 90 Days" }];

export default function AnalyticsPage() {
  const { isAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("7d");
  const [stats, setStats] = useState<CompanyStats | null>(null);
  const [ticketMetrics, setTicketMetrics] = useState<TicketMetricItem[]>([]);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformanceItem[]>([]);
  const [slaCompliance, setSlaCompliance] = useState<SLACompliance | null>(null);

  const getDateRange = useCallback(() => {
    const now = new Date();
    const days = timeRange === "30d" ? 30 : timeRange === "90d" ? 90 : 7;
    return { startDate: new Date(now.getTime() - days * 24 * 60 * 60 * 1000), endDate: now };
  }, [timeRange]);

  const fetchAnalytics = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    const { startDate, endDate } = getDateRange();
    try {
      const [statsRes, metricsRes, performanceRes, slaRes] = await Promise.all([
        apiClient.get<CompanyStats>("/analytics/stats", { start_date: startDate.toISOString(), end_date: endDate.toISOString() }),
        apiClient.get<{ metrics: TicketMetricItem[] }>("/analytics/metrics/tickets", { start_date: startDate.toISOString(), end_date: endDate.toISOString(), group_by: "day" }),
        apiClient.get<{ agents: AgentPerformanceItem[] }>("/analytics/metrics/agent-performance", { start_date: startDate.toISOString(), end_date: endDate.toISOString() }),
        apiClient.get<SLACompliance>("/analytics/sla-compliance", { start_date: startDate.toISOString(), end_date: endDate.toISOString() }),
      ]);
      setStats(statsRes.data); setTicketMetrics(metricsRes.data.metrics || []); setAgentPerformance(performanceRes.data.agents || []); setSlaCompliance(slaRes.data);
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load", variant: "error" }); }
    finally { setLoading(false); }
  }, [isAuthenticated, getDateRange, addToast]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const handleExportCSV = () => {
    if (!ticketMetrics.length) return;
    const csv = ["Date,Tickets Created,Tickets Resolved"].concat(ticketMetrics.map((m) => `${m.date || ""},${m.tickets_created},${m.tickets_resolved}`)).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `parwa-analytics-${timeRange}.csv`; a.click();
  };

  const formatChartDate = (date: string | null) => { if (!date) return ""; return new Date(date).toLocaleDateString("en-US", { month: "short", day: "numeric" }); };
  const slaPieData = slaCompliance ? [{ name: "Compliant", value: slaCompliance.total_tickets - slaCompliance.breached_tickets }, { name: "Breached", value: slaCompliance.breached_tickets }] : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Analytics</h1><p className="text-muted-foreground">Track performance metrics and insights</p></div>
        <div className="flex items-center gap-2">
          <Select value={timeRange} onValueChange={setTimeRange}><SelectTrigger className="w-[150px]"><Calendar className="mr-2 h-4 w-4" /><SelectValue /></SelectTrigger><SelectContent>{TIME_RANGES.map((r) => (<SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>))}</SelectContent></Select>
          <Button variant="outline" onClick={fetchAnalytics} disabled={loading}><RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />Refresh</Button>
          <Button variant="outline" onClick={handleExportCSV} disabled={loading}><Download className="mr-2 h-4 w-4" />Export CSV</Button>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        <Card><CardContent className="flex items-center gap-4 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600"><FileText className="h-5 w-5" /></div><div><p className="text-2xl font-bold">{stats?.total_tickets ?? 0}</p><p className="text-sm text-muted-foreground">Total Tickets</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 text-yellow-600"><TrendingUp className="h-5 w-5" /></div><div><p className="text-2xl font-bold">{stats?.open_tickets ?? 0}</p><p className="text-sm text-muted-foreground">Open Tickets</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600"><Clock className="h-5 w-5" /></div><div><p className="text-2xl font-bold">{stats ? `${stats.avg_response_time.toFixed(1)}h` : "N/A"}</p><p className="text-sm text-muted-foreground">Avg Response</p></div></CardContent></Card>
        <Card><CardContent className="flex items-center gap-4 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600"><BarChart3 className="h-5 w-5" /></div><div><p className="text-2xl font-bold">{stats ? `${stats.sla_compliance_rate.toFixed(1)}%` : "N/A"}</p><p className="text-sm text-muted-foreground">SLA Compliance</p></div></CardContent></Card>
      </div>
      {loading ? <div className="flex h-[40vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div> : <>
        <Card><CardHeader><CardTitle>Ticket Volume</CardTitle></CardHeader><CardContent><div className="h-[300px]"><ResponsiveContainer width="100%" height="100%"><LineChart data={ticketMetrics}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={formatChartDate} /><YAxis /><Tooltip /><Legend /><Line type="monotone" dataKey="tickets_created" name="Created" stroke="#3b82f6" dot={false} /><Line type="monotone" dataKey="tickets_resolved" name="Resolved" stroke="#22c55e" dot={false} /></LineChart></ResponsiveContainer></div></CardContent></Card>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card><CardHeader><CardTitle>Resolution Time (hours)</CardTitle></CardHeader><CardContent><div className="h-[250px]"><ResponsiveContainer width="100%" height="100%"><BarChart data={ticketMetrics}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tickFormatter={formatChartDate} /><YAxis /><Tooltip /><Bar dataKey="avg_resolution_time" fill="#8b5cf6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></CardContent></Card>
          <Card><CardHeader><CardTitle>SLA Compliance</CardTitle></CardHeader><CardContent><div className="h-[250px]">{slaCompliance && <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={slaPieData} cx="50%" cy="50%" innerRadius={60} outerRadius={80} dataKey="value">{slaPieData.map((_, i) => (<Cell key={i} fill={PIE_COLORS[i]} />))}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer>}</div>{slaCompliance && <div className="mt-4 grid grid-cols-2 gap-4 text-center"><div><p className="text-2xl font-bold text-green-500">{slaCompliance.compliance_rate.toFixed(1)}%</p><p className="text-sm text-muted-foreground">Compliance Rate</p></div><div><p className="text-2xl font-bold text-red-500">{slaCompliance.breached_tickets}</p><p className="text-sm text-muted-foreground">Breached</p></div></div>}</CardContent></Card>
        </div>
        <Card><CardHeader><CardTitle className="flex items-center gap-2"><Users className="h-5 w-5" />Agent Performance</CardTitle></CardHeader><CardContent>
          {agentPerformance.length === 0 ? <p className="py-8 text-center text-muted-foreground">No data available</p> : <table className="w-full"><thead><tr className="border-b"><th className="p-2 text-left text-sm font-medium">Agent</th><th className="p-2 text-right text-sm font-medium">Assigned</th><th className="p-2 text-right text-sm font-medium">Resolved</th><th className="p-2 text-right text-sm font-medium">Avg Time</th><th className="p-2 text-right text-sm font-medium">CSAT</th></tr></thead>
            <tbody>{agentPerformance.map((agent) => (<tr key={agent.agent_id} className="border-b"><td className="p-2 text-sm">{agent.agent_name}</td><td className="p-2 text-right text-sm">{agent.tickets_assigned}</td><td className="p-2 text-right text-sm">{agent.tickets_resolved}</td><td className="p-2 text-right text-sm">{agent.avg_resolution_time.toFixed(1)}h</td><td className="p-2 text-right text-sm font-medium">{(agent.customer_satisfaction * 100).toFixed(0)}%</td></tr>))}</tbody></table>}
        </CardContent></Card>
      </>}
    </div>
  );
}
