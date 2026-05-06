"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { CheckCircle, XCircle, Clock, DollarSign, AlertTriangle, RefreshCw, Loader2, ChevronRight, } from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface ApprovalRecord { approval_id: string; ticket_id: string; amount: number; status: string; approval_type: string; created_at: string; expires_at: string; }

const statusColors: Record<string, string> = { pending: "bg-yellow-100 text-yellow-700", approved: "bg-green-100 text-green-700", rejected: "bg-red-100 text-red-700", };
const getAmountColor = (amount: number): string => { if (amount >= 500) return "text-red-500 font-semibold"; if (amount >= 100) return "text-yellow-500 font-medium"; return "text-green-500"; };

export default function ApprovalsPage() {
  const { isAuthenticated, user } = useAuthStore();
  const { addToast } = useUIStore();
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<{ open: boolean; type: "approve" | "reject"; approval: ApprovalRecord | null; }>({ open: false, type: "approve", approval: null });
  const [rejectReason, setRejectReason] = useState("");

  const fetchApprovals = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try { const response = await apiClient.get<{ approvals: ApprovalRecord[] }>("/approvals/pending"); setApprovals(response.data.approvals || []); }
    catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load", variant: "error" }); }
    finally { setLoading(false); }
  }, [isAuthenticated, addToast]);

  useEffect(() => { fetchApprovals(); }, [fetchApprovals]);

  const handleApprove = async (approval: ApprovalRecord) => {
    if (!user) return;
    setActionLoading(approval.approval_id);
    try {
      const response = await apiClient.post<{ success: boolean; error?: string; }>(`/approvals/${approval.approval_id}/approve`, { approver_id: user.id });
      if (response.data.success) { addToast({ title: "Approved", description: `Refund of $${approval.amount.toFixed(2)} approved`, variant: "success" }); setApprovals((prev) => prev.filter((a) => a.approval_id !== approval.approval_id)); }
      else throw new Error(response.data.error || "Approval failed");
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to approve", variant: "error" }); }
    finally { setActionLoading(null); setConfirmDialog({ open: false, type: "approve", approval: null }); }
  };

  const handleReject = async (approval: ApprovalRecord, reason: string) => {
    if (!user) return;
    setActionLoading(approval.approval_id);
    try {
      const response = await apiClient.post<{ success: boolean; }>(`/approvals/${approval.approval_id}/reject`, { reason, rejected_by: user.id });
      if (response.data.success) { addToast({ title: "Rejected", description: "Request rejected", variant: "success" }); setApprovals((prev) => prev.filter((a) => a.approval_id !== approval.approval_id)); }
    } catch (err) { addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to reject", variant: "error" }); }
    finally { setActionLoading(null); setConfirmDialog({ open: false, type: "reject", approval: null }); setRejectReason(""); }
  };

  const getTimeRemaining = (expiresAt: string): string => { const diffMs = new Date(expiresAt).getTime() - Date.now(); if (diffMs <= 0) return "Expired"; const hours = Math.floor(diffMs / 3600000); return hours > 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h remaining` : `${hours}h remaining`; };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Approvals Queue</h1><p className="text-muted-foreground">Review and approve pending refund requests</p></div><Button onClick={fetchApprovals} variant="outline" disabled={loading}><RefreshCw className={cn("mr-2 h-4 w-4", loading && "animate-spin")} />Refresh</Button></div>
      <Card className="border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20"><CardContent className="flex items-center gap-4 p-4"><AlertTriangle className="h-5 w-5 text-yellow-500" /><div><p className="font-medium text-yellow-700">Important: Payment Processing</p><p className="text-sm text-yellow-600">Approving a refund will process through Paddle immediately.</p></div></CardContent></Card>
      {loading ? <div className="flex h-[40vh] items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-muted-foreground" /></div>
      : approvals.length === 0 ? <Card><CardContent className="flex flex-col items-center gap-4 py-12"><CheckCircle className="h-12 w-12 text-green-500" /><p className="text-lg font-medium">All Caught Up!</p><p className="text-muted-foreground">No pending approvals</p></CardContent></Card>
      : <div className="space-y-4">{approvals.map((approval) => (
          <Card key={approval.approval_id} className="hover:border-primary/50 transition-colors"><CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10"><DollarSign className="h-6 w-6 text-primary" /></div>
              <div className="flex-1">
                <div className="flex items-center gap-2"><span className={cn("text-lg font-bold", getAmountColor(approval.amount))}>${approval.amount.toFixed(2)}</span><Badge variant="outline" className="capitalize">{approval.approval_type}</Badge><Badge className={cn("capitalize", statusColors[approval.status])}>{approval.status}</Badge></div>
                <p className="text-sm text-muted-foreground">Ticket: {approval.ticket_id.slice(0, 8)}...</p>
                <p className="text-xs text-muted-foreground"><Clock className="h-3 w-3 inline mr-1" />{getTimeRemaining(approval.expires_at)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Link href={`/dashboard/approvals/${approval.approval_id}`}><Button variant="ghost" size="icon"><ChevronRight className="h-4 w-4" /></Button></Link>
                <Button variant="outline" size="sm" className="text-green-600 hover:bg-green-50" onClick={() => setConfirmDialog({ open: true, type: "approve", approval })} disabled={actionLoading === approval.approval_id}>{actionLoading === approval.approval_id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-1 h-4 w-4" />}Approve</Button>
                <Button variant="outline" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => setConfirmDialog({ open: true, type: "reject", approval })} disabled={actionLoading === approval.approval_id}><XCircle className="mr-1 h-4 w-4" />Deny</Button>
              </div>
            </div>
          </CardContent></Card>
        ))}</div>}
      <Dialog open={confirmDialog.open && confirmDialog.type === "reject"} onOpenChange={(open) => setConfirmDialog({ open, type: "reject", approval: null })}>
        <DialogContent><DialogHeader><DialogTitle>Reject Refund Request</DialogTitle><DialogDescription>Please provide a reason for rejecting this request.</DialogDescription></DialogHeader>
        {confirmDialog.approval && <p className="text-lg font-bold">${confirmDialog.approval.amount.toFixed(2)}</p>}
        <Input placeholder="Enter rejection reason..." value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
        <DialogFooter><Button variant="outline" onClick={() => setConfirmDialog({ open: false, type: "reject", approval: null })}>Cancel</Button><Button variant="destructive" onClick={() => confirmDialog.approval && rejectReason && handleReject(confirmDialog.approval, rejectReason)} disabled={!rejectReason.trim()}>Reject Request</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
