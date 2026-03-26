/**
 * PARWA UI Store
 *
 * Zustand store for managing UI state.
 * Handles sidebar, theme, modals, and other UI preferences.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * Theme type.
 */
export type Theme = "light" | "dark" | "system";

/**
 * Modal state.
 */
export interface ModalState {
  /** Modal ID */
  id: string;
  /** Modal data */
  data?: Record<string, unknown>;
}

/**
 * Toast notification.
 */
export interface ToastNotification {
  /** Unique toast ID */
  id: string;
  /** Toast title */
  title: string;
  /** Toast description */
  description?: string;
  /** Toast variant */
  variant: "default" | "success" | "error" | "warning";
  /** Auto dismiss timeout (ms) */
  duration?: number;
}

/**
 * UI store state interface.
 */
export interface UIState {
  // Sidebar
  /** Whether sidebar is open */
  sidebarOpen: boolean;
  /** Sidebar collapsed state */
  sidebarCollapsed: boolean;

  // Theme
  /** Current theme */
  theme: Theme;

  // Modals
  /** Currently active modal */
  activeModal: ModalState | null;
  /** Stack of open modals */
  modalStack: ModalState[];

  // Toasts
  /** Active toast notifications */
  toasts: ToastNotification[];

  // Loading states
  /** Global loading state */
  globalLoading: boolean;
  /** Loading messages */
  loadingMessage: string | null;

  // Navigation
  /** Current active nav item */
  activeNavItem: string | null;
  /** Breadcrumb trail */
  breadcrumbs: Array<{ label: string; href?: string }>;

  // Actions - Sidebar
  /** Toggle sidebar open/close */
  toggleSidebar: () => void;
  /** Set sidebar open state */
  setSidebarOpen: (open: boolean) => void;
  /** Toggle sidebar collapsed state */
  toggleSidebarCollapsed: () => void;
  /** Set sidebar collapsed state */
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Actions - Theme
  /** Set theme */
  setTheme: (theme: Theme) => void;
  /** Toggle between light and dark */
  toggleTheme: () => void;

  // Actions - Modals
  /** Open a modal */
  openModal: (id: string, data?: Record<string, unknown>) => void;
  /** Close current modal */
  closeModal: () => void;
  /** Close all modals */
  closeAllModals: () => void;
  /** Go back in modal stack */
  modalBack: () => void;

  // Actions - Toasts
  /** Add a toast notification */
  addToast: (toast: Omit<ToastNotification, "id">) => string;
  /** Remove a toast by ID */
  removeToast: (id: string) => void;
  /** Clear all toasts */
  clearToasts: () => void;

  // Actions - Loading
  /** Set global loading state */
  setGlobalLoading: (loading: boolean, message?: string) => void;

  // Actions - Navigation
  /** Set active nav item */
  setActiveNavItem: (item: string | null) => void;
  /** Set breadcrumbs */
  setBreadcrumbs: (breadcrumbs: Array<{ label: string; href?: string }>) => void;

  // Actions - Reset
  /** Reset all UI state */
  resetUIState: () => void;
}

/**
 * Initial UI state.
 */
const initialState = {
  sidebarOpen: true,
  sidebarCollapsed: false,
  theme: "system" as Theme,
  activeModal: null,
  modalStack: [],
  toasts: [],
  globalLoading: false,
  loadingMessage: null,
  activeNavItem: null,
  breadcrumbs: [],
};

/**
 * Generate unique ID for toasts.
 */
