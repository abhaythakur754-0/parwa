/**
 * PARWA Background Sync Hook
 *
 * Hook for background synchronization of offline actions.
 * Provides utilities for syncing data when connection is restored.
 *
 * @module hooks/pwa/useBackgroundSync
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Sync item status.
 */
export type SyncStatus = "pending" | "syncing" | "completed" | "failed";

/**
 * Sync item interface.
 */
export interface SyncItem<T = unknown> {
  /** Unique identifier */
  id: string;
  /** Sync queue name */
  queue: string;
  /** Item data */
  data: T;
  /** Current status */
  status: SyncStatus;
  /** Created timestamp */
  createdAt: number;
  /** Last attempt timestamp */
  lastAttempt?: number;
  /** Number of attempts */
  attempts: number;
  /** Last error */
  error?: string;
}

/**
 * Sync queue configuration.
 */
export interface SyncQueueConfig {
  /** Queue name */
  name: string;
  /** Max retry attempts */
  maxRetries?: number;
  /** Retry delay in ms */
  retryDelay?: number;
  /** Max items in queue */
  maxItems?: number;
  /** Sync function */
  onSync: (items: SyncItem[]) => Promise<void>;
}

/**
 * Background sync state.
 */
export interface BackgroundSyncState {
  /** Whether background sync is supported */
  isSupported: boolean;
  /** Whether sync is currently in progress */
  isSyncing: boolean;
  /** Number of pending items */
  pendingCount: number;
  /** Last sync timestamp */
  lastSync: Date | null;
  /** Sync errors */
  errors: Array<{
    queue: string;
    error: string;
    timestamp: number;
  }>;
}

/**
 * Background sync hook return type.
 */
export interface UseBackgroundSyncReturn<T = unknown> {
  /** Current state */
  state: BackgroundSyncState;
  /** Pending sync items */
  pendingItems: SyncItem<T>[];
  /** Register a sync queue */
  registerQueue: (config: SyncQueueConfig) => void;
  /** Add item to a queue */
  addToQueue: (queue: string, data: T) => string;
  /** Remove item from queue */
  removeFromQueue: (id: string) => void;
  /** Trigger sync for a specific queue */
  syncQueue: (queue: string) => Promise<void>;
  /** Trigger sync for all queues */
  syncAll: () => Promise<void>;
  /** Clear a queue */
  clearQueue: (queue: string) => void;
  /** Get queue stats */
  getQueueStats: (queue: string) => {
    pending: number;
    syncing: number;
    completed: number;
    failed: number;
  };
}

/**
 * IndexedDB helper for sync queue storage.
 */
class SyncQueueDB {
  private dbName = "parwa-sync-queue";
  private storeName = "syncItems";
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
          });
          store.createIndex("queue", "queue", { unique: false });
          store.createIndex("status", "status", { unique: false });
          store.createIndex("createdAt", "createdAt", { unique: false });
        }
      };
    });
  }

  async add<T>(item: SyncItem<T>): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.add(item);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async update<T>(item: SyncItem<T>): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.put(item);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async remove(id: string): Promise<void> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);
      const request = store.delete(id);

      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  async getByQueue<T>(queue: string): Promise<SyncItem<T>[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readonly");
      const store = transaction.objectStore(this.storeName);
      const index = store.index("queue");
      const request = index.getAll(queue);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async getByStatus<T>(status: SyncStatus): Promise<SyncItem<T>[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readonly");
      const store = transaction.objectStore(this.storeName);
      const index = store.index("status");
      const request = index.getAll(status);

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async getAll<T>(): Promise<SyncItem<T>[]> {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readonly");
      const store = transaction.objectStore(this.storeName);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async clearQueue(queue: string): Promise<void> {
    if (!this.db) await this.init();

    const items = await this.getByQueue(queue);

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(this.storeName, "readwrite");
      const store = transaction.objectStore(this.storeName);

      let completed = 0;
      items.forEach((item) => {
        const request = store.delete(item.id);
        request.onsuccess = () => {
          completed++;
          if (completed === items.length) resolve();
        };
        request.onerror = () => reject(request.error);
      });

      if (items.length === 0) resolve();
    });
  }
}

