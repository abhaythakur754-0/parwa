"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Clock, Mail, MessageSquare, Phone, Smartphone, Send, AlertTriangle, CheckCircle, XCircle, Bot, ThumbsUp, ThumbsDown, Minus, Loader2, } from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface Ticket { id: string; subject: string; body: string; status: string; channel: string; customer_email: string; ai_recommendation: string | null; ai_confidence: number | null; sentiment: string | null; created_at: string; updated_at: string; resolved_at: string | null; }

const statusColors: Record<string, string> = { open: "bg-yellow-100 text-yellow-700", in_progress: "bg-blue-100 text-blue-700", resolved: "bg-green-100 text-green-700", closed: "bg-gray-100 text-gray-700", escalated: "bg-red-100 text-red-700", };
const channelIcons: Record<string, React.ElementType> = { email: Mail, chat: MessageSquare, voice: Phone, sms: Smartphone, };
const sentimentConfig: Record<string, { icon: React.ElementType; color: string }> = { positive: { icon: ThumbsUp, color: "text-green-500" }, negative: { icon: ThumbsDown, color: "text-red-500" }, neutral: { icon: Minus, color: "text-gray-500" }, };

export default function TicketDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyMessage, setReplyMessage] = useState("");

  const fetchTicket = useCallback(async () => {
    if (!isAuthenticated || !resolvedParams.id) return;
    setLoading(true);
    try { const response = await apiClient.get<Ticket>(`/support/tickets/${resolvedParams.id}`); setTicket(response.data); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load ticket", variant: "error" }); }
    finally { setLoading(false); }
  }, [isAuthenticated, resolvedParams.id, addToast]);

  useEffect(() => { fetchTicket(); }, [fetchTicket]);

  const handleAction = async (action: "escalate" | "resolve" | "close") => {
    if (!ticket) return;
    try {
      if (action === "escalate") await apiClient.post(`/support/tickets/${ticket.id}/escalate`);
      else await apiClient.put(`/support/tickets/${ticket.id}`, { status: action === "resolve" ? "resolved" : "closed" });
      addToast({ title: "Success", description: `Ticket ${action}d successfully`, variant: "success" });
      fetchTicket();
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : `Failed to ${action}`, variant: "error" }); }
  };

  const handleReply = async () => {
    if (!ticket || !replyMessage.trim()) return;
    try { await apiClient.post(`/support/tickets/${ticket.id}/messages`, { message: replyMessage, sender: "agent" }); addToast({ title: "Success", description: "Reply sent", variant: "success" }); setReplyMessage(""); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to send", variant: "error" }); }
  };

  if (loading) return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
  if (!ticket) return <div className="space-y-6"><Button variant="ghost" size="icon" onClick={() => router.back()}><ArrowLeft className="h-5 w-5" /></Button><Card><CardContent className="p-8"><p>Ticket not found</p></CardContent></Card></div>;

  const ChannelIcon = channelIcons[ticket.channel] || MessageSquare;
  const sentiment = ticket.sentiment ? sentimentConfig[ticket.sentiment] : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}><ArrowLeft className="h-5 w-5" /></Button>
          <div><div className="flex items-center gap-2"><h1 className="text-xl font-semibold">{ticket.subject}</h1><Badge className={cn("capitalize", statusColors[ticket.status])}>{ticket.status}</Badge></div><p className="text-sm text-muted-foreground">ID: {ticket.id.slice(0, 8)}...</p></div>
        </div>
        <div className="flex gap-2">
          {ticket.status === "open" && <Button variant="outline" onClick={() => handleAction("escalate")}><AlertTriangle className="mr-2 h-4 w-4" />Escalate</Button>}
          {ticket.status !== "resolved" && ticket.status !== "closed" && <Button variant="outline" onClick={() => handleAction("resolve")}><CheckCircle className="mr-2 h-4 w-4" />Resolve</Button>}
          {ticket.status !== "closed" && <Button variant="destructive" onClick={() => handleAction("close")}><XCircle className="mr-2 h-4 w-4" />Close</Button>}
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card><CardHeader><CardTitle className="text-base">Original Message</CardTitle></CardHeader><CardContent><div className="flex items-start gap-4"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted"><ChannelIcon className="h-5 w-5 text-muted-foreground" /></div><p className="whitespace-pre-wrap flex-1">{ticket.body}</p></div></CardContent></Card>
          {ticket.ai_recommendation && <Card className="border-primary/50 bg-primary/5"><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bot className="h-5 w-5 text-primary" />AI Recommendation</CardTitle></CardHeader><CardContent><p className="whitespace-pre-wrap">{ticket.ai_recommendation}</p>{ticket.ai_confidence && <p className="text-sm text-muted-foreground mt-2">Confidence: {(ticket.ai_confidence * 100).toFixed(0)}%</p>}</CardContent></Card>}
          <Card><CardHeader><CardTitle className="text-base">Reply</CardTitle></CardHeader><CardContent><div className="flex items-start gap-4"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary"><MessageSquare className="h-5 w-5" /></div><div className="flex-1 space-y-4"><Input placeholder="Type your reply..." value={replyMessage} onChange={(e) => setReplyMessage(e.target.value)} /><Button onClick={handleReply} disabled={!replyMessage.trim()}><Send className="mr-2 h-4 w-4" />Send Reply</Button></div></div></CardContent></Card>
        </div>
        <div className="space-y-6">
          <Card><CardHeader><CardTitle className="text-base">Customer</CardTitle></CardHeader><CardContent><div className="flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted"><Mail className="h-5 w-5 text-muted-foreground" /></div><div><p className="font-medium">{ticket.customer_email}</p><p className="text-sm text-muted-foreground">Customer</p></div></div></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-base">Details</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="flex justify-between"><span className="text-muted-foreground">Channel</span><span className="capitalize">{ticket.channel}</span></div>
            {sentiment && <div className="flex justify-between"><span className="text-muted-foreground">Sentiment</span><span className={cn("capitalize", sentiment.color)}>{ticket.sentiment}</span></div>}
          </CardContent></Card>
        </div>
      </div>
    </div>
  );
}
