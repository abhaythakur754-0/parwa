/**
 * PARWA Notifications Hook
 *
 * Hook for push notification permission and handling.
 * Provides utilities for web push notifications.
 *
 * @module hooks/pwa/useNotifications
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";

/**
 * Notification permission state.
 */
export type NotificationPermissionState = "default" | "granted" | "denied";

/**
 * Notification options interface.
 */
export interface NotificationOptions {
  /** Notification title */
  title: string;
  /** Notification body text */
  body?: string;
  /** Icon URL */
  icon?: string;
  /** Badge URL */
  badge?: string;
  /** Image URL */
  image?: string;
  /** Tag for grouping */
  tag?: string;
  /** Whether to require interaction */
  requireInteraction?: boolean;
  /** Whether to silence */
  silent?: boolean;
  /** Vibration pattern */
  vibrate?: number[];
  /** Actions */
  actions?: Array<{
    action: string;
    title: string;
    icon?: string;
  }>;
  /** Data to attach */
  data?: Record<string, unknown>;
  /** Timestamp */
  timestamp?: number;
}

/**
 * Notification state interface.
 */
export interface NotificationState {
  /** Whether notifications are supported */
  isSupported: boolean;
  /** Current permission state */
  permission: NotificationPermissionState;
  /** Whether notifications are enabled */
  isEnabled: boolean;
  /** Whether service worker is ready */
  isServiceWorkerReady: boolean;
}

/**
 * Notification hook return type.
 */
export interface UseNotificationsReturn {
  /** Notification state */
  state: NotificationState;
  /** Request notification permission */
  requestPermission: () => Promise<NotificationPermissionState>;
  /** Show a notification */
  showNotification: (options: NotificationOptions) => Promise<void>;
  /** Show a local notification (without service worker) */
  showLocalNotification: (options: NotificationOptions) => Promise<Notification | null>;
  /** Close a notification by tag */
  closeNotification: (tag: string) => void;
  /** Get all notifications */
  getNotifications: () => Promise<Notification[]>;
}

