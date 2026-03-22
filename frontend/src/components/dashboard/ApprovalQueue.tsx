"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, Check, X, Clock, DollarSign } from "lucide-react";

/**
 * Approval request status.
 */
export type ApprovalStatus = "pending" | "approved" | "denied";

/**
 * Approval request data structure.
 */
export interface ApprovalRequest {
  /** Unique approval ID */
  id: string;
  /** Type of approval */
  type: "refund" | "escalation" | "credit" | "action";
  /** Amount in dollars (for refunds/credits) */
  amount?: number;
  /** Currency code */
  currency?: string;
  /** Request description */
  description: string;
  /** Requester information */
  requester: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  };
  /** Related ticket ID */
  ticketId?: string;
  /** Customer ID */
  customerId?: string;
  /** Current status */
  status: ApprovalStatus;
  /** When request was created */
  createdAt: string;
  /** When request was last updated */
  updatedAt: string;
  /** Time pending in minutes */
  minutesPending: number;
}

/**
 * Approval queue props.
 */
export interface ApprovalQueueProps {
  /** Array of pending approvals */
  approvals: ApprovalRequest[];
  /** Loading state */
  isLoading?: boolean;
  /** Callback when approval is approved */
  onApprove?: (approvalId: string) => Promise<void>;
  /** Callback when approval is denied */
  onDeny?: (approvalId: string) => Promise<void>;
  /** Callback to refresh the queue */
  onRefresh?: () => Promise<void>;
  /** Additional CSS classes */
  className?: string;
}

// Amount color coding based on size
function getAmountColor(amount: number): string {
  if (amount < 50) return "text-green-600 bg-green-50";
  if (amount < 200) return "text-blue-600 bg-blue-50";
  if (amount < 500) return "text-orange-600 bg-orange-50";
  return "text-red-600 bg-red-50";
}

// Type labels and icons
const typeConfig: Record<ApprovalRequest["type"], { label: string; icon: React.ReactNode }> = {
  refund: { label: "Refund", icon: <DollarSign className="h-4 w-4" /> },
  escalation: { label: "Escalation", icon: <Clock className="h-4 w-4" /> },
  credit: { label: "Credit", icon: <DollarSign className="h-4 w-4" /> },
  action: { label: "Action", icon: <Clock className="h-4 w-4" /> },
};

// Format relative time
function formatRelativeTime(minutes: number): string {
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${Math.round(minutes)}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Approval Queue Component
 *
 * Displays a list of pending approval requests with quick approve/deny actions.
 * Highlights amounts by size and shows time pending indicators.
 *
 * @example
 * ```tsx
 * <ApprovalQueue
 *   approvals={pendingApprovals}
 *   onApprove={handleApprove}
 *   onDeny={handleDeny}
 *   onRefresh={fetchApprovals}
 * />
 * ```
 */
export function ApprovalQueue({
  approvals,
  isLoading = false,
  onApprove,
  onDeny,
  onRefresh,
  className,
}: ApprovalQueueProps) {
  const [processingId, setProcessingId] = React.useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = React.useState(false);

  const handleApprove = async (approvalId: string) => {
    if (!onApprove) return;
    setProcessingId(approvalId);
    try {
      await onApprove(approvalId);
    } finally {
      setProcessingId(null);
    }
  };

  const handleDeny = async (approvalId: string) => {
    if (!onDeny) return;
    setProcessingId(approvalId);
    try {
      await onDeny(approvalId);
    } finally {
      setProcessingId(null);
    }
  };

  const handleRefresh = async () => {
    if (!onRefresh) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  const pendingApprovals = approvals.filter((a) => a.status === "pending");

  return (
    <Card className={cn("w-full", className)} data-testid="approval-queue">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          Approval Queue
          {pendingApprovals.length > 0 && (
            <Badge variant="default" className="ml-2">
              {pendingApprovals.length}
            </Badge>
          )}
        </CardTitle>
        {onRefresh && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isRefreshing || isLoading}
            aria-label="Refresh approval queue"
          >
            <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse flex space-x-4">
                <div className="flex-1 space-y-2 py-1">
                  <div className="h-4 bg-muted rounded w-3/4"></div>
                  <div className="h-3 bg-muted rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        ) : pendingApprovals.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="text-4xl mb-2" role="img" aria-label="All clear">✅</span>
            <p className="text-muted-foreground">All caught up!</p>
            <p className="text-sm text-muted-foreground mt-1">
              No pending approvals
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {pendingApprovals.map((approval) => (
              <div
                key={approval.id}
                className="border rounded-lg p-4 hover:bg-muted/30 transition-colors"
                data-testid={`approval-item-${approval.id}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className="text-xs">
                        {typeConfig[approval.type].label}
                      </Badge>
                      {approval.amount !== undefined && (
                        <span
                          className={cn(
                            "text-sm font-semibold px-2 py-0.5 rounded",
                            getAmountColor(approval.amount)
                          )}
                        >
                          ${approval.amount.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-medium mb-1">
                      {approval.description}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        {approval.requester.avatar ? (
                          <img
                            src={approval.requester.avatar}
                            alt={approval.requester.name}
                            className="w-4 h-4 rounded-full"
                          />
                        ) : (
                          <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center">
                            {approval.requester.name.charAt(0)}
                          </div>
                        )}
                        {approval.requester.name}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(approval.minutesPending)}
                      </span>
                      {approval.ticketId && (
                        <span>Ticket: #{approval.ticketId.slice(-6)}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-green-600 border-green-200 hover:bg-green-50"
                      onClick={() => handleApprove(approval.id)}
                      disabled={processingId === approval.id}
                      aria-label={`Approve request ${approval.id}`}
                    >
                      <Check className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-red-600 border-red-200 hover:bg-red-50"
                      onClick={() => handleDeny(approval.id)}
                      disabled={processingId === approval.id}
                      aria-label={`Deny request ${approval.id}`}
                    >
                      <X className="h-4 w-4 mr-1" />
                      Deny
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default ApprovalQueue;
