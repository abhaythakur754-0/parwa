/**
 * PARWA useCollisionDetection Hook
 *
 * Detects when multiple users are editing the same resource simultaneously,
 * providing reactive collision state and edit lifecycle management.
 * Connects to the useCollisionStore Zustand store and uses useSocket for
 * real-time event subscription with automatic cleanup.
 *
 * Socket.io events (new format):
 *   collision:edit:start  — { resourceId, userId, userName }
 *   collision:edit:stop   — { resourceId, userId, userName }
 *
 * Also compatible with existing events (legacy format):
 *   collision:enter       — { ticket_id, user_id, user_name, action }
 *   collision:leave       — { ticket_id, user_id }
 *   collision:update      — { ticket_id, user_id, field, value }
 *
 * Features:
 *   - Auto-cleanup: stops editing on unmount
 *   - Reactive: re-renders when collision state changes for the given resource
 *   - Provides active editors list and collision boolean
 */

'use client';

import { useCallback, useEffect, useRef, useMemo } from 'react';
import { useCollisionStore, CollisionUser, CollisionAction } from '@/lib/collision-store';
import { useSocket } from '@/hooks/useSocket';
import { socketClient } from '@/lib/socket-client';

// ── Types ────────────────────────────────────────────────────────────

export interface UseCollisionDetectionOptions {
  /** Current user ID (for emitting collision events). */
  userId?: string;
  /** Current user name (for emitting collision events). */
  userName?: string;
}

export interface UseCollisionDetectionReturn {
  /** List of users currently editing the same resource */
  activeEditors: CollisionUser[];
  /** Whether someone else is editing the same resource */
  hasCollision: boolean;
  /** Emit a collision:edit:start event for a resource */
  startEditing: (resourceId: string) => void;
  /** Emit a collision:edit:stop event for a resource */
  stopEditing: (resourceId: string) => void;
}

// ── Payload Normalizers ──────────────────────────────────────────────

/**
 * Normalize a collision:edit:start payload.
 * Supports both new format (resourceId, userId, userName) and
 * legacy format (ticket_id, user_id, user_name, action).
 */
function normalizeEditStartPayload(data: unknown): {
  resourceId: string;
  userId: string;
  userName: string;
  action: CollisionAction;
} | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;

  const resourceId = (d.resourceId as string) || (d.ticket_id as string);
  const userId = (d.userId as string) || (d.user_id as string);
  const userName = (d.userName as string) || (d.user_name as string) || '';

  if (!resourceId || !userId) return null;

  // collision:edit:start is always 'editing'; collision:enter may specify action
  const action = (d.action as CollisionAction) || 'editing';

  return { resourceId, userId, userName, action };
}

/**
 * Normalize a collision:edit:stop payload.
 * Supports both new format (resourceId, userId) and
 * legacy format (ticket_id, user_id).
 */
function normalizeEditStopPayload(data: unknown): {
  resourceId: string;
  userId: string;
} | null {
  if (!data || typeof data !== 'object') return null;

  const d = data as Record<string, unknown>;

  const resourceId = (d.resourceId as string) || (d.ticket_id as string);
  const userId = (d.userId as string) || (d.user_id as string);

  if (!resourceId || !userId) return null;

  return { resourceId, userId };
}

// ── Hook ─────────────────────────────────────────────────────────────

/**
 * Subscribe to collision detection events and provide reactive state
 * for a given resource.
 *
 * @param resourceId - The resource to track collisions for (e.g., ticket ID). If omitted, activeEditors/hasCollision will be empty/false.
 * @param options - Optional userId/userName for emitting collision events.
 */
