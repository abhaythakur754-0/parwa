/**
 * PARWA Frontend v2 - Main Entry
 *
 * Export all modules from the v2 frontend.
 */

// React Query Configuration
export {
  createQueryClient,
  queryKeys,
  defaultQueryClient,
  type QueryClientOptions,
  type QueryKeys,
} from "./lib/react-query/query-client";

export {
  QueryProvider,
  useQueryClient,
  useQueryCache,
  type QueryProviderProps,
} from "./lib/react-query/query-provider";

export {
  useOptimisticMutation,
  useListMutation,
  useInfiniteListMutation,
  useRetryableMutation,
  useBatchMutation,
  useDebouncedMutation,
  type OptimisticContext,
  type OptimisticMutationOptions,
  type ListMutationOptions,
  type InfiniteListMutationOptions,
} from "./lib/react-query/mutation-helpers";

// Query Hooks
export * from "./hooks/queries";

// PWA Hooks
export * from "./hooks/pwa";

// PWA Components
export * from "./components";