/**
 * Custom hook for push notification management.
 *
 * @returns Notification state and actions
 *
 * @example
 * ```tsx
 * function NotificationButton() {
 *   const {
 *     state,
 *     requestPermission,
 *     showNotification
 *   } = useNotifications();
 *
 *   if (!state.isSupported) {
 *     return <span>Notifications not supported</span>;
 *   }
 *
 *   if (state.permission === 'denied') {
 *     return <span>Notifications blocked</span>;
 *   }
 *
 *   return (
 *     <button onClick={async () => {
 *       if (state.permission !== 'granted') {
 *         await requestPermission();
 *       }
 *       await showNotification({
 *         title: 'Hello!',
 *         body: 'This is a test notification'
 *       });
 *     }}>
 *       {state.permission === 'granted' ? 'Notify Me' : 'Enable Notifications'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useNotifications(): UseNotificationsReturn {
  const [state, setState] = useState<NotificationState>({
    isSupported: typeof window !== "undefined" && "Notification" in window,
    permission: "default",
    isEnabled: false,
    isServiceWorkerReady: false,
  });

  const registrationRef = useRef<ServiceWorkerRegistration | null>(null);

  /**
   * Initialize notification state.
   */
  useEffect(() => {
    if (!state.isSupported) return;

    // Check current permission
    const permission = Notification.permission as NotificationPermissionState;
    setState((prev) => ({
      ...prev,
      permission,
      isEnabled: permission === "granted",
    }));

    // Get service worker registration
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        registrationRef.current = registration;
        setState((prev) => ({
          ...prev,
          isServiceWorkerReady: true,
        }));
      });
    }

    // Listen for permission changes
    const checkPermission = () => {
      const newPermission = Notification.permission as NotificationPermissionState;
      setState((prev) => ({
        ...prev,
        permission: newPermission,
        isEnabled: newPermission === "granted",
      }));
    };

    // Periodically check permission (workaround for no permission change event)
    const interval = setInterval(checkPermission, 1000);

    return () => clearInterval(interval);
  }, [state.isSupported]);

  /**
   * Request notification permission.
   */
  const requestPermission = useCallback(async (): Promise<NotificationPermissionState> => {
    if (!state.isSupported) {
      console.warn("Notifications are not supported");
      return "denied";
    }

    try {
      const permission = await Notification.requestPermission();
      const permissionState = permission as NotificationPermissionState;

      setState((prev) => ({
        ...prev,
        permission: permissionState,
        isEnabled: permissionState === "granted",
      }));

      return permissionState;
    } catch (error) {
      console.error("Failed to request notification permission:", error);
      return "denied";
    }
  }, [state.isSupported]);

  /**
   * Show a notification via service worker.
   */
  const showNotification = useCallback(async (options: NotificationOptions): Promise<void> => {
    if (!state.isEnabled) {
      throw new Error("Notifications are not enabled");
    }

    if (!registrationRef.current) {
      throw new Error("Service worker is not ready");
    }

    try {
      await registrationRef.current.showNotification(options.title, {
        body: options.body,
        icon: options.icon || "/icons/icon-192x192.png",
        badge: options.badge || "/icons/badge-72x72.png",
        image: options.image,
        tag: options.tag,
        requireInteraction: options.requireInteraction,
        silent: options.silent,
        vibrate: options.vibrate || [100, 50, 100],
        actions: options.actions,
        data: options.data,
        timestamp: options.timestamp || Date.now(),
      });
    } catch (error) {
      console.error("Failed to show notification:", error);
      throw error;
    }
  }, [state.isEnabled]);

  /**
   * Show a local notification (without service worker).
   */
  const showLocalNotification = useCallback(
    async (options: NotificationOptions): Promise<Notification | null> => {
      if (!state.isEnabled) {
        console.warn("Notifications are not enabled");
        return null;
      }

      try {
        const notification = new Notification(options.title, {
          body: options.body,
          icon: options.icon || "/icons/icon-192x192.png",
          image: options.image,
          tag: options.tag,
          requireInteraction: options.requireInteraction,
          silent: options.silent,
          data: options.data,
        });

        return notification;
      } catch (error) {
        console.error("Failed to show local notification:", error);
        return null;
      }
    },
    [state.isEnabled]
  );

  /**
   * Close a notification by tag.
   */
  const closeNotification = useCallback(async (tag: string) => {
    if (!registrationRef.current) return;

    const notifications = await registrationRef.current.getNotifications({ tag });
    notifications.forEach((notification) => notification.close());
  }, []);

  /**
   * Get all notifications.
   */
  const getNotifications = useCallback(async (): Promise<Notification[]> => {
    if (!registrationRef.current) return [];

    try {
      const notifications = await registrationRef.current.getNotifications();
      return Array.from(notifications);
    } catch {
      return [];
    }
  }, []);

  return {
    state,
    requestPermission,
    showNotification,
    showLocalNotification,
    closeNotification,
    getNotifications,
  };
}

/**
 * Hook to handle notification click events.
 *
 * @param onNotificationClick - Callback when notification is clicked
 */
export function useNotificationClick(
  onNotificationClick: (data: Record<string, unknown>, action?: string) => void
): void {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    const handleMessage = (event: MessageEvent) => {
      if (event.data && event.data.type === "NOTIFICATION_CLICK") {
        onNotificationClick(event.data.data, event.data.action);
      }
    };

    navigator.serviceWorker.addEventListener("message", handleMessage);

    return () => {
      navigator.serviceWorker.removeEventListener("message", handleMessage);
    };
  }, [onNotificationClick]);
}

/**
 * Hook to subscribe to push notifications.
 *
 * @returns Subscription state and methods
 */
export function usePushSubscription() {
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    navigator.serviceWorker.ready.then(async (registration) => {
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        setSubscription(existing);
        setIsSubscribed(true);
      }
    });
  }, []);

  const subscribe = useCallback(
    async (vapidPublicKey: string): Promise<PushSubscription | null> => {
      if (!("serviceWorker" in navigator)) return null;

      try {
        const registration = await navigator.serviceWorker.ready;
        const newSubscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
        });

        setSubscription(newSubscription);
        setIsSubscribed(true);

        return newSubscription;
      } catch (error) {
        console.error("Failed to subscribe to push:", error);
        return null;
      }
    },
    []
  );

  const unsubscribe = useCallback(async (): Promise<boolean> => {
    if (!subscription) return false;

    try {
      await subscription.unsubscribe();
      setSubscription(null);
      setIsSubscribed(false);
      return true;
    } catch (error) {
      console.error("Failed to unsubscribe from push:", error);
      return false;
    }
  }, [subscription]);

  return {
    subscription,
    isSubscribed,
    subscribe,
    unsubscribe,
  };
}

/**
 * Convert VAPID public key to Uint8Array.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export default useNotifications;
