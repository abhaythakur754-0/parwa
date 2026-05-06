"use client";

/**
 * PARWA Quick Actions Component
 *
 * Displays quick action buttons for common dashboard tasks.
 */

import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";

/**
 * Quick action item.
 */
interface QuickAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  variant?: "default" | "outline" | "secondary";
}

/**
 * Props for QuickActions component.
 */
interface QuickActionsProps {
  /** Callback when action is clicked */
  onAction: (action: string) => void;
  /** Loading state for specific actions */
  loadingActions?: string[];
  /** Additional class names */
  className?: string;
}

/**
 * Default quick actions.
 */
const defaultActions: QuickAction[] = [
  {
    id: "create_ticket",
    label: "Create Ticket",
    icon: (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
    ),
    variant: "default" as const,
  },
  {
    id: "approve_pending",
    label: "Approve Pending",
    icon: (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    variant: "outline" as const,
  },
  {
    id: "run_report",
    label: "Run Report",
    icon: (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    variant: "outline" as const,
  },
  {
    id: "view_analytics",
    label: "View Analytics",
    icon: (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
    variant: "outline" as const,
  },
];

/**
 * Quick actions component.
 */
export default function QuickActions({
  onAction,
  loadingActions = [],
  className,
}: QuickActionsProps) {
  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4",
        className
      )}
    >
      <h3 className="text-sm font-medium text-muted-foreground mb-4">
        Quick Actions
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {defaultActions.map((action) => (
          <Button
            key={action.id}
            variant={action.variant}
            className="h-auto py-4 flex-col gap-2"
            onClick={() => onAction(action.id)}
            disabled={loadingActions.includes(action.id)}
          >
            {loadingActions.includes(action.id) ? (
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              action.icon
            )}
            <span className="text-sm">{action.label}</span>
          </Button>
        ))}
      </div>
    </div>
  );
}
