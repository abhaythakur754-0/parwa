"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Bell,
  Check,
  CheckCheck,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle,
  X,
} from "lucide-react";

/**
 * Notification type.
 */
export type NotificationType = "info" | "success" | "warning" | "error";

/**
 * Notification data structure.
 */
export interface Notification {
  /** Unique notification ID */
  id: string;
  /** Notification title */
  title: string;
  /** Notification description */
  description?: string;
  /** Notification type */
  type: NotificationType;
  /** Whether notification is read */
  isRead: boolean;
  /** Creation timestamp */
  createdAt: string;
  /** Related entity ID */
  entityId?: string;
  /** Entity type for navigation */
  entityType?: "ticket" | "approval" | "customer" | "refund";
  /** Action URL */
  actionUrl?: string;
}

/**
 * Notification center props.
 */
export interface NotificationCenterProps {
  /** Array of notifications */
  notifications: Notification[];
  /** Loading state */
  isLoading?: boolean;
  /** Callback when notification is marked as read */
  onMarkAsRead?: (notificationId: string) => void;
  /** Callback when all notifications are marked as read */
  onMarkAllAsRead?: () => void;
  /** Callback when notification is clicked */
  onNotificationClick?: (notification: Notification) => void;
  /** Additional CSS classes */
  className?: string;
}

// Notification type config
const notificationConfig: Record<
  NotificationType,
  { icon: React.ReactNode; color: string; bgColor: string }
> = {
  info: {
    icon: <Info className="h-4 w-4" />,
    color: "text-blue-600",
    bgColor: "bg-blue-100",
  },
  success: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: "text-green-600",
    bgColor: "bg-green-100",
  },
  warning: {
    icon: <AlertTriangle className="h-4 w-4" />,
    color: "text-orange-600",
    bgColor: "bg-orange-100",
  },
  error: {
    icon: <XCircle className="h-4 w-4" />,
    color: "text-red-600",
    bgColor: "bg-red-100",
  },
};

// Format relative time
function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

/**
 * Notification Center Component
 *
 * A dropdown notification center with bell icon, unread badge, and
 * mark as read functionality.
 *
 * @example
 * ```tsx
 * <NotificationCenter
 *   notifications={notifications}
 *   onMarkAsRead={(id) => markAsRead(id)}
 *   onMarkAllAsRead={markAllAsRead}
 *   onNotificationClick={(n) => router.push(n.actionUrl)}
 * />
 * ```
 */
export function NotificationCenter({
  notifications,
  isLoading = false,
  onMarkAsRead,
  onMarkAllAsRead,
  onNotificationClick,
  className,
}: NotificationCenterProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  const unreadCount = notifications.filter((n) => !n.isRead).length;

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.isRead && onMarkAsRead) {
      onMarkAsRead(notification.id);
    }
    onNotificationClick?.(notification);
    setIsOpen(false);
  };

  const handleMarkAllAsRead = (e: React.MouseEvent) => {
    e.stopPropagation();
    onMarkAllAsRead?.();
  };

  return (
    <div className={cn("relative", className)} ref={dropdownRef}>
      {/* Bell button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className="relative"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <Badge
            variant="destructive"
            className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </Badge>
        )}
      </Button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute right-0 top-full mt-2 w-80 bg-background border rounded-lg shadow-lg z-50"
          data-testid="notification-dropdown"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b">
            <h3 className="font-semibold">Notifications</h3>
            {unreadCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={handleMarkAllAsRead}
              >
                <CheckCheck className="h-4 w-4 mr-1" />
                Mark all read
              </Button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex space-x-3">
                    <div className="w-10 h-10 bg-muted rounded-full"></div>
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-muted rounded w-3/4"></div>
                      <div className="h-3 bg-muted rounded w-1/2"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Bell className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-muted-foreground">No notifications</p>
              </div>
            ) : (
              <div className="divide-y">
                {notifications.map((notification) => {
                  const config = notificationConfig[notification.type];
                  return (
                    <div
                      key={notification.id}
                      className={cn(
                        "p-3 hover:bg-muted/50 cursor-pointer transition-colors",
                        !notification.isRead && "bg-primary/5"
                      )}
                      onClick={() => handleNotificationClick(notification)}
                      data-testid={`notification-${notification.id}`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Icon */}
                        <div
                          className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                            config.bgColor
                          )}
                        >
                          <span className={config.color}>{config.icon}</span>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p
                              className={cn(
                                "text-sm",
                                !notification.isRead && "font-semibold"
                              )}
                            >
                              {notification.title}
                            </p>
                            <div className="flex items-center gap-1 shrink-0">
                              {!notification.isRead && (
                                <div className="w-2 h-2 bg-primary rounded-full"></div>
                              )}
                              <span className="text-xs text-muted-foreground">
                                {formatRelativeTime(notification.createdAt)}
                              </span>
                            </div>
                          </div>
                          {notification.description && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                              {notification.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-2 border-t">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs"
                onClick={() => setIsOpen(false)}
              >
                Close
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default NotificationCenter;