export function useCollisionDetection(
  resourceId?: string,
  options?: UseCollisionDetectionOptions
): UseCollisionDetectionReturn {
  // ── Refs for stable callbacks ──────────────────────────────────────

  const resourceRef = useRef(resourceId);
  resourceRef.current = resourceId;

  const userIdRef = useRef(options?.userId);
  const userNameRef = useRef(options?.userName);
  userIdRef.current = options?.userId;
  userNameRef.current = options?.userName;

  // Track whether we've started editing (for auto-cleanup on unmount)
  const activeEditingResourceRef = useRef<string | null>(null);

  // ── Subscribe to Socket.io Events ──────────────────────────────────

  // New format: collision:edit:start
  useSocket('collision:edit:start', (...args: unknown[]) => {
    const payload = normalizeEditStartPayload(args[0]);
    if (!payload) return;

    useCollisionStore
      .getState()
      .userEntered(payload.resourceId, payload.userId, payload.userName, payload.action);
  });

  // New format: collision:edit:stop
  useSocket('collision:edit:stop', (...args: unknown[]) => {
    const payload = normalizeEditStopPayload(args[0]);
    if (!payload) return;

    useCollisionStore.getState().userLeft(payload.resourceId, payload.userId);
  });

  // Legacy format: collision:enter
  useSocket('collision:enter', (...args: unknown[]) => {
    const payload = normalizeEditStartPayload(args[0]);
    if (!payload) return;

    useCollisionStore
      .getState()
      .userEntered(payload.resourceId, payload.userId, payload.userName, payload.action);
  });

  // Legacy format: collision:leave
  useSocket('collision:leave', (...args: unknown[]) => {
    const payload = normalizeEditStopPayload(args[0]);
    if (!payload) return;

    useCollisionStore.getState().userLeft(payload.resourceId, payload.userId);
  });

  // Legacy format: collision:update
  useSocket('collision:update', (...args: unknown[]) => {
    const data = args[0] as Record<string, unknown> | undefined;
    if (!data) return;

    const resourceId = (data.resourceId as string) || (data.ticket_id as string);
    const userId = (data.userId as string) || (data.user_id as string);
    const field = data.field as string | undefined;

    if (!resourceId || !userId || !field) return;

    useCollisionStore.getState().fieldUpdate(resourceId, userId, field);
  });

  // ── Reactive Store State ───────────────────────────────────────────

  const collisionsMap = useCollisionStore((state) => state.collisions);

  const activeEditors = useMemo<CollisionUser[]>(() => {
    if (!resourceId) return [];
    const users = collisionsMap.get(resourceId) || [];
    // Return all users on this resource who are editing
    return users.filter((u) => u.action === 'editing');
  }, [collisionsMap, resourceId]);

  const hasCollision = useMemo(() => {
    if (!resourceId) return false;
    const uid = userIdRef.current;
    // Has collision if someone ELSE is editing this resource
    return activeEditors.some((u) => u.userId !== uid);
  }, [activeEditors, resourceId]);

  // ── Action: Start Editing ──────────────────────────────────────────

  const startEditing = useCallback((targetResourceId: string) => {
    const uid = userIdRef.current;
    const uname = userNameRef.current;

    if (!uid) {
      if (process.env.NODE_ENV === 'development') {
        console.warn('[useCollisionDetection] Cannot start editing — no userId provided');
      }
      return;
    }

    // Track for auto-cleanup
    activeEditingResourceRef.current = targetResourceId;

    // Update local store
    useCollisionStore.getState().userEntered(targetResourceId, uid, uname || '', 'editing');

    // Emit to other users via Socket.io
    socketClient.emit('collision:edit:start', {
      resourceId: targetResourceId,
      userId: uid,
      userName: uname || '',
      // Also send legacy fields for backward compatibility
      ticket_id: targetResourceId,
      user_id: uid,
      user_name: uname || '',
      action: 'editing',
    });
  }, []);

  // ── Action: Stop Editing ───────────────────────────────────────────

  const stopEditing = useCallback((targetResourceId: string) => {
    const uid = userIdRef.current;

    if (!uid) return;

    // Clear active tracking
    if (activeEditingResourceRef.current === targetResourceId) {
      activeEditingResourceRef.current = null;
    }

    // Update local store
    useCollisionStore.getState().userLeft(targetResourceId, uid);

    // Emit to other users via Socket.io
    socketClient.emit('collision:edit:stop', {
      resourceId: targetResourceId,
      userId: uid,
      // Also send legacy fields for backward compatibility
      ticket_id: targetResourceId,
      user_id: uid,
    });
  }, []);

  // ── Auto-Cleanup on Unmount ────────────────────────────────────────

  useEffect(() => {
    return () => {
      const activeResource = activeEditingResourceRef.current;
      const uid = userIdRef.current;

      if (activeResource && uid) {
        // Update local store
        useCollisionStore.getState().userLeft(activeResource, uid);

        // Emit stop to other users
        socketClient.emit('collision:edit:stop', {
          resourceId: activeResource,
          userId: uid,
          ticket_id: activeResource,
          user_id: uid,
        });

        activeEditingResourceRef.current = null;
      }
    };
  }, []);

  return {
    activeEditors,
    hasCollision,
    startEditing,
    stopEditing,
  };
}

export default useCollisionDetection;
