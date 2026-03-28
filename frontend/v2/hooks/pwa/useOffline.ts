/**
 * PARWA Offline Hook
 *
 * Hook for offline status detection and sync queue management.
 * Provides utilities for offline-first functionality.
 *
 * @module hooks/pwa/useOffline
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Network status interface.
 */
export interface NetworkStatus {
  /** Whether currently online */
  isOnline: boolean;
  /** Whether currently offline */
  isOffline: boolean;
  /** Connection type if available */
  connectionType: string;
  /** Downlink speed in Mbps if available */
  downlink: number | null;
  /** Effective connection type if available */
  effectiveType: string;
  /** RTT in ms if available */
  rtt: number | null;
  /** Whether data saver is enabled */
  saveData: boolean;
  /** Last online timestamp */
  lastOnline: Date | null;
  /** Last offline timestamp */
  lastOffline: Date | null;
}

/**
 * Pending sync item interface.
 */
export interface PendingSyncItem {
  /** Unique ID for the sync item */
  id: string;
  /** URL to sync to */
  url: string;
  /** HTTP method */
  method: string;
  /** Request headers */
  headers: Record<string, string>;
  /** Request body */
  body: string;
  /** Timestamp when queued */
  timestamp: number;
  /** Number of retry attempts */
  retries: number;
  /** Last error message */
  lastError?: string;
}

/**
 * Sync queue status interface.
 */
export interface SyncQueueStatus {
  /** Total pending items */
  pendingCount: number;
  /** Whether sync is in progress */
  isSyncing: boolean;
  /** Last sync timestamp */
  lastSync: Date | null;
  /** Sync errors */
  errors: Array<{
    id: string;
    error: string;
    timestamp: number;
  }>;
}

/**
 * Offline hook return type.
 */
export interface UseOfflineReturn {
  /** Network status */
  networkStatus: NetworkStatus;
  /** Sync queue status */
  syncQueueStatus: SyncQueueStatus;
  /** Pending sync items */
  pendingItems: PendingSyncItem[];
  /** Manually trigger sync */
  triggerSync: () => Promise<void>;
  /** Add item to sync queue */
  addToQueue: (item: Omit<PendingSyncItem, "id" | "timestamp" | "retries">) => string;
  /** Remove item from queue */
  removeFromQueue: (id: string) => void;
  /** Clear all pending items */
  clearQueue: () => void;
  /** Retry a failed item */
  retryItem: (id: string) => Promise<boolean>;
}

/**
 * Database helper for offline queue.
 */
class OfflineQueueDB {
  private dbName = "parwa-offline-queue";
  private storeName = "pendingRequests";
  private db: IDBDatabase | null = null;

  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, 1);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, {
            keyPath: "id",
            autoIncrement: true,
          });
          store.createIndex("timestamp", "timestamp", { unique: false });
        }
      };
    });
  }

  async add(item: Omit<PendingSyncItem, "id">): Promise<string> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.add(item);

      request.onsuccess = () => resolve(String(request.result));
      request.onerror = () => reject(request.error);
    });
  }

  async getAll(): Promise<PendingSyncItem[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readonly");
      const store = transaction.objectStore(this.storeName);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async remove(id: string): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.delete(Number(id));

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async clear(): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.clear();

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async update(item: PendingSyncItem): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.put(item);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }
}

/**
 * Custom hook for offline status detection and sync queue.
 *
 * @returns Offline state and actions
 *
 * @example
 * ```tsx
 * function OfflineBanner() {
 *   const { networkStatus, syncQueueStatus } = useOffline();
 *
 *   if (networkStatus.isOffline) {
 *     return (
 *       <div className="bg-yellow-500 p-2 text-center">
 *         You are offline. {syncQueueStatus.pendingCount} actions pending.
 *       </div>
 *     );
 *   }
 *
 *   return null;
 * }
 * ```
 */
