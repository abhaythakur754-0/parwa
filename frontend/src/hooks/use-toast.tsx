"use client";

import * as React from "react";

/**
 * Toast types for the PARWA application.
 */
export type ToastVariant = "default" | "success" | "error" | "warning" | "info";

/**
 * Toast action button configuration.
 */
export interface ToastAction {
  label: string;
  onClick: () => void;
}

/**
 * Toast configuration object.
 */
export interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
  action?: ToastAction;
  dismissible?: boolean;
}

/**
 * Toast options for creating new toasts.
 */
export interface ToastOptions {
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
  action?: ToastAction;
  dismissible?: boolean;
}

/**
 * Toast context value type.
 */
interface ToastContextValue {
  toasts: Toast[];
  addToast: (options: ToastOptions) => string;
  dismissToast: (id: string) => void;
  updateToast: (id: string, options: Partial<ToastOptions>) => void;
  clearToasts: () => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

/**
 * Default toast duration in milliseconds.
 */
const DEFAULT_DURATION = 5000;

/**
 * Generate a unique ID for toasts.
 */
function generateId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Toast provider component.
 * 
 * Provides toast state management for the entire application.
 * Should be placed at the root of the component tree.
 * 
 * @example
 * ```tsx
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 * ```
 */
export function ToastProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const addToast = React.useCallback((options: ToastOptions): string => {
    const id = generateId();
    const toast: Toast = {
      id,
      title: options.title,
      description: options.description,
      variant: options.variant || "default",
      duration: options.duration ?? DEFAULT_DURATION,
      action: options.action,
      dismissible: options.dismissible ?? true,
    };

    setToasts((prev) => [...prev, toast]);

    // Auto-dismiss after duration
    if (toast.duration && toast.duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, toast.duration);
    }

    return id;
  }, []);

  const dismissToast = React.useCallback((id: string): void => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const updateToast = React.useCallback((id: string, options: Partial<ToastOptions>): void => {
    setToasts((prev) =>
      prev.map((t) =>
        t.id === id
          ? { ...t, ...options }
          : t
      )
    );
  }, []);

  const clearToasts = React.useCallback((): void => {
    setToasts([]);
  }, []);

  const value = React.useMemo(
    () => ({
      toasts,
      addToast,
      dismissToast,
      updateToast,
      clearToasts,
    }),
    [toasts, addToast, dismissToast, updateToast, clearToasts]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
    </ToastContext.Provider>
  );
}

/**
 * Hook to access toast functionality.
 * 
 * Can be used within or outside a ToastProvider.
 * Returns default no-op values if used outside provider.
 * 
 * @returns Toast context value with all toast methods
 * 
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { addToast } = useToast();
 *   
 *   const handleClick = () => {
 *     addToast({
 *       title: "Success!",
 *       description: "Your changes have been saved.",
 *       variant: "success",
 *     });
 *   };
 *   
 *   return <button onClick={handleClick}>Save</button>;
 * }
 * ```
 */
export function useToast(): ToastContextValue {
  const context = React.useContext(ToastContext);
  
  // Return default no-op values if used outside provider
  // This allows the Toaster to work during static generation
  if (!context) {
    return {
      toasts: [],
      addToast: () => generateId(),
      dismissToast: () => {},
      updateToast: () => {},
      clearToasts: () => {},
    };
  }
  
  return context;
}

/**
 * Convenience function to show different toast types.
 */
export const toast = {
  /**
   * Show a default toast.
   */
  default: (options: Omit<ToastOptions, "variant">): string => {
    // This is a placeholder - actual implementation would need context access
    console.log("Toast (default):", options);
    return generateId();
  },
  
  /**
   * Show a success toast.
   */
  success: (options: Omit<ToastOptions, "variant">): string => {
    console.log("Toast (success):", options);
    return generateId();
  },
  
  /**
   * Show an error toast.
   */
  error: (options: Omit<ToastOptions, "variant">): string => {
    console.log("Toast (error):", options);
    return generateId();
  },
  
  /**
   * Show a warning toast.
   */
  warning: (options: Omit<ToastOptions, "variant">): string => {
    console.log("Toast (warning):", options);
    return generateId();
  },
  
  /**
   * Show an info toast.
   */
  info: (options: Omit<ToastOptions, "variant">): string => {
    console.log("Toast (info):", options);
    return generateId();
  },
};

export default useToast;
