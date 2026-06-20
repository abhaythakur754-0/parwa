'use client';

import { useQuery } from '@tanstack/react-query';
import { jarvisApi } from '@/lib/api';

import { getCurrentTenantId } from '@/lib/auth-context';

export default function UrgentAttention() {
  const { data: notifications, isLoading } = useQuery<any>({
    queryKey: ['notifications-urgent', getCurrentTenantId()],
    queryFn: () => jarvisApi.getNotifications(getCurrentTenantId(), false),
    refetchInterval: 8000,
  });

  const allNotifs: any[] = notifications?.notifications || [];
  const urgent = allNotifs.filter(
    (n: any) =>
      n.priority?.toLowerCase() === 'high' ||
      n.priority?.toLowerCase() === 'urgent' ||
      n.priority?.toLowerCase() === 'escalated'
  );

  if (isLoading) {
    return (
      <div className="jarvis-card border-jarvis-red/20">
        <h3 className="text-xs text-jarvis-red tracking-widest uppercase mb-3">⚠ Urgent Attention</h3>
        <div className="skeleton h-10 rounded" />
      </div>
    );
  }

  if (urgent.length === 0) {
    return (
      <div className="jarvis-card border-jarvis-green/10">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-xs text-jarvis-green tracking-widest uppercase">✓ No Urgent Items</h3>
        </div>
        <p className="text-[11px] text-jarvis-muted">All high-priority items are handled</p>
      </div>
    );
  }

  return (
    <div className="jarvis-card border-jarvis-red/30 bg-red-950/10">
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex w-2 h-2 rounded-full bg-jarvis-red animate-pulse" />
        <h3 className="text-xs text-jarvis-red tracking-widest uppercase font-bold">
          ⚠ Urgent Attention — {urgent.length} Item{urgent.length !== 1 ? 's' : ''}
        </h3>
      </div>
      <div className="space-y-2 max-h-40 overflow-y-auto">
        {urgent.map((item: any, idx: number) => (
          <div
            key={item.key || idx}
            className="bg-jarvis-red/5 border border-jarvis-red/20 rounded-lg p-2.5 slide-in-right"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-jarvis-red font-medium truncate">{item.title || 'Urgent Alert'}</p>
                {item.description && (
                  <p className="text-[11px] text-jarvis-muted mt-0.5 truncate">{item.description}</p>
                )}
              </div>
              {item.timestamp && (
                <span className="text-[10px] text-jarvis-muted flex-shrink-0">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </span>
              )}
            </div>
            {item.customer_name && (
              <div className="mt-1.5 text-[10px] text-jarvis-cyan">
                VIP: {item.customer_name}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}