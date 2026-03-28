/**
 * PARWA PWA Hooks Index
 *
 * Export all PWA hooks for the PARWA v2 frontend.
 */

// PWA Installation & Updates
export {
  usePWA,
  useIsPWA,
  useDisplayMode,
  // Types
  type PWAInstallState,
  type PWAUpdateState,
  type UsePWAReturn,
} from "./usePWA";

// Offline Detection & Sync
export {
  useOffline,
  useOnlineOnly,
  // Types
  type NetworkStatus,
  type PendingSyncItem,
  type SyncQueueStatus,
  type UseOfflineReturn,
} from "./useOffline";

// Push Notifications
export {
  useNotifications,
  useNotificationClick,
  usePushSubscription,
  // Types
  type NotificationPermissionState,
  type NotificationOptions,
  type NotificationState,
  type UseNotificationsReturn,
} from "./useNotifications";

// Background Sync
export {
  useBackgroundSync,
  useSyncQueue,
  // Types
  type SyncStatus,
  type SyncItem,
  type SyncQueueConfig,
  type BackgroundSyncState,
  type UseBackgroundSyncReturn,
} from "./useBackgroundSync";
