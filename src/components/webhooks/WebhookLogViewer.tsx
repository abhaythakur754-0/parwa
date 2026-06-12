"use client";

import { useState, useEffect } from "react";
import { RefreshCw, RotateCcw, ExternalLink, Loader2 } from "lucide-react";

interface WebhookEvent {
  id: string;
  source: string;
  event_type: string;
  status: string;
  retry_count: number;
  created_at: string;
  processed_at: string | null;
  payload_preview: string | null;
}

/**
 * WebhookLogViewer — Gap A webhook event log viewer.
 * Shows incoming webhook events and allows retry of failed events.
 */
export function WebhookLogViewer() {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/webhooks/events?limit=50");
      const data = await res.json();
      setEvents(data.events || []);
      setTotal(data.total || 0);
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  const retryEvent = async (eventId: string) => {
    try {
      await fetch(`/api/webhooks/events/${eventId}/retry`, { method: "POST" });
      fetchEvents();
    } catch {
      // Silently fail
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "processed":
        return <span className="px-2 py-0.5 text-xs font-medium text-green-700 bg-green-50 rounded-full">Processed</span>;
      case "received":
        return <span className="px-2 py-0.5 text-xs font-medium text-blue-700 bg-blue-50 rounded-full">Received</span>;
      case "failed":
        return <span className="px-2 py-0.5 text-xs font-medium text-red-700 bg-red-50 rounded-full">Failed</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-medium text-gray-700 bg-gray-50 rounded-full">{status}</span>;
    }
  };

  const formatTime = (dateStr: string) => {
    if (!dateStr) return "—";
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Webhook Events</h3>
          <p className="text-sm text-gray-500">{total} events received</p>
        </div>
        <button onClick={fetchEvents} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {loading && events.length === 0 ? (
        <div className="text-center py-8"><Loader2 className="mx-auto h-6 w-6 animate-spin text-gray-400" /></div>
      ) : events.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <ExternalLink className="mx-auto h-8 w-8 text-gray-300 mb-2" />
          <p className="text-sm">No webhook events received yet</p>
          <p className="text-xs text-gray-400 mt-1">Register a webhook in Settings → Integrations</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Event</th>
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Received</th>
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-gray-50">
                  <td className="py-2 px-3">
                    <span className="font-medium text-gray-900">{event.source}</span>
                  </td>
                  <td className="py-2 px-3 text-gray-600">{event.event_type}</td>
                  <td className="py-2 px-3">{getStatusBadge(event.status)}</td>
                  <td className="py-2 px-3 text-gray-500 text-xs">{formatTime(event.created_at)}</td>
                  <td className="py-2 px-3">
                    {event.status === "failed" && (
                      <button onClick={() => retryEvent(event.id)} className="flex items-center gap-1 px-2 py-1 text-xs text-orange-600 hover:text-orange-800 hover:bg-orange-50 rounded transition-colors">
                        <RotateCcw className="h-3 w-3" /> Retry
                      </button>
                    )}
                    {event.retry_count > 0 && (
                      <span className="text-xs text-gray-400">{event.retry_count} retries</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
