'use client';

import { useCollisionStore } from '@/lib/collision-store';
import { AlertTriangle, Users, Edit3 } from 'lucide-react';

interface CollisionBannerProps {
  ticketId: string;
  currentUserId?: string;
}

export function CollisionBanner({ ticketId, currentUserId }: CollisionBannerProps) {
  // Use primitive selectors to avoid infinite loop with useSyncExternalStore
  // (getCollisions returns a new array reference each time)
  const collisionCount = useCollisionStore((s) => {
    const all = s.collisions.get(ticketId) || [];
    return all.filter(u => u.userId !== currentUserId).length;
  });
  const hasEditor = useCollisionStore((s) => s.hasEditor(ticketId));
  const firstUserName = useCollisionStore((s) => {
    const all = s.collisions.get(ticketId) || [];
    const other = all.filter(u => u.userId !== currentUserId);
    return other[0]?.userName || '';
  });
  const isEditing = useCollisionStore((s) => {
    const all = s.collisions.get(ticketId) || [];
    return all.some(u => u.userId !== currentUserId && u.action === 'editing');
  });

  if (collisionCount === 0) return null;

  return (
    <div
      data-testid="collision-banner"
      role="alert"
      className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border text-sm ${
        isEditing
          ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
          : 'bg-blue-500/10 border-blue-500/20 text-blue-300'
      }`}
    >
      {isEditing ? (
        <AlertTriangle className="w-4 h-4 shrink-0" data-testid="collision-warning-icon" />
      ) : (
        <Users className="w-4 h-4 shrink-0" data-testid="collision-viewing-icon" />
      )}

      <div className="flex-1">
        <span className="font-medium">
          {collisionCount === 1
            ? firstUserName
            : `${firstUserName} and ${collisionCount - 1} other${collisionCount > 2 ? 's' : ''}`}
        </span>
        <span className="ml-1 opacity-80">
          {isEditing ? (
            <>
              {' '}is <Edit3 className="w-3 h-3 inline" /> editing this ticket
            </>
          ) : (
            ' is viewing this ticket'
          )}
        </span>
      </div>

      {isEditing && (
        <span className="text-xs opacity-60">
          Be careful — changes may conflict
        </span>
      )}
    </div>
  );
}