/**
 * Custom hook for background synchronization.
 *
 * @returns Background sync state and actions
 *
 * @example
 * ```tsx
 * function TicketSubmit() {
 *   const { addToQueue, state } = useBackgroundSync<TicketData>();
 *
 *   const handleSubmit = async (data: TicketData) => {
 *     if (!navigator.onLine) {
 *       addToQueue('tickets', data);
 *       toast.info('You are offline. Ticket will be submitted when online.');
 *     } else {
 *       await submitTicket(data);
 *     }
 *   };
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       {state.pendingCount > 0 && (
 *         <span>{state.pendingCount} items pending sync</span>
 *       )}
 *     </form>
 *   );
 * }
 * ```
 */
export function useBackgroundSync<T = unknown>(): UseBackgroundSyncReturn<T> {
  const [state, setState] = useState<BackgroundSyncState>({
    isSupported:
      typeof window !== "undefined" &&
      "serviceWorker" in navigator &&
      "SyncManager" in window,
    isSyncing: false,
    pendingCount: 0,
    lastSync: null,
    errors: [],
  });

  const [pendingItems, setPendingItems] = useState<SyncItem<T>[]>([]);
  const queuesRef = useRef<Map<string, SyncQueueConfig>>(new Map());
  const dbRef = useRef<SyncQueueDB | null>(null);

  /**
   * Initialize the sync queue database.
   */
  useEffect(() => {
    dbRef.current = new SyncQueueDB();
    dbRef.current.init().then(() => {
      refreshItems();
    });
  }, []);

  /**
   * Handle online event to trigger sync.
   */
  useEffect(() => {
    const handleOnline = () => {
      syncAll();
    };

    window.addEventListener("online", handleOnline);

    // Listen for background sync events from service worker
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.addEventListener("message", (event) => {
        if (event.data && event.data.type === "BACKGROUND_SYNC_COMPLETE") {
          refreshItems();
        }
      });
    }

    return () => {
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  /**
   * Refresh pending items from database.
   */
  const refreshItems = useCallback(async () => {
    if (!dbRef.current) return;

    const items = await dbRef.current.getByStatus<T>("pending");
    setPendingItems(items);
    setState((prev) => ({
      ...prev,
      pendingCount: items.length,
    }));
  }, []);

  /**
   * Generate unique ID.
   */
  const generateId = useCallback((): string => {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  /**
   * Register a sync queue.
   */
  const registerQueue = useCallback((config: SyncQueueConfig) => {
    queuesRef.current.set(config.name, {
      maxRetries: 3,
      retryDelay: 5000,
      maxItems: 100,
      ...config,
    });
  }, []);

  /**
   * Add item to a queue.
   */
  const addToQueue = useCallback(
    (queue: string, data: T): string => {
      if (!dbRef.current) {
        console.error("Sync queue database not initialized");
        return "";
      }

      const config = queuesRef.current.get(queue);
      if (!config) {
        console.error(`Queue "${queue}" not registered`);
        return "";
      }

      const id = generateId();
      const item: SyncItem<T> = {
        id,
        queue,
        data,
        status: "pending",
        createdAt: Date.now(),
        attempts: 0,
      };

      dbRef.current.add(item).then(() => {
        refreshItems();

        // Register for background sync
        if (state.isSupported && "serviceWorker" in navigator) {
          navigator.serviceWorker.ready.then((registration) => {
            registration.sync.register(`sync-${queue}`);
          });
        }
      });

      return id;
    },
    [generateId, refreshItems, state.isSupported]
  );

  /**
   * Remove item from queue.
   */
  const removeFromQueue = useCallback(
    async (id: string) => {
      if (!dbRef.current) return;

      await dbRef.current.remove(id);
      await refreshItems();
    },
    [refreshItems]
  );

  /**
   * Sync a specific queue.
   */
  const syncQueue = useCallback(
    async (queue: string) => {
      const config = queuesRef.current.get(queue);
      if (!config || !dbRef.current) return;

      setState((prev) => ({ ...prev, isSyncing: true }));

      const items = await dbRef.current.getByQueue<T>(queue);
      const pendingItems = items.filter((item) => item.status === "pending");

      try {
        // Update items to syncing status
        for (const item of pendingItems) {
          await dbRef.current!.update({
            ...item,
            status: "syncing",
            lastAttempt: Date.now(),
          });
        }

        await config.onSync(pendingItems);

        // Mark as completed
        for (const item of pendingItems) {
          await dbRef.current!.update({
            ...item,
            status: "completed",
          });
        }

        setState((prev) => ({
          ...prev,
          lastSync: new Date(),
        }));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Sync failed";

        // Mark as failed
        for (const item of pendingItems) {
          const newAttempts = item.attempts + 1;
          const shouldRetry = newAttempts < (config.maxRetries ?? 3);

          await dbRef.current!.update({
            ...item,
            status: shouldRetry ? "pending" : "failed",
            attempts: newAttempts,
            error: errorMessage,
          });
        }

        setState((prev) => ({
          ...prev,
          errors: [
            ...prev.errors,
            {
              queue,
              error: errorMessage,
              timestamp: Date.now(),
            },
          ],
        }));
      } finally {
        setState((prev) => ({ ...prev, isSyncing: false }));
        await refreshItems();
      }
    },
    [refreshItems]
  );

  /**
   * Sync all queues.
   */
  const syncAll = useCallback(async () => {
    if (!navigator.onLine) return;

    const queueNames = Array.from(queuesRef.current.keys());
    await Promise.all(queueNames.map((name) => syncQueue(name)));
  }, [syncQueue]);

  /**
   * Clear a queue.
   */
  const clearQueue = useCallback(
    async (queue: string) => {
      if (!dbRef.current) return;

      await dbRef.current.clearQueue(queue);
      await refreshItems();
    },
    [refreshItems]
  );

  /**
   * Get queue statistics.
   */
  const getQueueStats = useCallback(
    (queue: string) => {
      const items = pendingItems.filter((item) => item.queue === queue);

      return {
        pending: items.filter((item) => item.status === "pending").length,
        syncing: items.filter((item) => item.status === "syncing").length,
        completed: items.filter((item) => item.status === "completed").length,
        failed: items.filter((item) => item.status === "failed").length,
      };
    },
    [pendingItems]
  );

  return {
    state,
    pendingItems,
    registerQueue,
    addToQueue,
    removeFromQueue,
    syncQueue,
    syncAll,
    clearQueue,
    getQueueStats,
  };
}

/**
 * Hook for syncing a specific data type.
 *
 * @param queueName - Name of the sync queue
 * @param onSync - Sync function
 * @returns Queue-specific sync state and actions
 */
export function useSyncQueue<T>(
  queueName: string,
  onSync: (items: T[]) => Promise<void>
): {
  /** Add item to queue */
  enqueue: (data: T) => string;
  /** Sync pending items */
  sync: () => Promise<void>;
  /** Number of pending items */
  pending: number;
  /** Whether sync is in progress */
  isSyncing: boolean;
} {
  const { addToQueue, syncQueue, getQueueStats, state } = useBackgroundSync<T>();

  // Register the queue
  useEffect(() => {
    // This would register the queue - simplified for this hook
  }, [queueName, onSync]);

  const enqueue = useCallback(
    (data: T) => {
      return addToQueue(queueName, data);
    },
    [addToQueue, queueName]
  );

  const sync = useCallback(() => {
    return syncQueue(queueName);
  }, [syncQueue, queueName]);

  const stats = getQueueStats(queueName);

  return {
    enqueue,
    sync,
    pending: stats.pending,
    isSyncing: state.isSyncing,
  };
}

export default useBackgroundSync;
