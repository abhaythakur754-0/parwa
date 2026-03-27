/**
 * PARWA Offline Indicator Component
 *
 * Displays the current network status and pending sync count.
 * Provides visual feedback for offline/online state.
 *
 * @module components/OfflineIndicator
 */

"use client";

import { useOffline } from "../hooks/pwa/useOffline";

/**
 * Offline Indicator Props
 */
export interface OfflineIndicatorProps {
  /** Custom class name */
  className?: string;
  /** Show pending sync count */
  showPendingCount?: boolean;
  /** Variant style */
  variant?: "banner" | "badge" | "toast";
  /** Show detailed connection info */
  showDetails?: boolean;
}

/**
 * Offline Indicator Component
 *
 * Shows the current network status with visual styling.
 *
 * @example
 * ```tsx
 * function Layout() {
 *   return (
 *     <>
 *       <OfflineIndicator variant="banner" showPendingCount />
 *       <main>...</main>
 *     </>
 *   );
 * }
 * ```
 */
export function OfflineIndicator({
  className = "",
  showPendingCount = true,
  variant = "banner",
  showDetails = false,
}: OfflineIndicatorProps): JSX.Element | null {
  const { networkStatus, syncQueueStatus } = useOffline();

  // Don't render if online and no pending items
  if (networkStatus.isOnline && (!showPendingCount || syncQueueStatus.pendingCount === 0)) {
    return null;
  }

  /**
   * Render as a banner (full-width bar).
   */
  if (variant === "banner") {
    return (
      <div
        className={`
          w-full px-4 py-2 text-center text-sm font-medium
          ${networkStatus.isOffline
            ? "bg-yellow-500 text-yellow-900"
            : syncQueueStatus.pendingCount > 0
            ? "bg-blue-500 text-white"
            : "bg-green-500 text-white"
          }
          ${className}
        `}
        role="status"
        aria-live="polite"
      >
        {networkStatus.isOffline ? (
          <div className="flex items-center justify-center gap-2">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
              />
            </svg>
            <span>You are currently offline</span>
            {showPendingCount && syncQueueStatus.pendingCount > 0 && (
              <span className="ml-2 px-2 py-0.5 bg-yellow-600 text-yellow-100 rounded-full text-xs">
                {syncQueueStatus.pendingCount} pending
              </span>
            )}
          </div>
        ) : syncQueueStatus.pendingCount > 0 ? (
          <div className="flex items-center justify-center gap-2">
            <svg
              className="w-4 h-4 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
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
            <span>Syncing {syncQueueStatus.pendingCount} item(s)...</span>
          </div>
        ) : null}

        {showDetails && (
          <div className="text-xs opacity-75 mt-1">
            Connection: {networkStatus.effectiveType}
            {networkStatus.downlink && ` (${networkStatus.downlink} Mbps)`}
          </div>
        )}
      </div>
    );
  }

  /**
   * Render as a badge (small pill).
   */
  if (variant === "badge") {
    return (
      <div
        className={`
          inline-flex items-center gap-1.5 px-2.5 py-1
          text-xs font-medium rounded-full
          ${networkStatus.isOffline
            ? "bg-yellow-100 text-yellow-800"
            : "bg-green-100 text-green-800"
          }
          ${className}
        `}
        role="status"
        aria-live="polite"
      >
        <span
          className={`
            w-2 h-2 rounded-full
            ${networkStatus.isOffline ? "bg-yellow-500 animate-pulse" : "bg-green-500"}
          `}
        />
        <span>{networkStatus.isOffline ? "Offline" : "Online"}</span>
        {showPendingCount && syncQueueStatus.pendingCount > 0 && (
          <span className="ml-1 px-1.5 py-0.5 bg-gray-200 text-gray-700 rounded-full">
            {syncQueueStatus.pendingCount}
          </span>
        )}
      </div>
    );
  }

  /**
   * Render as a toast (floating notification).
   */
  if (variant === "toast") {
    return (
      <div
        className={`
          fixed bottom-4 right-4 z-50
          px-4 py-3 rounded-lg shadow-lg
          flex items-center gap-3
          ${networkStatus.isOffline
            ? "bg-yellow-500 text-yellow-900"
            : "bg-green-500 text-white"
          }
          ${className}
        `}
        role="alert"
        aria-live="assertive"
      >
        {networkStatus.isOffline ? (
          <>
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414"
              />
            </svg>
            <div>
              <p className="font-medium">You're offline</p>
              {showPendingCount && syncQueueStatus.pendingCount > 0 && (
                <p className="text-sm opacity-80">
                  {syncQueueStatus.pendingCount} actions will sync when connected
                </p>
              )}
            </div>
          </>
        ) : (
          <>
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0"
              />
            </svg>
            <div>
              <p className="font-medium">Back online</p>
              {showPendingCount && syncQueueStatus.pendingCount > 0 && (
                <p className="text-sm opacity-80">Syncing pending items...</p>
              )}
            </div>
          </>
        )}
      </div>
    );
  }

  return null;
}

/**
 * Network Status Badge (Compact)
 *
 * Shows only a dot indicating network status.
 */
export function NetworkStatusDot({
  className = "",
}: {
  className?: string;
}): JSX.Element {
  const { networkStatus } = useOffline();

  return (
    <div
      className={`
        relative inline-flex items-center
        ${className}
      `}
      title={networkStatus.isOffline ? "Offline" : "Online"}
    >
      <span
        className={`
          w-2.5 h-2.5 rounded-full
          ${networkStatus.isOffline
            ? "bg-yellow-500 animate-pulse"
            : "bg-green-500"
          }
        `}
      />
      {networkStatus.isOffline && (
        <span className="absolute -top-1 -right-1 w-2 h-2 bg-yellow-500 rounded-full animate-ping opacity-75" />
      )}
    </div>
  );
}

/**
 * Connection Quality Indicator
 *
 * Shows connection quality (speed) when available.
 */
export function ConnectionQuality({
  className = "",
}: {
  className?: string;
}): JSX.Element | null {
  const { networkStatus } = useOffline();

  if (!networkStatus.downlink || networkStatus.isOffline) {
    return null;
  }

  const quality =
    networkStatus.downlink > 10
      ? "excellent"
      : networkStatus.downlink > 5
      ? "good"
      : networkStatus.downlink > 1
      ? "fair"
      : "poor";

  const bars =
    quality === "excellent"
      ? 4
      : quality === "good"
      ? 3
      : quality === "fair"
      ? 2
      : 1;

  const color =
    quality === "excellent" || quality === "good"
      ? "bg-green-500"
      : quality === "fair"
      ? "bg-yellow-500"
      : "bg-red-500";

  return (
    <div
      className={`inline-flex items-center gap-1 ${className}`}
      title={`${quality} connection (${networkStatus.downlink} Mbps)`}
    >
      {[1, 2, 3, 4].map((level) => (
        <span
          key={level}
          className={`
            w-1 rounded-sm
            ${level <= bars ? color : "bg-gray-300"}
            ${level === 1 ? "h-1" : level === 2 ? "h-2" : level === 3 ? "h-3" : "h-4"}
          `}
        />
      ))}
    </div>
  );
}

export default OfflineIndicator;
