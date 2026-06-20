'use client';

import { useNotifications } from '@/hooks/useNotifications';

function priorityColor(priority: string): { dot: string; text: string; border: string } {
  switch (priority?.toLowerCase()) {
    case 'low':
    case 'auto':
      return { dot: 'bg-jarvis-green', text: 'text-jarvis-green', border: 'border-l-jarvis-green' };
    case 'medium':
    case 'batch':
      return { dot: 'bg-jarvis-yellow', text: 'text-jarvis-yellow', border: 'border-l-jarvis-yellow' };
    case 'high':
    case 'escalated':
    case 'urgent':
      return { dot: 'bg-jarvis-red', text: 'text-jarvis-red', border: 'border-l-jarvis-red' };
    default:
      return { dot: 'bg-jarvis-muted', text: 'text-jarvis-muted', border: 'border-l-jarvis-muted' };
  }
}

function priorityBadge(priority: string): string {
  switch (priority?.toLowerCase()) {
    case 'low':
    case 'auto':
      return 'jarvis-badge-green';
    case 'medium':
    case 'batch':
      return 'jarvis-badge-yellow';
    case 'high':
    case 'escalated':
    case 'urgent':
      return 'jarvis-badge-red';
    default:
      return 'jarvis-badge';
  }
}

function categoryLabel(cat: string): string {
  if (!cat) return 'SYSTEM';
  return cat.toUpperCase();
}

function timeAgo(timestamp: string): string {
  if (!timestamp) return '';
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 5) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function LiveActivityFeed() {
  const { data, isLoading } = useNotifications();
  const notifications = data?.notifications || [];

  if (isLoading) {
    return (
      <div className="jarvis-card">
        <h3 className="text-xs text-jarvis-muted tracking-widest uppercase mb-3">Live Activity Feed</h3>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton h-12 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-xs text-jarvis-muted tracking-widest uppercase">Live Activity Feed</h3>
          <span className="inline-flex w-1.5 h-1.5 rounded-full bg-jarvis-green animate-pulse" />
        </div>
        <span className="text-[10px] text-jarvis-muted">{notifications.length} events</span>
      </div>

      <div className="space-y-1.5 max-h-96 overflow-y-auto pr-1">
        {notifications.length === 0 ? (
          <div className="text-center py-8 text-jarvis-muted text-sm">
            No activity yet
          </div>
        ) : (
          notifications.map((notif: any, idx: number) => {
            const pc = priorityColor(notif.priority);
            return (
              <div
                key={notif.key || idx}
                className={`border-l-2 ${pc.border} bg-jarvis-bg/40 rounded-r-lg p-2.5 hover:bg-jarvis-bg/70 transition-colors slide-in-right`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex w-1.5 h-1.5 rounded-full ${pc.dot} flex-shrink-0 mt-1.5`} />
                      <span className="text-sm text-jarvis-text truncate font-medium">
                        {notif.title || 'Untitled Event'}
                      </span>
                      <span className={`jarvis-badge ${priorityBadge(notif.priority)}`}>
                        {(notif.priority || 'info').toUpperCase()}
                      </span>
                    </div>
                    {notif.description && (
                      <p className="text-xs text-jarvis-muted mt-1 pl-3.5 truncate">
                        {notif.description}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <span className="text-[10px] text-jarvis-muted tabular-nums">
                      {timeAgo(notif.timestamp)}
                    </span>
                    {notif.category && (
                      <span className="text-[9px] text-jarvis-cyan tracking-wider">
                        {categoryLabel(notif.category)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}