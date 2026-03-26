/**
 * PARWA Stores
 *
 * Export all Zustand stores for the PARWA application.
 *
 * Stores included:
 * - useAuthStore: Authentication state (user, token, isAuthenticated)
 * - useVariantStore: Variant selection state (selectedVariant, config)
 * - useUIStore: UI state (sidebar, theme, modals, toasts)
 *
 * @example
 * ```tsx
 * import { useAuthStore, useVariantStore, useUIStore } from "@/stores";
 *
 * function App() {
 *   const { isAuthenticated } = useAuthStore();
 *   const { selectedVariant } = useVariantStore();
 *   const { theme, setTheme } = useUIStore();
 *
 *   return (
 *     <div>
 *       <p>Auth: {isAuthenticated ? "Yes" : "No"}</p>
 *       <p>Variant: {selectedVariant}</p>
 *       <p>Theme: {theme}</p>
 *     </div>
 *   );
 * }
 * ```
 */

// Auth store
export { useAuthStore, useUser, useIsAuthenticated, useAuthLoading, useAuthError } from "./authStore";
export type { AuthState } from "./authStore";

// Variant store
export {
  useVariantStore,
  useSelectedVariant,
  useVariantConfig,
  useAvailableVariants,
  useVariantLoading,
  useIsVariantSelected,
} from "./variantStore";
export type { VariantState } from "./variantStore";

// UI store
export {
  useUIStore,
  useSidebar,
  useTheme,
  useModal,
  useToasts,
  useIsModalOpen,
} from "./uiStore";
export type { UIState, Theme, ModalState, ToastNotification } from "./uiStore";
