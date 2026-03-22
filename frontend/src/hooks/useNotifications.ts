/**
 * PARWA useNotifications Hook
 *
 * Custom hook for notification management.
 * Handles fetching, marking as read, and real-time updates.
 *
 * Features:
 * - Fetch notifications list
 * - Mark as read functionality
 * - Unread count
 * - Real-time subscription (future)
 */

import { useState, useCallback, useEffect } from "react";
import { apiClient } from "../services/api/client";
import { useUIStore } from "../stores/uiStore";

/**
 * Notification type enumeration.
 */
export type NotificationType =
  | "ticket_created"
  | "ticket_updated"
  | "ticket_resolved"
  | "approval_pending"
  | "approval_processed"
  | "escalation"
  | "agent_status"
  | "system"
  | "alert";

/**
 * Notification priority enumeration.
 */
export type NotificationPriority = "low" | "medium" | "high" | "critical";

/**
 * Notification interface.
 */
export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  priority: NotificationPriority;
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
  readAt?: string;
}

/**
 * Notifications list response.
 */
export interface NotificationsListResponse {
  notifications: Notification[];
  total: number;
  unreadCount: number;
  page: number;
  pageSize: number;
}

/**
 * useNotifications hook return type.
 */
export interface UseNotificationsReturn {
  /** List of notifications */
  notifications: Notification[];
  /** Unread count */
  unreadCount: number;
  /** Total count for pagination */
  total: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: string | null;

  // Actions
  /** Fetch notifications */
  fetchNotifications: (page?: number) => Promise<void>;
  /** Mark a notification as read */
  markAsRead: (id: string) => Promise<void>;
  /** Mark all notifications as read */
  markAllAsRead: () => Promise<void>;
  /** Subscribe to real-time updates */
  subscribe: () => () => void;
  /** Refresh notifications */
  refresh: () => Promise<void>;
  /** Clear error */
  clearError: () => void;
}

/**
 * Custom hook for notification management.
 *
 * @returns Notifications state and actions
 *
 * @example
 * ```tsx
 * function NotificationCenter() {
 *   const {
 *     notifications,
 *     unreadCount,
 *     markAsRead,
 *     markAllAsRead
 *   } = useNotifications();
 *
 *   return (
 *     <div>
 *       <Badge count={unreadCount} />
 *       {notifications.map(notification => (
 *         <NotificationItem
 *           key={notification.id}
 *           notification={notification}
 *           onMarkRead={() => markAsRead(notification.id)}
 *         />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useNotifications(): UseNotificationsReturn {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { addToast } = useUIStore();

  /**
   * Fetch notifications from API.
   */
  const fetchNotifications = useCallback(
    async (newPage = 1): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<NotificationsListResponse>("/notifications", {
          page: String(newPage),
          pageSize: "20",
        });

        setNotifications(response.data.notifications);
        setTotal(response.data.total);
        setUnreadCount(response.data.unreadCount);
        setPage(response.data.page);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to fetch notifications";
        setError(message);
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [addToast]
  );

  /**
   * Mark a notification as read.
   */
  const markAsRead = useCallback(
    async (id: string): Promise<void> => {
      try {
        await apiClient.post<void>(`/notifications/${id}/read`);

        // Update local state
        setNotifications((prev) =>
          prev.map((n) =>
            n.id === id ? { ...n, read: true, readAt: new Date().toISOString() } : n
          )
        );

        // Decrease unread count
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to mark as read";
        addToast({
          title: "Error",
          description: message,
          variant: "error",
        });
        throw err;
      }
    },
    [addToast]
  );

  /**
   * Mark all notifications as read.
   */
  const markAllAsRead = useCallback(async (): Promise<void> => {
    try {
      await apiClient.post<void>("/notifications/read-all");

      // Update local state
      setNotifications((prev) =>
        prev.map((n) => ({
          ...n,
          read: true,
          readAt: n.readAt || new Date().toISOString(),
        }))
      );

      // Reset unread count
      setUnreadCount(0);

      addToast({
        title: "All notifications read",
        description: "All notifications have been marked as read.",
        variant: "success",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to mark all as read";
      addToast({
        title: "Error",
        description: message,
        variant: "error",
      });
      throw err;
    }
  }, [addToast]);

  /**
   * Subscribe to real-time updates.
   * Returns cleanup function.
   */
  const subscribe = useCallback((): (() => void) => {
    // Polling implementation (WebSocket would be better for production)
    const intervalId = setInterval(() => {
      fetchNotifications(page);
    }, 30000); // Poll every 30 seconds

    return () => {
      clearInterval(intervalId);
    };
  }, [fetchNotifications, page]);

  /**
   * Refresh notifications.
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchNotifications(page);
  }, [fetchNotifications, page]);

  /**
   * Clear error.
   */
  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  /**
   * Auto-fetch on mount.
   */
  useEffect(() => {
    fetchNotifications();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    notifications,
    unreadCount,
    total,
    isLoading,
    error,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    subscribe,
    refresh,
    clearError,
  };
}

export default useNotifications;
