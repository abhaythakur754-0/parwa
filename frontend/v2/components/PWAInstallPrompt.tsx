/**
 * PARWA PWA Install Prompt Component
 *
 * Displays a banner prompting users to install the PWA.
 * Handles different platforms and install states.
 *
 * @module components/PWAInstallPrompt
 */

"use client";

import { useState, useEffect } from "react";
import { usePWA } from "../hooks/pwa/usePWA";

/**
 * PWA Install Prompt Props
 */
export interface PWAInstallPromptProps {
  /** Custom class name */
  className?: string;
  /** Position of the prompt */
  position?: "top" | "bottom";
  /** Delay before showing the prompt (ms) */
  delay?: number;
  /** Minimum visits before showing */
  minVisits?: number;
  /** Custom title */
  title?: string;
  /** Custom description */
  description?: string;
  /** Callback when prompt is dismissed */
  onDismiss?: () => void;
  /** Callback when installed */
  onInstalled?: () => void;
}

/**
 * PWA Install Prompt Component
 *
 * Shows a banner prompting users to install the PWA.
 * Automatically handles platform detection and install flow.
 *
 * @example
 * ```tsx
 * function Layout() {
 *   return (
 *     <>
 *       <PWAInstallPrompt
 *         position="bottom"
 *         delay={5000}
 *         minVisits={2}
 *       />
 *       <main>...</main>
 *     </>
 *   );
 * }
 * ```
 */
export function PWAInstallPrompt({
  className = "",
  position = "bottom",
  delay = 3000,
  minVisits = 1,
  title = "Install PARWA",
  description = "Install PARWA for a better experience with offline support and faster loading.",
  onDismiss,
  onInstalled,
}: PWAInstallPromptProps): JSX.Element | null {
  const { installState, promptInstall } = usePWA();
  const [isVisible, setIsVisible] = useState(false);
  const [isDismissed, setIsDismissed] = useState(false);

  /**
   * Check visit count and delay before showing prompt.
   */
  useEffect(() => {
    // Don't show if already installed, can't install, or dismissed
    if (installState.isInstalled || !installState.canInstall || isDismissed) {
      return;
    }

    // Check visit count
    const visitCount = parseInt(localStorage.getItem("parwa_visit_count") || "0", 10);
    if (visitCount < minVisits) {
      localStorage.setItem("parwa_visit_count", String(visitCount + 1));
      return;
    }

    // Check if previously dismissed
    const dismissedTime = localStorage.getItem("parwa_install_dismissed");
    if (dismissedTime) {
      const hoursSinceDismissed =
        (Date.now() - parseInt(dismissedTime, 10)) / (1000 * 60 * 60);
      // Don't show again for 24 hours after dismissal
      if (hoursSinceDismissed < 24) {
        return;
      }
    }

    // Delay before showing
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, delay);

    return () => clearTimeout(timer);
  }, [installState.canInstall, installState.isInstalled, isDismissed, delay, minVisits]);

  /**
   * Handle install button click.
   */
  const handleInstall = async () => {
    const installed = await promptInstall();
    if (installed) {
      setIsVisible(false);
      onInstalled?.();
    }
  };

  /**
   * Handle dismiss button click.
   */
  const handleDismiss = () => {
    setIsVisible(false);
    setIsDismissed(true);
    localStorage.setItem("parwa_install_dismissed", String(Date.now()));
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
        bg-gradient-to-r from-indigo-600 to-purple-600
        text-white shadow-lg
        ${className}
      `}
      role="banner"
      aria-label="Install application prompt"
    >
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          {/* Icon */}
          <div className="hidden sm:flex items-center justify-center w-12 h-12 bg-white/20 rounded-xl">
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
              />
            </svg>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-lg truncate">{title}</h3>
            <p className="text-sm text-white/80 truncate">{description}</p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleDismiss}
              className="px-3 py-2 text-sm font-medium text-white/80 hover:text-white transition-colors"
              aria-label="Dismiss install prompt"
            >
              Not now
            </button>
            <button
              onClick={handleInstall}
              disabled={installState.isInstalling}
              className={`
                px-4 py-2 bg-white text-indigo-600
                font-semibold rounded-lg
                hover:bg-white/90
                transition-all duration-200
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center gap-2
              `}
            >
              {installState.isInstalling ? (
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
                  Installing...
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
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  Install
                </>
              )}
            </button>
          </div>

          {/* Close button for mobile */}
          <button
            onClick={handleDismiss}
            className="sm:hidden p-2 text-white/80 hover:text-white"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    </div>
  );
}

/**
 * Compact PWA Install Button
 *
 * A smaller button for navigation bars or menus.
 */
export function PWAInstallButton({
  className = "",
}: {
  className?: string;
}): JSX.Element | null {
  const { installState, promptInstall } = usePWA();

  if (installState.isInstalled || !installState.canInstall) {
    return null;
  }

  return (
    <button
      onClick={promptInstall}
      disabled={installState.isInstalling}
      className={`
        inline-flex items-center gap-2
        px-3 py-2
        bg-indigo-600 text-white
        text-sm font-medium
        rounded-lg
        hover:bg-indigo-700
        transition-colors
        disabled:opacity-50
        ${className}
      `}
      aria-label="Install application"
    >
      {installState.isInstalling ? (
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
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
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
          />
        </svg>
      )}
      <span className="hidden sm:inline">
        {installState.isInstalling ? "Installing..." : "Install App"}
      </span>
    </button>
  );
}

export default PWAInstallPrompt;
