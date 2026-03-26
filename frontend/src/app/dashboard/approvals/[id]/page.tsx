"use client";

import { useEffect, useState, useCallback, use } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, XCircle, Clock, DollarSign, AlertTriangle, Bot, ThumbsUp, ThumbsDown, Minus, Loader2, FileText, User, } from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface ApprovalDetail { approval_id: string; ticket_id: string; amount: number; status: string; approval_type: string; created_at: string; expires_at: string; recommendation?: string; recommendation_reason?: string; }

const recommendationColors: Record<string, string> = { APPROVE: "bg-green-100 text-green-700", REVIEW: "bg-yellow-100 text-yellow-700", DENY: "bg-red-100 text-red-700", };
const statusColors: Record<string, string> = { pending: "bg-yellow-100 text-yellow-700", approved: "bg-green-100 text-green-700", rejected: "bg-red-100 text-red-700", };

export default function ApprovalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const { addToast } = useUIStore();
  const [approval, setApproval] = useState<ApprovalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const fetchApproval = useCallback(async () => {
    if (!isAuthenticated || !resolvedParams.id) return;
    setLoading(true);
    try { const response = await apiClient.get<ApprovalDetail>(`/approvals/${resolvedParams.id}`); setApproval(response.data); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load", variant: "error" }); }
    finally { setLoading(false); }
  }, [isAuthenticated, resolvedParams.id, addToast]);

  useEffect(() => { fetchApproval(); }, [fetchApproval]);

  const handleApprove = async () => {
    if (!approval || !user) return;
    setActionLoading(true);
    try {
      const response = await apiClient.post<{ success: boolean; }>(`/approvals/${approval.approval_id}/approve`, { approver_id: user.id });
      if (response.data.success) { addToast({ title: "Approved", description: "Refund approved", variant: "success" }); fetchApproval(); }
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to approve", variant: "error" }); }
    finally { setActionLoading(false); }
  };

  const handleReject = async () => {
    if (!approval || !user || !rejectReason.trim()) return;
    setActionLoading(true);
    try {
      const response = await apiClient.post<{ success: boolean; }>(`/approvals/${approval.approval_id}/reject`, { reason: rejectReason, rejected_by: user.id });
      if (response.data.success) { addToast({ title: "Rejected", description: "Request rejected", variant: "success" }); fetchApproval(); }
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to reject", variant: "error" }); }
    finally { setActionLoading(false); }
  };

  if (loading) return <div className="flex h-[50vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>;
  if (!approval) return <div className="space-y-6"><Button variant="ghost" size="icon" onClick={() => router.back()}><ArrowLeft className="h-5 w-5" /></Button><Card><CardContent className="p-8"><p>Approval not found</p></CardContent></Card></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}><ArrowLeft className="h-5 w-5" /></Button>
          <div><div className="flex items-center gap-2"><h1 className="text-xl font-semibold">Approval: ${approval.amount.toFixed(2)}</h1><Badge className={cn("capitalize", statusColors[approval.status])}>{approval.status}</Badge></div><p className="text-sm text-muted-foreground">ID: {approval.approval_id.slice(0, 8)}...</p></div>
        </div>
        {approval.status === "pending" && <div className="flex gap-2"><Button className="bg-green-600 hover:bg-green-700" onClick={handleApprove} disabled={actionLoading}>{actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-2 h-4 w-4" />}Approve</Button><Button variant="destructive" onClick={handleReject} disabled={actionLoading || !rejectReason.trim()}>{actionLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <XCircle className="mr-2 h-4 w-4" />}Deny</Button></div>}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {approval.recommendation && (
            <Card className={cn("border-2", approval.recommendation === "APPROVE" && "border-green-500 bg-green-50", approval.recommendation === "REVIEW" && "border-yellow-500 bg-yellow-50", approval.recommendation === "DENY" && "border-red-500 bg-red-50")}>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bot className="h-5 w-5" />AI Recommendation</CardTitle></CardHeader>
              <CardContent><Badge className={cn("text-base capitalize", recommendationColors[approval.recommendation])}>{approval.recommendation}</Badge>{approval.recommendation_reason && <p className="mt-2 text-sm text-muted-foreground">{approval.recommendation_reason}</p>}</CardContent>
            </Card>
          )}
          {approval.status === "pending" && <Card><CardHeader><CardTitle className="text-base">Rejection Reason</CardTitle></CardHeader><CardContent><Input placeholder="Enter reason if denying..." value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} /></CardContent></Card>}
        </div>
        <div className="space-y-6">
          <Card><CardHeader><CardTitle className="text-base">Refund Amount</CardTitle></CardHeader><CardContent><div className="flex items-center gap-4"><div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10"><DollarSign className="h-6 w-6 text-primary" /></div><p className="text-3xl font-bold">${approval.amount.toFixed(2)}</p></div></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-base">Details</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="flex justify-between"><span className="text-muted-foreground">Type</span><span className="capitalize">{approval.approval_type}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Status</span><Badge className={cn("capitalize", statusColors[approval.status])}>{approval.status}</Badge></div>
          </CardContent></Card>
          {approval.status === "pending" && <Card className="border-yellow-500 bg-yellow-50"><CardContent className="flex items-center gap-4 p-4"><Clock className="h-5 w-5 text-yellow-500" /><div><p className="font-medium text-yellow-700">Time Sensitive</p><p className="text-sm text-yellow-600">Expires: {new Date(approval.expires_at).toLocaleString()}</p></div></CardContent></Card>}
        </div>
      </div>
    </div>
  );
}
