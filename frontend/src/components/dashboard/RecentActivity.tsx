"use client";

/**
 * PARWA Recent Activity Component
 *
 * Displays a feed of recent activity items with icons and timestamps.
 */

import { cn } from "@/utils/utils";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Activity type.
 */
export type ActivityType =
  | "ticket_created"
  | "ticket_resolved"
  | "approval"
  | "escalation"
  | "agent_action"
  | "customer_interaction"
  | "system";

/**
 * Activity item.
 */
export interface ActivityItem {
  /** Unique ID */
  id: string;
  /** Type of activity */
  type: ActivityType;
  /** User who performed the action */
  user: string;
  /** Action description */
  action: string;
  /** Timestamp */
  timestamp: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Props for RecentActivity component.
 */
interface RecentActivityProps {
  /** List of activity items */
  activities: ActivityItem[];
  /** Loading state */
  isLoading?: boolean;
  /** Max items to show */
  maxItems?: number;
  /** Show view all link */
  showViewAll?: boolean;
  /** Additional class names */
  className?: string;
}

/**
 * Activity type configurations.
 */
const activityConfig: Record<
  ActivityType,
  { icon: React.ReactNode; color: string; bgColor: string }
> = {
  ticket_created: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
    ),
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/50",
  },
  ticket_resolved: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-900/50",
  },
  approval: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900/50",
  },
  escalation: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
      </svg>
    ),
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-100 dark:bg-orange-900/50",
  },
  agent_action: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    color: "text-cyan-600 dark:text-cyan-400",
    bgColor: "bg-cyan-100 dark:bg-cyan-900/50",
  },
  customer_interaction: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    ),
    color: "text-pink-600 dark:text-pink-400",
    bgColor: "bg-pink-100 dark:bg-pink-900/50",
  },
  system: {
    icon: (
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    color: "text-gray-600 dark:text-gray-400",
    bgColor: "bg-gray-100 dark:bg-gray-900/50",
  },
};

/**
 * Format relative time.
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

/**
 * Activity item skeleton.
 */
function ActivitySkeleton() {
  return (
    <div className="flex items-start gap-3 animate-pulse">
      <div className="h-8 w-8 rounded-full bg-muted" />
      <div className="flex-1 space-y-1">
        <div className="h-4 w-3/4 bg-muted rounded" />
        <div className="h-3 w-1/4 bg-muted rounded" />
      </div>
    </div>
  );
}

/**
 * Recent activity component.
 */
export default function RecentActivity({
  activities,
  isLoading = false,
  maxItems = 10,
  showViewAll = true,
  className,
}: RecentActivityProps) {
  const displayActivities = activities.slice(0, maxItems);

  /**
   * Empty state.
   */
  const EmptyState = () => (
    <div className="text-center py-8">
      <svg
        className="h-12 w-12 mx-auto text-muted-foreground mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
      <p className="text-muted-foreground">No recent activity</p>
    </div>
  );

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">Recent Activity</CardTitle>
        {showViewAll && activities.length > 0 && (
          <Button variant="ghost" size="sm" asChild>
            <a href="/dashboard/activity">View All</a>
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <ActivitySkeleton key={i} />
            ))}
          </div>
        ) : activities.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            {displayActivities.map((activity) => {
              const config = activityConfig[activity.type] || activityConfig.system;

              return (
                <div
                  key={activity.id}
                  className="flex items-start gap-3 group"
                >
                  {/* Icon */}
                  <div
                    className={cn(
                      "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0",
                      config.bgColor,
                      config.color
                    )}
                  >
                    {config.icon}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">
                      <span className="font-medium">{activity.user}</span>
                      <span className="text-muted-foreground"> {activity.action}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatRelativeTime(activity.timestamp)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