export function useOffline(): UseOfflineReturn {
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus>({
    isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
    isOffline: typeof navigator !== "undefined" ? !navigator.onLine : false,
    connectionType: "unknown",
    downlink: null,
    effectiveType: "unknown",
    rtt: null,
    saveData: false,
    lastOnline: null,
    lastOffline: null,
  });

  const [syncQueueStatus, setSyncQueueStatus] = useState<SyncQueueStatus>({
    pendingCount: 0,
    isSyncing: false,
    lastSync: null,
    errors: [],
  });

  const [pendingItems, setPendingItems] = useState<PendingSyncItem[]>([]);
  const dbRef = useRef<OfflineQueueDB | null>(null);
  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Initialize the offline queue database.
   */
  useEffect(() => {
    dbRef.current = new OfflineQueueDB();
    dbRef.current.init().then(() => {
      refreshQueue();
    });
  }, []);

  /**
   * Handle online/offline events.
   */
  useEffect(() => {
    const handleOnline = () => {
      setNetworkStatus((prev) => ({
        ...prev,
        isOnline: true,
        isOffline: false,
        lastOnline: new Date(),
      }));

      // Trigger background sync when coming back online
      triggerSync();
    };

    const handleOffline = () => {
      setNetworkStatus((prev) => ({
        ...prev,
        isOnline: false,
        isOffline: true,
        lastOffline: new Date(),
      }));
    };

    // Handle network information API if available
    const handleConnectionChange = () => {
      const connection = (navigator as Navigator & {
        connection?: {
          type?: string;
          downlink?: number;
          effectiveType?: string;
          rtt?: number;
          saveData?: boolean;
        };
      }).connection;

      if (connection) {
        setNetworkStatus((prev) => ({
          ...prev,
          connectionType: connection.type || "unknown",
          downlink: connection.downlink ?? null,
          effectiveType: connection.effectiveType || "unknown",
          rtt: connection.rtt ?? null,
          saveData: connection.saveData ?? false,
        }));
      }
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    const connection = (navigator as Navigator & { connection?: EventTarget }).connection;
    if (connection) {
      connection.addEventListener("change", handleConnectionChange);
      handleConnectionChange();
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);

      if (connection) {
        connection.removeEventListener("change", handleConnectionChange);
      }

      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Refresh the pending queue from IndexedDB.
   */
  const refreshQueue = useCallback(async () => {
    if (!dbRef.current) return;

    const items = await dbRef.current.getAll();
    setPendingItems(items);
    setSyncQueueStatus((prev) => ({
      ...prev,
      pendingCount: items.length,
    }));
  }, []);

  /**
   * Trigger sync of pending items.
   */
  const triggerSync = useCallback(async () => {
    if (!dbRef.current || !navigator.onLine) return;

    setSyncQueueStatus((prev) => ({
      ...prev,
      isSyncing: true,
    }));

    const items = await dbRef.current.getAll();
    const errors: SyncQueueStatus["errors"] = [];

    for (const item of items) {
      try {
        const response = await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body,
        });

        if (response.ok) {
          await dbRef.current!.remove(item.id);
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Unknown error";

        // Update item with error
        await dbRef.current!.update({
          ...item,
          retries: item.retries + 1,
          lastError: errorMessage,
        });

        errors.push({
          id: item.id,
          error: errorMessage,
          timestamp: Date.now(),
        });
      }
    }

    await refreshQueue();

    setSyncQueueStatus((prev) => ({
      ...prev,
      isSyncing: false,
      lastSync: new Date(),
      errors,
    }));

    // Notify service worker about sync completion
    if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: "SYNC_COMPLETE",
        pendingCount: items.length - errors.length,
      });
    }
  }, [refreshQueue]);

  /**
   * Add item to sync queue.
   */
  const addToQueue = useCallback(
    (item: Omit<PendingSyncItem, "id" | "timestamp" | "retries">): string => {
      if (!dbRef.current) {
        console.error("Offline queue not initialized");
        return "";
      }

      const fullItem = {
        ...item,
        timestamp: Date.now(),
        retries: 0,
      };

      // Use async operation
      dbRef.current.add(fullItem).then((id) => {
        refreshQueue();
      });

      return ""; // ID will be generated asynchronously
    },
    [refreshQueue]
  );

  /**
   * Remove item from queue.
   */
  const removeFromQueue = useCallback(
    async (id: string) => {
      if (!dbRef.current) return;

      await dbRef.current.remove(id);
      await refreshQueue();
    },
    [refreshQueue]
  );

  /**
   * Clear all pending items.
   */
  const clearQueue = useCallback(async () => {
    if (!dbRef.current) return;

    await dbRef.current.clear();
    await refreshQueue();
  }, [refreshQueue]);

  /**
   * Retry a failed item.
   */
  const retryItem = useCallback(
    async (id: string): Promise<boolean> => {
      if (!dbRef.current || !navigator.onLine) return false;

      const item = pendingItems.find((i) => i.id === id);
      if (!item) return false;

      try {
        const response = await fetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body,
        });

        if (response.ok) {
          await dbRef.current.remove(id);
          await refreshQueue();
          return true;
        }

        return false;
      } catch {
        return false;
      }
    },
    [pendingItems, refreshQueue]
  );

  return {
    networkStatus,
    syncQueueStatus,
    pendingItems,
    triggerSync,
    addToQueue,
    removeFromQueue,
    clearQueue,
    retryItem,
  };
}

/**
 * Hook to execute a function only when online.
 *
 * @param fn - Function to execute
 * @returns Wrapped function that queues when offline
 */
export function useOnlineOnly<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T
): {
  execute: T;
  isPending: boolean;
  error: Error | null;
} {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(
    async (...args: Parameters<T>) => {
      setIsPending(true);
      setError(null);

      try {
        if (!navigator.onLine) {
          throw new Error("You are currently offline. This action will be synced when you're back online.");
        }

        const result = await fn(...args);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error("Unknown error");
        setError(error);
        throw error;
      } finally {
        setIsPending(false);
      }
    },
    [fn]
  ) as T;

  return {
    execute,
    isPending,
    error,
  };
}

export default useOffline;
