/**
 * PARWA Sync Status Component
 *
 * Displays the background sync status and pending items.
 * Provides visual feedback for data synchronization.
 *
 * @module components/SyncStatus
 */

"use client";

import { useState } from "react";
import { useOffline, type PendingSyncItem } from "../hooks/pwa/useOffline";

/**
 * Sync Status Props
 */
export interface SyncStatusProps {
  /** Custom class name */
  className?: string;
  /** Maximum items to show in list */
  maxItems?: number;
  /** Show detailed item list */
  showList?: boolean;
  /** Allow manual retry */
  allowRetry?: boolean;
  /** Callback when sync completes */
  onSyncComplete?: () => void;
}

/**
 * Sync Status Component
 *
 * Shows current sync status and pending items.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   return (
 *     <div>
 *       <SyncStatus showList allowRetry />
 *       {/* ... *\/}
 *     </div>
 *   );
 * }
 * ```
 */
export function SyncStatus({
  className = "",
  maxItems = 5,
  showList = false,
  allowRetry = false,
  onSyncComplete,
}: SyncStatusProps): JSX.Element | null {
  const {
    networkStatus,
    syncQueueStatus,
    pendingItems,
    triggerSync,
    removeFromQueue,
    retryItem,
  } = useOffline();

  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if online and no pending items
  if (networkStatus.isOnline && pendingItems.length === 0) {
    return null;
  }

  /**
   * Get icon for sync item type.
   */
  const getItemIcon = (url: string): JSX.Element => {
    if (url.includes("/tickets")) {
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          />
        </svg>
      );
    }
    if (url.includes("/approvals")) {
      return (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      );
    }
    return (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
        />
      </svg>
    );
  };

  /**
   * Format timestamp.
   */
  const formatTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  /**
   * Get method badge color.
   */
  const getMethodColor = (method: string): string => {
    switch (method.toUpperCase()) {
      case "POST":
        return "bg-green-100 text-green-800";
      case "PUT":
      case "PATCH":
        return "bg-yellow-100 text-yellow-800";
      case "DELETE":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const displayedItems = isExpanded ? pendingItems : pendingItems.slice(0, maxItems);

  return (
    <div className={`bg-white rounded-lg shadow-md ${className}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 border-b cursor-pointer"
        onClick={() => showList && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {/* Status indicator */}
          <div
            className={`
              w-3 h-3 rounded-full
              ${networkStatus.isOffline
                ? "bg-yellow-500 animate-pulse"
                : syncQueueStatus.isSyncing
                ? "bg-blue-500 animate-spin"
                : "bg-green-500"
              }
            `}
          />

          <div>
            <h3 className="font-medium text-gray-900">
              {networkStatus.isOffline
                ? "Offline - Actions Queued"
                : syncQueueStatus.isSyncing
                ? "Syncing..."
                : "Sync Complete"}
            </h3>
            <p className="text-sm text-gray-500">
              {pendingItems.length} item{pendingItems.length !== 1 ? "s" : ""} pending
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Sync button */}
          {networkStatus.isOnline && pendingItems.length > 0 && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                triggerSync();
              }}
              disabled={syncQueueStatus.isSyncing}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {syncQueueStatus.isSyncing ? "Syncing..." : "Sync Now"}
            </button>
          )}

          {/* Expand indicator */}
          {showList && pendingItems.length > 0 && (
            <svg
              className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </div>
      </div>

      {/* Item list */}
      {showList && isExpanded && pendingItems.length > 0 && (
        <div className="divide-y max-h-64 overflow-y-auto">
          {displayedItems.map((item) => (
            <SyncItemRow
              key={item.id}
              item={item}
              onRemove={() => removeFromQueue(item.id)}
              onRetry={allowRetry ? () => retryItem(item.id) : undefined}
              getIcon={getItemIcon}
              formatTime={formatTime}
              getMethodColor={getMethodColor}
            />
          ))}

          {pendingItems.length > maxItems && !isExpanded && (
            <div className="p-2 text-center text-sm text-gray-500">
              +{pendingItems.length - maxItems} more items
            </div>
          )}
        </div>
      )}

      {/* Last sync info */}
      {syncQueueStatus.lastSync && (
        <div className="p-3 bg-gray-50 text-xs text-gray-500">
          Last sync: {formatTime(syncQueueStatus.lastSync.getTime())}
        </div>
      )}

      {/* Errors */}
      {syncQueueStatus.errors.length > 0 && (
        <div className="p-3 bg-red-50 border-t border-red-100">
          <p className="text-sm font-medium text-red-800">
            {syncQueueStatus.errors.length} error(s) occurred during sync
          </p>
          <ul className="mt-1 text-xs text-red-600">
            {syncQueueStatus.errors.slice(0, 3).map((error, index) => (
              <li key={index}>{error.error}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Sync Item Row Component
 */
function SyncItemRow({
  item,
  onRemove,
  onRetry,
  getIcon,
  formatTime,
  getMethodColor,
}: {
  item: PendingSyncItem;
  onRemove: () => void;
  onRetry?: () => void;
  getIcon: (url: string) => JSX.Element;
  formatTime: (timestamp: number) => string;
  getMethodColor: (method: string) => string;
}): JSX.Element {
  const [isRemoving, setIsRemoving] = useState(false);

  const handleRemove = async () => {
    setIsRemoving(true);
    await onRemove();
  };

  return (
    <div className="flex items-center gap-3 p-3 hover:bg-gray-50">
      {/* Icon */}
      <div className="flex-shrink-0 w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center text-gray-600">
        {getIcon(item.url)}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${getMethodColor(item.method)}`}>
            {item.method}
          </span>
          <span className="text-sm font-medium text-gray-900 truncate">
            {item.url.split("/").pop() || item.url}
          </span>
        </div>
        <p className="text-xs text-gray-500">
          {formatTime(item.timestamp)}
          {item.retries > 0 && ` • ${item.retries} retries`}
        </p>
        {item.lastError && (
          <p className="text-xs text-red-500 truncate">{item.lastError}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {onRetry && (
          <button
            onClick={onRetry}
            className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
            title="Retry"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>
        )}
        <button
          onClick={handleRemove}
          disabled={isRemoving}
          className="p-1 text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
          title="Remove"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

/**
 * Compact Sync Badge
 *
 * Shows pending count in a small badge.
 */
export function SyncBadge({
  className = "",
  onClick,
}: {
  className?: string;
  onClick?: () => void;
}): JSX.Element | null {
  const { networkStatus, syncQueueStatus } = useOffline();

  if (networkStatus.isOnline && syncQueueStatus.pendingCount === 0) {
    return null;
  }

  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-1.5
        px-2.5 py-1
        ${networkStatus.isOffline ? "bg-yellow-100 text-yellow-800" : "bg-blue-100 text-blue-800"}
        text-xs font-medium
        rounded-full
        hover:opacity-80
        transition-opacity
        ${className}
      `}
    >
      {syncQueueStatus.isSyncing ? (
        <svg className="animate-spin h-3 w-3" fill="none" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      ) : (
        <svg
          className="w-3 h-3"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      )}
      <span>
        {networkStatus.isOffline
          ? "Offline"
          : syncQueueStatus.isSyncing
          ? "Syncing"
          : `${syncQueueStatus.pendingCount} pending`}
      </span>
    </button>
  );
}

export default SyncStatus;
