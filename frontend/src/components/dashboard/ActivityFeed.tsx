"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  MessageSquare,
  RefreshCw,
  UserPlus,
  AlertTriangle,
  CheckCircle,
  DollarSign,
  Settings,
  FileText,
  ChevronDown,
  Filter,
} from "lucide-react";

/**
 * Activity type.
 */
export type ActivityType =
  | "ticket_created"
  | "ticket_resolved"
  | "message_sent"
  | "refund_processed"
  | "escalation"
  | "user_joined"
  | "settings_changed"
  | "approval_approved"
  | "approval_denied";

/**
 * Activity data structure.
 */
export interface Activity {
  /** Unique activity ID */
  id: string;
  /** Activity type */
  type: ActivityType;
  /** Activity description */
  description: string;
  /** User who performed the action */
  user: {
    id: string;
    name: string;
    avatar?: string;
  };
  /** Related entity ID */
  entityId?: string;
  /** Entity type */
  entityType?: "ticket" | "customer" | "refund" | "approval";
  /** Activity timestamp */
  timestamp: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Activity feed props.
 */
export interface ActivityFeedProps {
  /** Array of activities */
  activities: Activity[];
  /** Loading state */
  isLoading?: boolean;
  /** Show filter dropdown */
  showFilters?: boolean;
  /** Selected filter types */
  selectedFilters?: ActivityType[];
  /** Callback when filter changes */
  onFilterChange?: (filters: ActivityType[]) => void;
  /** Callback to load more activities */
  onLoadMore?: () => void;
  /** Whether more activities are available */
  hasMore?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// Activity type config
const activityConfig: Record<
  ActivityType,
  { icon: React.ReactNode; color: string; bgColor: string; label: string }
> = {
  ticket_created: {
    icon: <MessageSquare className="h-4 w-4" />,
    color: "text-blue-600",
    bgColor: "bg-blue-100",
    label: "Ticket Created",
  },
  ticket_resolved: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: "text-green-600",
    bgColor: "bg-green-100",
    label: "Ticket Resolved",
  },
  message_sent: {
    icon: <MessageSquare className="h-4 w-4" />,
    color: "text-purple-600",
    bgColor: "bg-purple-100",
    label: "Message Sent",
  },
  refund_processed: {
    icon: <DollarSign className="h-4 w-4" />,
    color: "text-orange-600",
    bgColor: "bg-orange-100",
    label: "Refund Processed",
  },
  escalation: {
    icon: <AlertTriangle className="h-4 w-4" />,
    color: "text-red-600",
    bgColor: "bg-red-100",
    label: "Escalation",
  },
  user_joined: {
    icon: <UserPlus className="h-4 w-4" />,
    color: "text-indigo-600",
    bgColor: "bg-indigo-100",
    label: "User Joined",
  },
  settings_changed: {
    icon: <Settings className="h-4 w-4" />,
    color: "text-gray-600",
    bgColor: "bg-gray-100",
    label: "Settings Changed",
  },
  approval_approved: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: "text-green-600",
    bgColor: "bg-green-100",
    label: "Approval Approved",
  },
  approval_denied: {
    icon: <AlertTriangle className="h-4 w-4" />,
    color: "text-red-600",
    bgColor: "bg-red-100",
    label: "Approval Denied",
  },
};

// Format relative time
function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}

/**
 * Activity Feed Component
 *
 * Displays a chronological list of activities with filtering and pagination.
 *
 * @example
 * ```tsx
 * <ActivityFeed
 *   activities={activities}
 *   showFilters={true}
 *   onLoadMore={loadMoreActivities}
 *   hasMore={true}
 * />
 * ```
 */
export function ActivityFeed({
  activities,
  isLoading = false,
  showFilters = false,
  selectedFilters = [],
  onFilterChange,
  onLoadMore,
  hasMore = false,
  className,
}: ActivityFeedProps) {
  const [showFilterDropdown, setShowFilterDropdown] = React.useState(false);

  const handleFilterToggle = (type: ActivityType) => {
    if (!onFilterChange) return;

    const newFilters = selectedFilters.includes(type)
      ? selectedFilters.filter((t) => t !== type)
      : [...selectedFilters, type];

    onFilterChange(newFilters);
  };

  const clearFilters = () => {
    onFilterChange?.([]);
  };

  return (
    <Card className={cn("w-full", className)} data-testid="activity-feed">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-semibold">Activity Feed</CardTitle>
        {showFilters && (
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowFilterDropdown(!showFilterDropdown)}
              aria-label="Filter activities"
            >
              <Filter className="h-4 w-4 mr-1" />
              Filters
              {selectedFilters.length > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {selectedFilters.length}
                </Badge>
              )}
            </Button>

            {showFilterDropdown && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-background border rounded-md shadow-lg z-10">
                <div className="p-2 border-b">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs"
                    onClick={clearFilters}
                    disabled={selectedFilters.length === 0}
                  >
                    Clear filters
                  </Button>
                </div>
                <div className="max-h-64 overflow-y-auto p-2">
                  {(Object.keys(activityConfig) as ActivityType[]).map((type) => (
                    <label
                      key={type}
                      className="flex items-center gap-2 p-2 hover:bg-muted rounded cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedFilters.includes(type)}
                        onChange={() => handleFilterToggle(type)}
                        className="rounded"
                      />
                      <span
                        className={cn(
                          "w-6 h-6 rounded flex items-center justify-center",
                          activityConfig[type].bgColor
                        )}
                      >
                        <span className={activityConfig[type].color}>
                          {activityConfig[type].icon}
                        </span>
                      </span>
                      <span className="text-sm">{activityConfig[type].label}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="animate-pulse flex space-x-4">
                <div className="w-10 h-10 bg-muted rounded-full"></div>
                <div className="flex-1 space-y-2 py-1">
                  <div className="h-4 bg-muted rounded w-3/4"></div>
                  <div className="h-3 bg-muted rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        ) : activities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="text-4xl mb-2" role="img" aria-label="No activity">📋</span>
            <p className="text-muted-foreground">No activity yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Activities will appear here as they happen
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              {activities.map((activity) => {
                const config = activityConfig[activity.type];
                return (
                  <div
                    key={activity.id}
                    className="flex items-start gap-3"
                    data-testid={`activity-${activity.id}`}
                  >
                    {/* Icon */}
                    <div
                      className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center shrink-0",
                        config.bgColor
                      )}
                    >
                      <span className={config.color}>{config.icon}</span>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {activity.user.avatar ? (
                          <img
                            src={activity.user.avatar}
                            alt={activity.user.name}
                            className="w-5 h-5 rounded-full"
                          />
                        ) : (
                          <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs">
                            {activity.user.name.charAt(0)}
                          </div>
                        )}
                        <span className="font-medium text-sm">
                          {activity.user.name}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {activity.description}
                      </p>
                      {activity.entityId && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {activity.entityType}: #{activity.entityId.slice(-6)}
                        </p>
                      )}
                    </div>

                    {/* Timestamp */}
                    <span className="text-xs text-muted-foreground shrink-0">
                      {formatRelativeTime(activity.timestamp)}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Load more */}
            {hasMore && onLoadMore && (
              <div className="mt-4 flex justify-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onLoadMore}
                  aria-label="Load more activities"
                >
                  <ChevronDown className="h-4 w-4 mr-1" />
                  Load More
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default ActivityFeed;