function generateId(): string {
  return `toast-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * UI store using Zustand with persistence.
 *
 * @example
 * ```tsx
 * function ThemeToggle() {
 *   const { theme, setTheme, toggleTheme } = useUIStore();
 *
 *   return (
 *     <button onClick={toggleTheme}>
 *       Current: {theme}
 *     </button>
 *   );
 * }
 *
 * function Sidebar() {
 *   const { sidebarOpen, toggleSidebar } = useUIStore();
 *
 *   return (
 *     <aside className={sidebarOpen ? 'open' : 'closed'}>
 *       ...
 *     </aside>
 *   );
 * }
 * ```
 */
export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Sidebar actions
      toggleSidebar: () => {
        set((state) => ({ sidebarOpen: !state.sidebarOpen }));
      },

      setSidebarOpen: (open: boolean) => {
        set({ sidebarOpen: open });
      },

      toggleSidebarCollapsed: () => {
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
      },

      setSidebarCollapsed: (collapsed: boolean) => {
        set({ sidebarCollapsed: collapsed });
      },

      // Theme actions
      setTheme: (theme: Theme) => {
        set({ theme });

        // Apply theme to document
        if (typeof document !== "undefined") {
          const root = document.documentElement;

          if (theme === "system") {
            const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
              .matches
              ? "dark"
              : "light";
            root.classList.toggle("dark", systemTheme === "dark");
          } else {
            root.classList.toggle("dark", theme === "dark");
          }
        }
      },

      toggleTheme: () => {
        const { theme } = get();
        const newTheme = theme === "dark" ? "light" : "dark";
        get().setTheme(newTheme);
      },

      // Modal actions
      openModal: (id: string, data?: Record<string, unknown>) => {
        const { activeModal, modalStack } = get();

        // Push current modal to stack if exists
        const newStack = activeModal ? [...modalStack, activeModal] : modalStack;

        set({
          activeModal: { id, data },
          modalStack: newStack,
        });
      },

      closeModal: () => {
        const { modalStack } = get();

        // Pop from stack if available
        if (modalStack.length > 0) {
          const newStack = [...modalStack];
          const previousModal = newStack.pop();
          set({
            activeModal: previousModal ?? null,
            modalStack: newStack,
          });
        } else {
          set({ activeModal: null, modalStack: [] });
        }
      },

      closeAllModals: () => {
        set({ activeModal: null, modalStack: [] });
      },

      modalBack: () => {
        get().closeModal();
      },

      // Toast actions
      addToast: (toast: Omit<ToastNotification, "id">) => {
        const id = generateId();
        const newToast: ToastNotification = {
          ...toast,
          id,
          duration: toast.duration ?? 5000,
        };

        set((state) => ({
          toasts: [...state.toasts, newToast],
        }));

        // Auto remove after duration
        if (newToast.duration && newToast.duration > 0) {
          setTimeout(() => {
            get().removeToast(id);
          }, newToast.duration);
        }

        return id;
      },

      removeToast: (id: string) => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      },

      clearToasts: () => {
        set({ toasts: [] });
      },

      // Loading actions
      setGlobalLoading: (loading: boolean, message?: string) => {
        set({
          globalLoading: loading,
          loadingMessage: message ?? null,
        });
      },

      // Navigation actions
      setActiveNavItem: (item: string | null) => {
        set({ activeNavItem: item });
      },

      setBreadcrumbs: (breadcrumbs: Array<{ label: string; href?: string }>) => {
        set({ breadcrumbs });
      },

      // Reset
      resetUIState: () => {
        set({
          ...initialState,
          // Preserve theme preference
          theme: get().theme,
        });
      },
    }),
    {
      name: "parwa-ui",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
      }),
    }
  )
);

/**
 * Hook to get sidebar state.
 */
export function useSidebar() {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const sidebarCollapsed = useUIStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);
  const toggleSidebarCollapsed = useUIStore((state) => state.toggleSidebarCollapsed);
  const setSidebarCollapsed = useUIStore((state) => state.setSidebarCollapsed);

  return {
    sidebarOpen,
    sidebarCollapsed,
    toggleSidebar,
    setSidebarOpen,
    toggleSidebarCollapsed,
    setSidebarCollapsed,
  };
}

/**
 * Hook to get theme state.
 */
export function useTheme() {
  const theme = useUIStore((state) => state.theme);
  const setTheme = useUIStore((state) => state.setTheme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);

  return { theme, setTheme, toggleTheme };
}

/**
 * Hook to get modal state.
 */
export function useModal() {
  const activeModal = useUIStore((state) => state.activeModal);
  const openModal = useUIStore((state) => state.openModal);
  const closeModal = useUIStore((state) => state.closeModal);
  const closeAllModals = useUIStore((state) => state.closeAllModals);

  return { activeModal, openModal, closeModal, closeAllModals };
}

/**
 * Hook to get toast notifications.
 */
export function useToasts() {
  const toasts = useUIStore((state) => state.toasts);
  const addToast = useUIStore((state) => state.addToast);
  const removeToast = useUIStore((state) => state.removeToast);
  const clearToasts = useUIStore((state) => state.clearToasts);

  return { toasts, addToast, removeToast, clearToasts };
}

/**
 * Hook to check if a specific modal is open.
 */
export function useIsModalOpen(modalId: string) {
  return useUIStore((state) => state.activeModal?.id === modalId);
}

export default useUIStore;
