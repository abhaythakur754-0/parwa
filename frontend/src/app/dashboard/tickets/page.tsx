"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Plus, Search, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  ArrowUpDown, MoreHorizontal, Eye, MessageSquare, AlertTriangle, X,
} from "lucide-react";
import { cn } from "@/utils/utils";
import { apiClient } from "@/services/api/client";
import { useAuthStore } from "@/stores/authStore";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type TicketStatus = "open" | "in_progress" | "resolved" | "closed" | "escalated";

interface Ticket {
  id: string; company_id: string; customer_email: string; channel: string;
  status: string; category: string | null; subject: string; body: string;
  created_at: string; updated_at: string;
}

interface TicketListResponse { tickets: Ticket[]; total: number; page: number; page_size: number; }

const statusColors: Record<TicketStatus, string> = {
  open: "bg-yellow-100 text-yellow-700", in_progress: "bg-blue-100 text-blue-700",
  resolved: "bg-green-100 text-green-700", closed: "bg-gray-100 text-gray-700",
  escalated: "bg-red-100 text-red-700",
};

export default function TicketsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { addToast } = useUIStore();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "all");
  const [channelFilter, setChannelFilter] = useState(searchParams.get("channel") || "all");
  const [searchQuery, setSearchQuery] = useState(searchParams.get("search") || "");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);
  const pageSize = 20;
  const totalPages = Math.ceil(total / pageSize);

  const fetchTickets = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const params: Record<string, string> = { page: String(page), page_size: String(pageSize) };
      if (statusFilter !== "all") params.status = statusFilter;
      if (channelFilter !== "all") params.channel = channelFilter;
      const response = await apiClient.get<TicketListResponse>("/support/tickets", params);
      setTickets(response.data.tickets);
      setTotal(response.data.total);
    } catch (err) {
      addToast({ title: "Error", description: err instanceof Error ? err.message : "Failed to load tickets", variant: "error" });
    } finally { setLoading(false); }
  }, [isAuthenticated, page, statusFilter, channelFilter, addToast]);

  useEffect(() => { fetchTickets(); }, [fetchTickets]);

  const formatDate = (dateString: string) => new Date(dateString).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
  const maskEmail = (email: string) => { if (!email?.includes("@")) return email; const [l, d] = email.split("@"); return `${l.slice(0, 3)}***@${d}`; };
  const clearFilters = () => { setStatusFilter("all"); setChannelFilter("all"); setSearchQuery(""); setPage(1); };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold">Tickets</h1><p className="text-muted-foreground">Manage and track customer support tickets</p></div>
        <Link href="/dashboard/tickets?create=true"><Button><Plus className="mr-2 h-4 w-4" />New Ticket</Button></Link>
      </div>
      <Card><CardContent className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search tickets..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9" />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[150px]"><SelectValue placeholder="Status" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
              <SelectItem value="escalated">Escalated</SelectItem>
            </SelectContent>
          </Select>
          <Select value={channelFilter} onValueChange={setChannelFilter}>
            <SelectTrigger className="w-[150px]"><SelectValue placeholder="Channel" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Channels</SelectItem>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="chat">Chat</SelectItem>
              <SelectItem value="voice">Voice</SelectItem>
            </SelectContent>
          </Select>
          {(statusFilter !== "all" || channelFilter !== "all" || searchQuery) && <Button variant="ghost" size="sm" onClick={clearFilters}><X className="mr-2 h-4 w-4" />Clear</Button>}
        </div>
      </CardContent></Card>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow>
            <TableHead>ID</TableHead><TableHead>Subject</TableHead><TableHead>Status</TableHead><TableHead>Channel</TableHead><TableHead>Customer</TableHead><TableHead>Created</TableHead><TableHead></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {loading ? [...Array(10)].map((_, i) => <TableRow key={i}><TableCell colSpan={7}><div className="h-4 w-full animate-pulse rounded bg-muted" /></TableCell></TableRow>)
            : tickets.length === 0 ? <TableRow><TableCell colSpan={7} className="h-32 text-center"><p className="text-muted-foreground">No tickets found</p></TableCell></TableRow>
            : tickets.map((ticket) => (
              <TableRow key={ticket.id} className="cursor-pointer hover:bg-muted/50" onClick={() => router.push(`/dashboard/tickets/${ticket.id}`)}>
                <TableCell className="font-mono text-sm">{ticket.id.slice(0, 8)}...</TableCell>
                <TableCell><div className="max-w-[300px] truncate font-medium">{ticket.subject}</div></TableCell>
                <TableCell><Badge className={cn("capitalize", statusColors[ticket.status as TicketStatus])}>{ticket.status}</Badge></TableCell>
                <TableCell><Badge variant="outline" className="capitalize">{ticket.channel}</Badge></TableCell>
                <TableCell className="text-muted-foreground">{maskEmail(ticket.customer_email)}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{formatDate(ticket.created_at)}</TableCell>
                <TableCell>
                  <DropdownMenu><DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}><Button variant="ghost" size="icon" className="h-8 w-8"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); router.push(`/dashboard/tickets/${ticket.id}`); }}><Eye className="mr-2 h-4 w-4" />View Details</DropdownMenuItem>
                      <DropdownMenuItem onClick={(e) => e.stopPropagation()}><MessageSquare className="mr-2 h-4 w-4" />Reply</DropdownMenuItem>
                      <DropdownMenuItem onClick={(e) => e.stopPropagation()}><AlertTriangle className="mr-2 h-4 w-4" />Escalate</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent></Card>
      {!loading && tickets.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total} tickets</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => setPage(1)} disabled={page === 1}><ChevronsLeft className="h-4 w-4" /></Button>
            <Button variant="outline" size="icon" onClick={() => setPage(page - 1)} disabled={page === 1}><ChevronLeft className="h-4 w-4" /></Button>
            <span className="px-4 text-sm">Page {page} of {totalPages}</span>
            <Button variant="outline" size="icon" onClick={() => setPage(page + 1)} disabled={page === totalPages}><ChevronRight className="h-4 w-4" /></Button>
            <Button variant="outline" size="icon" onClick={() => setPage(totalPages)} disabled={page === totalPages}><ChevronsRight className="h-4 w-4" /></Button>
          </div>
        </div>
      )}
    </div>
  );
}
