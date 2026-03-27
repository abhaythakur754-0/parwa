/**
 * PARWA PWA Hook
 *
 * Hook for PWA installation prompt and update detection.
 * Provides utilities for Progressive Web App features.
 *
 * @module hooks/pwa/usePWA
 */

"use client";

import { useState, useEffect, useCallback } from "react";

/**
 * BeforeInstallPromptEvent type extension.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
}

/**
 * PWA installation state.
 */
export interface PWAInstallState {
  /** Whether the app can be installed */
  canInstall: boolean;
  /** Whether the app is currently installed */
  isInstalled: boolean;
  /** Whether installation is in progress */
  isInstalling: boolean;
  /** Installation error */
  error: Error | null;
  /** Platform detected for installation */
  platform: string;
}

/**
 * PWA update state.
 */
export interface PWAUpdateState {
  /** Whether an update is available */
  hasUpdate: boolean;
  /** Whether update is being applied */
  isUpdating: boolean;
  /** The waiting service worker */
  waitingWorker: ServiceWorker | null;
  /** Registration object */
  registration: ServiceWorkerRegistration | null;
}

/**
 * PWA hook return type.
 */
export interface UsePWAReturn {
  /** Installation state */
  installState: PWAInstallState;
  /** Update state */
  updateState: PWAUpdateState;
  /** Prompt user to install the app */
  promptInstall: () => Promise<boolean>;
  /** Apply the available update */
  applyUpdate: () => void;
  /** Check for updates manually */
  checkForUpdate: () => Promise<boolean>;
  /** Dismiss the install prompt */
  dismissInstall: () => void;
}

/**
 * Custom hook for PWA installation and update management.
 *
 * @returns PWA state and actions
 *
 * @example
 * ```tsx
 * function PWAInstallBanner() {
 *   const {
 *     installState,
 *     updateState,
 *     promptInstall,
 *     applyUpdate
 *   } = usePWA();
 *
 *   if (installState.canInstall) {
 *     return (
 *       <button onClick={promptInstall}>
 *         Install App
 *       </button>
 *     );
 *   }
 *
 *   if (updateState.hasUpdate) {
 *     return (
 *       <button onClick={applyUpdate}>
 *         Update Available - Click to Update
 *       </button>
 *     );
 *   }
 *
 *   return null;
 * }
 * ```
 */
