/**
 * PARWA Update Notification Component
 *
 * Displays a notification when a new version is available.
 * Allows users to update the app.
 *
 * @module components/UpdateNotification
 */

"use client";

import { useState, useEffect } from "react";
import { usePWA } from "../hooks/pwa/usePWA";

/**
 * Update Notification Props
 */
export interface UpdateNotificationProps {
  /** Custom class name */
  className?: string;
  /** Position of the notification */
  position?: "top" | "bottom";
  /** Auto-update countdown in seconds (0 = disabled) */
  autoUpdateDelay?: number;
  /** Custom message */
  message?: string;
  /** Callback when update is applied */
  onUpdate?: () => void;
  /** Callback when notification is dismissed */
  onDismiss?: () => void;
}

/**
 * Update Notification Component
 *
 * Shows a banner when a new version is available.
 *
 * @example
 * ```tsx
 * function Layout() {
 *   return (
 *     <>
 *       <UpdateNotification position="bottom" autoUpdateDelay={10} />
 *       <main>...</main>
 *     </>
 *   );
 * }
 * ```
 */
export function UpdateNotification({
  className = "",
  position = "bottom",
  autoUpdateDelay = 0,
  message = "A new version of PARWA is available!",
  onUpdate,
  onDismiss,
}: UpdateNotificationProps): JSX.Element | null {
  const { updateState, applyUpdate } = usePWA();
  const [isVisible, setIsVisible] = useState(false);
  const [countdown, setCountdown] = useState(autoUpdateDelay);
  const [isDismissed, setIsDismissed] = useState(false);

  /**
   * Show notification when update is available.
   */
  useEffect(() => {
    if (updateState.hasUpdate && !isDismissed) {
      setIsVisible(true);
    }
  }, [updateState.hasUpdate, isDismissed]);

  /**
   * Auto-update countdown.
   */
  useEffect(() => {
    if (!isVisible || autoUpdateDelay === 0 || countdown <= 0) return;

    const timer = setTimeout(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);

    if (countdown === 1) {
      handleUpdate();
    }

    return () => clearTimeout(timer);
  }, [isVisible, autoUpdateDelay, countdown]);

  /**
   * Handle update button click.
   */
  const handleUpdate = () => {
    applyUpdate();
    setIsVisible(false);
    onUpdate?.();
  };

  /**
   * Handle dismiss button click.
   */
  const handleDismiss = () => {
    setIsVisible(false);
    setIsDismissed(true);
    onDismiss?.();
  };

  // Don't render if not visible
  if (!isVisible) {
    return null;
  }

  const positionClasses =
    position === "top" ? "top-0 border-b" : "bottom-0 border-t";

  return (
    <div
      className={`
        fixed left-0 right-0 z-50
        ${positionClasses}
        bg-gradient-to-r from-blue-600 to-indigo-600
        text-white shadow-lg
        ${className}
      `}
      role="alert"
      aria-live="assertive"
    >
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          {/* Icon */}
          <div className="hidden sm:flex items-center justify-center w-10 h-10 bg-white/20 rounded-lg">
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
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <p className="font-medium">{message}</p>
            {autoUpdateDelay > 0 && countdown > 0 && (
              <p className="text-sm text-white/80">
                Updating in {countdown} second{countdown !== 1 ? "s" : ""}...
              </p>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleDismiss}
              className="px-3 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors"
              aria-label="Dismiss update notification"
            >
              Later
            </button>
            <button
              onClick={handleUpdate}
              disabled={updateState.isUpdating}
              className={`
                px-4 py-2 bg-white text-blue-600
                font-semibold rounded-lg
                hover:bg-white/90
                transition-all duration-200
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center gap-2
              `}
            >
              {updateState.isUpdating ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4"
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
                  Updating...
                </>
              ) : (
                <>
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
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  Update Now
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Update Badge Component
 *
 * Shows a small badge when update is available.
 */
export function UpdateBadge({
  className = "",
  onClick,
}: {
  className?: string;
  onClick?: () => void;
}): JSX.Element | null {
  const { updateState, applyUpdate } = usePWA();

  if (!updateState.hasUpdate) {
    return null;
  }

  const handleClick = () => {
    applyUpdate();
    onClick?.();
  };

  return (
    <button
      onClick={handleClick}
      disabled={updateState.isUpdating}
      className={`
        inline-flex items-center gap-1.5
        px-2.5 py-1
        bg-blue-600 text-white
        text-xs font-medium
        rounded-full
        hover:bg-blue-700
        transition-colors
        disabled:opacity-50
        ${className}
      `}
      title="Update available - Click to update"
    >
      {updateState.isUpdating ? (
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
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      )}
      <span>{updateState.isUpdating ? "Updating..." : "Update"}</span>
    </button>
  );
}

/**
 * Version Display Component
 *
 * Shows the current app version.
 */
export function VersionDisplay({
  className = "",
  showLabel = true,
}: {
  className?: string;
  showLabel?: boolean;
}): JSX.Element {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "2.0.0";

  return (
    <div className={`text-xs text-gray-500 ${className}`}>
      {showLabel && <span>PARWA v</span>}
      <span>{version}</span>
    </div>
  );
}

export default UpdateNotification;
