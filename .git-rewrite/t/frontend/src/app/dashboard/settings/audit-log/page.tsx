"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  userId: string;
  action: string;
  actionType: "create" | "update" | "delete" | "login" | "approval" | "escalation";
  resource: string;
  resourceId: string;
  details: string;
  ipAddress: string;
}

const ACTION_TYPE_COLORS: Record<string, string> = {
  create: "bg-green-500",
  update: "bg-blue-500",
  delete: "bg-red-500",
  login: "bg-purple-500",
  approval: "bg-yellow-500",
  escalation: "bg-orange-500",
};

const mockAuditLogs: AuditLogEntry[] = [
  {
    id: "1",
    timestamp: "2026-03-22T10:30:00Z",
    user: "john@example.com",
    userId: "u_1",
    action: "Approved refund request",
    actionType: "approval",
    resource: "ticket",
    resourceId: "T-1234",
    details: "Refund of $49.99 approved for ticket T-1234",
    ipAddress: "192.168.1.100",
  },
  {
    id: "2",
    timestamp: "2026-03-22T10:15:00Z",
    user: "jane@example.com",
    userId: "u_2",
    action: "Created new API key",
    actionType: "create",
    resource: "api_key",
    resourceId: "ak_5678",
    details: "API key 'Production Key' created with read permissions",
    ipAddress: "192.168.1.101",
  },
  {
    id: "3",
    timestamp: "2026-03-22T09:45:00Z",
    user: "admin@example.com",
    userId: "u_3",
    action: "Updated team member role",
    actionType: "update",
    resource: "team",
    resourceId: "u_4",
    details: "Changed role from 'Viewer' to 'Agent'",
    ipAddress: "192.168.1.102",
  },
  {
    id: "4",
    timestamp: "2026-03-22T09:30:00Z",
    user: "system",
    userId: "system",
    action: "Escalated ticket to human agent",
    actionType: "escalation",
    resource: "ticket",
    resourceId: "T-1235",
    details: "Automatic escalation after 3 failed AI attempts",
    ipAddress: "internal",
  },
  {
    id: "5",
    timestamp: "2026-03-22T09:00:00Z",
    user: "john@example.com",
    userId: "u_1",
    action: "User login",
    actionType: "login",
    resource: "session",
    resourceId: "s_9012",
    details: "Successful login from Chrome on macOS",
    ipAddress: "192.168.1.100",
  },
  {
    id: "6",
    timestamp: "2026-03-21T18:00:00Z",
    user: "jane@example.com",
    userId: "u_2",
    action: "Deleted webhook endpoint",
    actionType: "delete",
    resource: "webhook",
    resourceId: "wh_1234",
    details: "Removed webhook https://old.example.com/hook",
    ipAddress: "192.168.1.101",
  },
];

const USERS = ["All Users", "john@example.com", "jane@example.com", "admin@example.com", "system"];
const ACTION_TYPES = ["All Types", "create", "update", "delete", "login", "approval", "escalation"];

export default function AuditLogPage() {
  const [logs] = useState<AuditLogEntry[]>(mockAuditLogs);
  const [searchQuery, setSearchQuery] = useState("");
  const [userFilter, setUserFilter] = useState("All Users");
  const [actionFilter, setActionFilter] = useState("All Types");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesSearch = searchQuery === "" ||
        log.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.details.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.resourceId.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesUser = userFilter === "All Users" || log.user === userFilter;
      const matchesAction = actionFilter === "All Types" || log.actionType === actionFilter;

      let matchesDate = true;
      if (dateFrom) {
        matchesDate = matchesDate && new Date(log.timestamp) >= new Date(dateFrom);
      }
      if (dateTo) {
        matchesDate = matchesDate && new Date(log.timestamp) <= new Date(dateTo + "T23:59:59");
      }

      return matchesSearch && matchesUser && matchesAction && matchesDate;
    });
  }, [logs, searchQuery, userFilter, actionFilter, dateFrom, dateTo]);

  const paginatedLogs = filteredLogs.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);

  const exportToCSV = () => {
    const headers = ["Timestamp", "User", "Action", "Type", "Resource", "Resource ID", "Details", "IP Address"];
    const rows = filteredLogs.map(log => [
      log.timestamp,
      log.user,
      log.action,
      log.actionType,
      log.resource,
      log.resourceId,
      log.details,
      log.ipAddress,
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-log-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
  };

  const clearFilters = () => {
    setSearchQuery("");
    setUserFilter("All Users");
    setActionFilter("All Types");
    setDateFrom("");
    setDateTo("");
    setCurrentPage(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Audit Log</h1>
          <p className="text-muted-foreground">Track all system activities and changes</p>
        </div>
        <Button onClick={exportToCSV} disabled={filteredLogs.length === 0}>
          Export CSV ({filteredLogs.length} entries)
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Filter audit logs by various criteria</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <Input
              placeholder="Search logs..."
              value={searchQuery}
              onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            <Select value={userFilter} onValueChange={v => { setUserFilter(v); setCurrentPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder="Filter by user" />
              </SelectTrigger>
              <SelectContent>
                {USERS.map(user => (
                  <SelectItem key={user} value={user}>{user}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={actionFilter} onValueChange={v => { setActionFilter(v); setCurrentPage(1); }}>
              <SelectTrigger>
                <SelectValue placeholder="Filter by action" />
              </SelectTrigger>
              <SelectContent>
                {ACTION_TYPES.map(action => (
                  <SelectItem key={action} value={action}>{action}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="date"
              placeholder="From date"
              value={dateFrom}
              onChange={e => { setDateFrom(e.target.value); setCurrentPage(1); }}
            />
            <Input
              type="date"
              placeholder="To date"
              value={dateTo}
              onChange={e => { setDateTo(e.target.value); setCurrentPage(1); }}
            />
          </div>
          <div className="flex justify-end mt-4">
            <Button variant="outline" onClick={clearFilters}>Clear Filters</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Activity Log</CardTitle>
          <CardDescription>
            Showing {paginatedLogs.length} of {filteredLogs.length} entries
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>IP Address</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {paginatedLogs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    No audit logs match your filters
                  </TableCell>
                </TableRow>
              ) : (
                paginatedLogs.map(log => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm">
                      {new Date(log.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>{log.user}</TableCell>
                    <TableCell>{log.action}</TableCell>
                    <TableCell>
                      <Badge className={`${ACTION_TYPE_COLORS[log.actionType]} text-white`}>
                        {log.actionType}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-sm">{log.resource}</span>
                      <span className="text-muted-foreground ml-1">({log.resourceId})</span>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                      {log.details}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{log.ipAddress}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <div className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
