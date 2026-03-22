"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Ticket priority type.
 */
export type TicketPriority = "low" | "medium" | "high" | "urgent";

/**
 * Ticket status type.
 */
export type TicketStatus = "open" | "in_progress" | "pending" | "resolved" | "closed";

/**
 * Ticket data structure.
 */
export interface Ticket {
  /** Unique ticket ID */
  id: string;
  /** Ticket subject line */
  subject: string;
  /** Customer information */
  customer: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  };
  /** Current status */
  status: TicketStatus;
  /** Priority level */
  priority: TicketPriority;
  /** Assigned agent */
  assignee?: {
    id: string;
    name: string;
    avatar?: string;
  };
  /** Creation timestamp */
  createdAt: string;
  /** Last update timestamp */
  updatedAt: string;
  /** Communication channel */
  channel: "email" | "chat" | "voice" | "sms";
}

/**
 * Sort configuration.
 */
export interface SortConfig {
  /** Column to sort by */
  column: keyof Ticket | null;
  /** Sort direction */
  direction: "asc" | "desc";
}

/**
 * Ticket list props.
 */
export interface TicketListProps {
  /** Array of tickets to display */
  tickets: Ticket[];
  /** Loading state */
  isLoading?: boolean;
  /** Compact view mode */
  compact?: boolean;
  /** Callback when ticket is clicked */
  onTicketClick?: (ticket: Ticket) => void;
  /** Callback when sort changes */
  onSort?: (config: SortConfig) => void;
  /** Current sort configuration */
  sortConfig?: SortConfig;
  /** Additional CSS classes */
  className?: string;
}

// Status badge variants
const statusVariants: Record<TicketStatus, "default" | "secondary" | "outline" | "destructive"> = {
  open: "default",
  in_progress: "secondary",
  pending: "outline",
  resolved: "secondary",
  closed: "outline",
};

// Status labels
const statusLabels: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

// Priority colors
const priorityColors: Record<TicketPriority, string> = {
  low: "text-gray-500",
  medium: "text-blue-500",
  high: "text-orange-500",
  urgent: "text-red-500",
};

/**
 * Ticket List Component
 *
 * Displays a sortable, filterable list of support tickets with
 * status badges, priority indicators, and assignee avatars.
 *
 * @example
 * ```tsx
 * <TicketList
 *   tickets={tickets}
 *   onTicketClick={(ticket) => router.push(`/tickets/${ticket.id}`)}
 *   compact={true}
 * />
 * ```
 */
export function TicketList({
  tickets,
  isLoading = false,
  compact = false,
  onTicketClick,
  onSort,
  sortConfig,
  className,
}: TicketListProps) {
  const handleSort = (column: keyof Ticket) => {
    if (!onSort) return;

    const newDirection =
      sortConfig?.column === column && sortConfig.direction === "asc"
        ? "desc"
        : "asc";

    onSort({ column, direction: newDirection });
  };

  const renderSortIcon = (column: keyof Ticket) => {
    if (sortConfig?.column !== column) return null;

    return (
      <span className="ml-1" aria-label={`Sorted ${sortConfig.direction === "asc" ? "ascending" : "descending"}`}>
        {sortConfig.direction === "asc" ? "↑" : "↓"}
      </span>
    );
  };

  if (isLoading) {
    return (
      <Card className={cn("w-full", className)}>
        <CardContent className="p-4">
          <div className="flex items-center justify-center py-8">
            <div className="animate-pulse flex space-x-4">
              <div className="flex-1 space-y-4 py-1">
                <div className="h-4 bg-muted rounded w-3/4"></div>
                <div className="h-4 bg-muted rounded w-1/2"></div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (tickets.length === 0) {
    return (
      <Card className={cn("w-full", className)}>
        <CardContent className="p-4">
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="text-4xl mb-2" role="img" aria-label="Empty inbox">📭</span>
            <p className="text-muted-foreground">No tickets found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Tickets will appear here when customers submit requests
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("w-full", className)} data-testid="ticket-list">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              className="cursor-pointer hover:bg-muted/50 select-none"
              onClick={() => handleSort("subject")}
            >
              Subject {renderSortIcon("subject")}
            </TableHead>
            <TableHead>Customer</TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50 select-none"
              onClick={() => handleSort("status")}
            >
              Status {renderSortIcon("status")}
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-muted/50 select-none"
              onClick={() => handleSort("priority")}
            >
              Priority {renderSortIcon("priority")}
            </TableHead>
            {!compact && <TableHead>Assignee</TableHead>}
            {!compact && <TableHead>Channel</TableHead>}
            <TableHead
              className="cursor-pointer hover:bg-muted/50 select-none"
              onClick={() => handleSort("updatedAt")}
            >
              Updated {renderSortIcon("updatedAt")}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tickets.map((ticket) => (
            <TableRow
              key={ticket.id}
              className="cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => onTicketClick?.(ticket)}
              data-testid={`ticket-row-${ticket.id}`}
            >
              <TableCell className="font-medium max-w-xs truncate">
                {ticket.subject}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {ticket.customer.avatar ? (
                    <img
                      src={ticket.customer.avatar}
                      alt={ticket.customer.name}
                      className="w-6 h-6 rounded-full"
                    />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-xs">
                      {ticket.customer.name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="flex flex-col">
                    <span className="text-sm">{ticket.customer.name}</span>
                    <span className="text-xs text-muted-foreground">{ticket.customer.email}</span>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariants[ticket.status]}>
                  {statusLabels[ticket.status]}
                </Badge>
              </TableCell>
              <TableCell>
                <span className={cn("font-medium", priorityColors[ticket.priority])}>
                  {ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)}
                </span>
              </TableCell>
              {!compact && (
                <TableCell>
                  {ticket.assignee ? (
                    <div className="flex items-center gap-2">
                      {ticket.assignee.avatar ? (
                        <img
                          src={ticket.assignee.avatar}
                          alt={ticket.assignee.name}
                          className="w-6 h-6 rounded-full"
                        />
                      ) : (
                        <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs">
                          {ticket.assignee.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <span className="text-sm">{ticket.assignee.name}</span>
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-sm">Unassigned</span>
                  )}
                </TableCell>
              )}
              {!compact && (
                <TableCell className="capitalize">
                  <span className="flex items-center gap-1">
                    {ticket.channel === "email" && "📧"}
                    {ticket.channel === "chat" && "💬"}
                    {ticket.channel === "voice" && "📞"}
                    {ticket.channel === "sms" && "📱"}
                    {ticket.channel}
                  </span>
                </TableCell>
              )}
              <TableCell className="text-muted-foreground text-sm">
                {new Date(ticket.updatedAt).toLocaleDateString()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

export default TicketList;
