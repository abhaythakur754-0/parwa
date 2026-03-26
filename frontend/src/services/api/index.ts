/**
 * PARWA API Module
 *
 * Export all API client and endpoint functions.
 */

// Client
export { apiClient, createAPIClient, APIError } from "./client";
export type { APIResponse, RequestConfig } from "./client";

// Auth API
export { authAPI } from "./auth";
export type { User, LoginCredentials, RegisterData, AuthResponse } from "./auth";

// Variants API
export {
  variantsAPI,
  getMiniVariantConfig,
  getParwaJuniorVariantConfig,
  getParwaHighVariantConfig,
  getDefaultVariantConfigs,
} from "./variants";
export type {
  VariantId,
  VariantTier,
  VariantConfig,
  VariantSelectionResponse,
  VariantComparison,
} from "./variants";
