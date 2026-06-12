"use client";

import { useState, useEffect } from "react";
import { Bell, X, Check, AlertTriangle, Info, AlertCircle } from "lucide-react";

interface Notification {
  id: string;
  category: string;
  severity: string;
  title: string;
  body: string | null;
  action_url: string | null;
  read: boolean;
  created_at: string;
}

/**
 * NotificationBell — GAP 12 notification component.
 * Shows bell icon with unread count badge and dropdown panel.
 */
export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isOpen && notifications.length === 0) fetchNotifications();
  }, [isOpen]);

  const fetchUnreadCount = async () => {
    try {
      const res = await fetch("/api/notifications/unread-count");
      const data = await res.json();
      setUnreadCount(data.unread_count || 0);
    } catch { /* silently fail */ }
  };

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/notifications/list?limit=20");
      const data = await res.json();
      setNotifications(data.notifications || []);
    } catch { /* silently fail */ }
    finally { setLoading(false); }
  };

  const markAsRead = async (notificationId?: string) => {
    try {
      await fetch("/api/notifications/mark-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notification_id: notificationId || null }),
      });
      if (notificationId) {
        setNotifications((prev) => prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n)));
      } else {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      }
      setUnreadCount(0);
    } catch { /* silently fail */ }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "critical": return <AlertCircle className="h-4 w-4 text-red-500" />;
      case "high": return <AlertTriangle className="h-4 w-4 text-orange-500" />;
      case "medium": return <Info className="h-4 w-4 text-yellow-500" />;
      default: return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = { integration_health: "Integration", billing: "Billing", webhooks: "Webhook", ai_actions: "AI Action", system: "System", compliance: "Compliance" };
    return labels[category] || category;
  };

  const formatTime = (dateStr: string) => {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="relative">
      <button onClick={() => setIsOpen(!isOpen)} className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors">
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 inline-flex items-center justify-center h-5 min-w-[20px] px-1 text-xs font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-96 bg-white rounded-lg shadow-xl border border-gray-200 z-50">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
              <div className="flex items-center gap-2">
                {unreadCount > 0 && <button onClick={() => markAsRead()} className="text-xs text-blue-600 hover:text-blue-800">Mark all read</button>}
                <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-gray-600"><X className="h-4 w-4" /></button>
              </div>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-center text-sm text-gray-500">Loading...</div>
              ) : notifications.length === 0 ? (
                <div className="p-8 text-center">
                  <Bell className="mx-auto h-8 w-8 text-gray-300 mb-2" />
                  <p className="text-sm text-gray-500">No notifications yet</p>
                </div>
              ) : (
                notifications.map((n) => (
                  <div key={n.id} className={`px-4 py-3 border-b border-gray-50 hover:bg-gray-50 cursor-pointer ${!n.read ? "bg-blue-50" : ""}`} onClick={() => !n.read && markAsRead(n.id)}>
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 mt-0.5">{getSeverityIcon(n.severity)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-gray-500">{getCategoryLabel(n.category)}</span>
                          {!n.read && <span className="h-2 w-2 rounded-full bg-blue-500" />}
                        </div>
                        <p className="text-sm font-medium text-gray-900 truncate">{n.title}</p>
                        {n.body && <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{n.body}</p>}
                        <p className="text-xs text-gray-400 mt-1">{formatTime(n.created_at)}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
