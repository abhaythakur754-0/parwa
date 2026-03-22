/**
 * PARWA Variant Store
 *
 * Zustand store for managing variant selection state.
 * Handles selected variant, configuration, and pricing.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { VariantId, VariantConfig } from "../services/api/variants";
import { variantsAPI, getDefaultVariantConfigs } from "../services/api/variants";

/**
 * Variant store state interface.
 */
export interface VariantState {
  /** Currently selected variant ID */
  selectedVariant: VariantId | null;
  /** Configuration for selected variant */
  variantConfig: VariantConfig | null;
  /** All available variants */
  availableVariants: VariantConfig[];
  /** Loading state */
  isLoading: boolean;
  /** Error message */
  error: string | null;

  // Actions
  /** Select a variant */
  selectVariant: (variantId: VariantId) => Promise<void>;
  /** Clear selected variant */
  clearVariant: () => void;
  /** Fetch all available variants */
  fetchVariants: () => Promise<void>;
  /** Set variant directly (for local selection without API) */
  setLocalVariant: (variantId: VariantId) => void;
  /** Get variant config by ID */
  getVariantById: (variantId: VariantId) => VariantConfig | undefined;
  /** Clear any errors */
  clearError: () => void;
  /** Initialize store with defaults */
  initialize: () => void;
}

/**
 * Initial variant state.
 */
const initialState = {
  selectedVariant: null,
  variantConfig: null,
  availableVariants: [] as VariantConfig[],
  isLoading: false,
  error: null,
};

/**
 * Variant store using Zustand with persistence.
 *
 * @example
 * ```tsx
 * function VariantSelector() {
 *   const { selectedVariant, selectVariant, isLoading } = useVariantStore();
 *
 *   const handleSelect = async (variantId: VariantId) => {
 *     await selectVariant(variantId);
 *   };
 *
 *   return <div>...</div>;
 * }
 * ```
 */
export const useVariantStore = create<VariantState>()(
  persist(
    (set, get) => ({
      ...initialState,

      selectVariant: async (variantId: VariantId) => {
        set({ isLoading: true, error: null });

        try {
          // Try to select via API (if authenticated)
          try {
            await variantsAPI.selectVariant(variantId);
          } catch {
            // If API fails (not authenticated), continue with local selection
          }

          // Get the variant config
          let config: VariantConfig | undefined;

          // Try to fetch from API first
          try {
            config = await variantsAPI.getVariantConfig(variantId);
          } catch {
            // Fallback to local configs
            const { availableVariants } = get();
            config = availableVariants.find((v) => v.id === variantId);
          }

          if (!config) {
            throw new Error(`Variant ${variantId} not found`);
          }

          set({
            selectedVariant: variantId,
            variantConfig: config,
            isLoading: false,
            error: null,
          });
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Failed to select variant";
          set({
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },

      clearVariant: () => {
        set({
          selectedVariant: null,
          variantConfig: null,
        });
      },

      fetchVariants: async () => {
        set({ isLoading: true, error: null });

        try {
          const variants = await variantsAPI.getVariants();

          set({
            availableVariants: variants,
            isLoading: false,
          });
        } catch {
          // Fallback to default configs
          const defaultVariants = getDefaultVariantConfigs();

          set({
            availableVariants: defaultVariants,
            isLoading: false,
          });
        }
      },

      setLocalVariant: (variantId: VariantId) => {
        const { availableVariants } = get();
        const config = availableVariants.find((v) => v.id === variantId);

        if (config) {
          set({
            selectedVariant: variantId,
            variantConfig: config,
          });
        }
      },

      getVariantById: (variantId: VariantId) => {
        const { availableVariants } = get();
        return availableVariants.find((v) => v.id === variantId);
      },

      clearError: () => {
        set({ error: null });
      },

      initialize: () => {
        const { availableVariants } = get();

        // Load default variants if not already loaded
        if (availableVariants.length === 0) {
          const defaultVariants = getDefaultVariantConfigs();
          set({ availableVariants: defaultVariants });
        }
      },
    }),
    {
      name: "parwa-variant",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        selectedVariant: state.selectedVariant,
        variantConfig: state.variantConfig,
      }),
    }
  )
);

/**
 * Hook to get selected variant ID.
 */
export function useSelectedVariant() {
  return useVariantStore((state) => state.selectedVariant);
}

/**
 * Hook to get variant config.
 */
export function useVariantConfig() {
  return useVariantStore((state) => state.variantConfig);
}

/**
 * Hook to get available variants.
 */
export function useAvailableVariants() {
  return useVariantStore((state) => state.availableVariants);
}

/**
 * Hook to get variant loading state.
 */
export function useVariantLoading() {
  return useVariantStore((state) => state.isLoading);
}

/**
 * Hook to check if a variant is selected.
 */
export function useIsVariantSelected(variantId: VariantId) {
  return useVariantStore((state) => state.selectedVariant === variantId);
}

export default useVariantStore;