export function usePWA(): UsePWAReturn {
  const [installPromptEvent, setInstallPromptEvent] = useState<BeforeInstallPromptEvent | null>(null);

  const [installState, setInstallState] = useState<PWAInstallState>({
    canInstall: false,
    isInstalled: false,
    isInstalling: false,
    error: null,
    platform: "unknown",
  });

  const [updateState, setUpdateState] = useState<PWAUpdateState>({
    hasUpdate: false,
    isUpdating: false,
    waitingWorker: null,
    registration: null,
  });

  /**
   * Handle the beforeinstallprompt event.
   */
  useEffect(() => {
    // Check if already installed
    const isInstalled =
      window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone === true;

    setInstallState((prev) => ({
      ...prev,
      isInstalled,
    }));

    // Listen for install prompt
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      const promptEvent = e as BeforeInstallPromptEvent;
      setInstallPromptEvent(promptEvent);
      setInstallState((prev) => ({
        ...prev,
        canInstall: true,
        platform: detectPlatform(),
      }));
    };

    // Listen for app installed event
    const handleAppInstalled = () => {
      setInstallPromptEvent(null);
      setInstallState((prev) => ({
        ...prev,
        canInstall: false,
        isInstalled: true,
        isInstalling: false,
      }));
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, []);

  /**
   * Service worker registration and update detection.
   */
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }

    navigator.serviceWorker.ready.then((registration) => {
      setUpdateState((prev) => ({
        ...prev,
        registration,
      }));

      // Check for updates
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;

        if (newWorker) {
          newWorker.addEventListener("statechange", () => {
            if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
              // New content is available
              setUpdateState((prev) => ({
                ...prev,
                hasUpdate: true,
                waitingWorker: newWorker,
              }));
            }
          });
        }
      });
    });

    // Handle controller change (new SW activated)
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      // Force reload to get the new version
      window.location.reload();
    });

    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener("message", (event) => {
      if (event.data && event.data.type === "SW_UPDATED") {
        setUpdateState((prev) => ({
          ...prev,
          hasUpdate: true,
        }));
      }
    });
  }, []);

  /**
   * Detect the current platform.
   */
  const detectPlatform = useCallback((): string => {
    const ua = navigator.userAgent.toLowerCase();

    if (ua.includes("android")) return "android";
    if (ua.includes("iphone") || ua.includes("ipad")) return "ios";
    if (ua.includes("windows")) return "windows";
    if (ua.includes("mac")) return "mac";
    if (ua.includes("linux")) return "linux";

    return "unknown";
  }, []);

  /**
   * Prompt the user to install the app.
   */
  const promptInstall = useCallback(async (): Promise<boolean> => {
    if (!installPromptEvent) {
      setInstallState((prev) => ({
        ...prev,
        error: new Error("Installation not available"),
      }));
      return false;
    }

    setInstallState((prev) => ({
      ...prev,
      isInstalling: true,
      error: null,
    }));

    try {
      await installPromptEvent.prompt();

      const { outcome } = await installPromptEvent.userChoice;

      setInstallPromptEvent(null);
      setInstallState((prev) => ({
        ...prev,
        canInstall: outcome !== "accepted",
        isInstalled: outcome === "accepted",
        isInstalling: false,
      }));

      return outcome === "accepted";
    } catch (error) {
      setInstallState((prev) => ({
        ...prev,
        isInstalling: false,
        error: error instanceof Error ? error : new Error("Installation failed"),
      }));
      return false;
    }
  }, [installPromptEvent]);

  /**
   * Apply the available update.
   */
  const applyUpdate = useCallback(() => {
    if (updateState.waitingWorker) {
      setUpdateState((prev) => ({
        ...prev,
        isUpdating: true,
      }));

      // Tell the waiting worker to skip waiting and activate
      updateState.waitingWorker.postMessage({ type: "SKIP_WAITING" });
    } else if (updateState.registration) {
      // Force update check
      updateState.registration.update();
    }
  }, [updateState]);

  /**
   * Manually check for updates.
   */
  const checkForUpdate = useCallback(async (): Promise<boolean> => {
    if (!("serviceWorker" in navigator)) {
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.update();

      if (registration.waiting) {
        setUpdateState((prev) => ({
          ...prev,
          hasUpdate: true,
          waitingWorker: registration.waiting,
        }));
        return true;
      }

      return false;
    } catch (error) {
      console.error("Failed to check for updates:", error);
      return false;
    }
  }, []);

  /**
   * Dismiss the install prompt.
   */
  const dismissInstall = useCallback(() => {
    setInstallPromptEvent(null);
    setInstallState((prev) => ({
      ...prev,
      canInstall: false,
    }));
  }, []);

  return {
    installState,
    updateState,
    promptInstall,
    applyUpdate,
    checkForUpdate,
    dismissInstall,
  };
}

/**
 * Hook to check if running as a PWA.
 *
 * @returns Whether the app is running as a standalone PWA
 */
export function useIsPWA(): boolean {
  const [isPWA, setIsPWA] = useState(false);

  useEffect(() => {
    const checkPWA = () => {
      return (
        window.matchMedia("(display-mode: standalone)").matches ||
        (window.navigator as Navigator & { standalone?: boolean }).standalone === true
      );
    };

    setIsPWA(checkPWA());

    // Listen for display mode changes
    const mediaQuery = window.matchMedia("(display-mode: standalone)");
    const handleChange = (e: MediaQueryListEvent) => {
      setIsPWA(e.matches);
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return isPWA;
}

/**
 * Hook to get the current display mode.
 *
 * @returns Current display mode
 */
export function useDisplayMode(): string {
  const [displayMode, setDisplayMode] = useState("browser");

  useEffect(() => {
    const checkDisplayMode = () => {
      if (window.matchMedia("(display-mode: standalone)").matches) {
        return "standalone";
      }
      if (window.matchMedia("(display-mode: minimal-ui)").matches) {
        return "minimal-ui";
      }
      if (window.matchMedia("(display-mode: fullscreen)").matches) {
        return "fullscreen";
      }
      return "browser";
    };

    setDisplayMode(checkDisplayMode());

    // Listen for display mode changes
    const modes = ["standalone", "minimal-ui", "fullscreen"];
    const cleanups: (() => void)[] = [];

    modes.forEach((mode) => {
      const mediaQuery = window.matchMedia(`(display-mode: ${mode})`);
      const handleChange = () => setDisplayMode(checkDisplayMode());
      mediaQuery.addEventListener("change", handleChange);
      cleanups.push(() => mediaQuery.removeEventListener("change", handleChange));
    });

    return () => cleanups.forEach((cleanup) => cleanup());
  }, []);

  return displayMode;
}

export default usePWA;
