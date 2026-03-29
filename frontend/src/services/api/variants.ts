/**
 * PARWA Variants API
 *
 * API functions for managing PARWA variants (Mini, Junior, High).
 */

import { apiClient } from "./client";

/**
 * Variant tier type.
 */
export type VariantTier = "light" | "medium" | "heavy";

/**
 * Variant ID type.
 */
export type VariantId = "mini" | "parwa" | "parwa_high";

/**
 * Variant configuration.
 */
export interface VariantConfig {
  /** Variant ID */
  id: VariantId;
  /** Display name */
  name: string;
  /** Tier level */
  tier: VariantTier;
  /** Monthly price in USD */
  price: number;
  /** Annual price in USD (if discounted) */
  annualPrice?: number;
  /** Maximum concurrent calls */
  maxConcurrentCalls: number;
  /** Maximum refund amount in USD */
  refundLimit: number;
  /** Escalation threshold percentage */
  escalationThreshold: number;
  /** Supported channels */
  supportedChannels: string[];
  /** AI tier level */
  aiTier: VariantTier;
  /** Target audience */
  targetAudience: string;
  /** Feature flags */
  features: {
    /** Can execute refunds with approval */
    canExecuteRefunds: boolean;
    /** Has HIPAA compliance */
    hipaaCompliance: boolean;
    /** Has churn prediction */
    churnPrediction: boolean;
    /** Maximum teams supported */
    maxTeams: number;
    /** Has video support */
    videoSupport: boolean;
    /** Has learning from feedback */
    learningEnabled: boolean;
    /** Has analytics dashboard */
    analyticsDashboard: boolean;
  };
}

/**
 * Variant selection response.
 */
export interface VariantSelectionResponse {
  /** Success indicator */
  success: boolean;
  /** Selected variant ID */
  variantId: VariantId;
  /** Message */
  message?: string;
}

/**
 * Variant comparison data.
 */
export interface VariantComparison {
  /** Feature name */
  feature: string;
  /** Category */
  category: string;
  /** Mini variant value */
  mini: string | boolean;
  /** PARWA Junior value */
  parwa: string | boolean;
  /** PARWA High value */
  parwa_high: string | boolean;
}

/**
 * Variants API functions.
 */
export const variantsAPI = {
  /**
   * Get all available variants.
   *
   * @returns List of variant configurations
   * @throws APIError on failure
   */
  async getVariants(): Promise<VariantConfig[]> {
    const response = await apiClient.get<VariantConfig[]>("/variants", undefined, {
      includeAuth: false,
    });

    return response.data;
  },

  /**
   * Get a specific variant configuration.
   *
   * @param variantId - Variant ID to fetch
   * @returns Variant configuration
   * @throws APIError on failure
   */
  async getVariantConfig(variantId: VariantId): Promise<VariantConfig> {
    const response = await apiClient.get<VariantConfig>(
      `/variants/${variantId}`,
      undefined,
      { includeAuth: false }
    );

    return response.data;
  },

  /**
   * Select a variant for the current user/company.
   *
   * @param variantId - Variant ID to select
   * @returns Selection response
   * @throws APIError on failure
   */
  async selectVariant(variantId: VariantId): Promise<VariantSelectionResponse> {
    const response = await apiClient.post<VariantSelectionResponse>(
      "/variants/select",
      { variantId }
    );

    return response.data;
  },

  /**
   * Get the currently selected variant for the user/company.
   *
   * @returns Selected variant configuration or null
   * @throws APIError on failure
   */
  async getSelectedVariant(): Promise<VariantConfig | null> {
    try {
      const response = await apiClient.get<VariantConfig | null>(
        "/variants/selected"
      );
      return response.data;
    } catch (error) {
      // Return null if not found or not authenticated
      if (error instanceof Error && error.message.includes("401")) {
        return null;
      }
      throw error;
    }
  },

  /**
   * Get feature comparison for all variants.
   *
   * @returns Comparison data for all variants
   * @throws APIError on failure
   */
  async getComparison(): Promise<VariantComparison[]> {
    const response = await apiClient.get<VariantComparison[]>(
      "/variants/comparison",
      undefined,
      { includeAuth: false }
    );

    return response.data;
  },

  /**
   * Calculate pricing for a variant.
   *
   * @param variantId - Variant ID
   * @param billingPeriod - Billing period (monthly/yearly)
   * @param seats - Number of seats (for team plans)
   * @returns Pricing breakdown
   * @throws APIError on failure
   */
  async calculatePricing(
    variantId: VariantId,
    billingPeriod: "monthly" | "yearly",
    seats: number = 1
  ): Promise<{
    basePrice: number;
    seatPrice: number;
    total: number;
    discount: number;
  }> {
    const response = await apiClient.post<{
      basePrice: number;
      seatPrice: number;
      total: number;
      discount: number;
    }>("/variants/pricing", {
      variantId,
      billingPeriod,
      seats,
    });

    return response.data;
  },

  /**
   * Check if a variant supports a specific feature.
   *
   * @param variantId - Variant ID
   * @param feature - Feature to check
   * @returns Whether the feature is supported
   * @throws APIError on failure
   */
  async checkFeatureSupport(
    variantId: VariantId,
    feature: string
  ): Promise<{ supported: boolean }> {
    const response = await apiClient.get<{ supported: boolean }>(
      `/variants/${variantId}/features/${feature}`
    );

    return response.data;
  },

  /**
   * Upgrade to a higher tier variant.
   *
   * @param variantId - Target variant ID
   * @returns Upgrade response
   * @throws APIError on failure
   */
  async upgradeVariant(variantId: VariantId): Promise<VariantSelectionResponse> {
    const response = await apiClient.post<VariantSelectionResponse>(
      "/variants/upgrade",
      { variantId }
    );

    return response.data;
  },

  /**
   * Downgrade to a lower tier variant.
   *
   * @param variantId - Target variant ID
   * @returns Downgrade response
   * @throws APIError on failure
   */
  async downgradeVariant(variantId: VariantId): Promise<VariantSelectionResponse> {
    const response = await apiClient.post<VariantSelectionResponse>(
      "/variants/downgrade",
      { variantId }
    );

    return response.data;
  },
};

/**
 * Get default Mini variant configuration.
 * Used for display purposes when API is not available.
 */
export function getMiniVariantConfig(): VariantConfig {
  return {
    id: "mini",
    name: "Mini PARWA",
    tier: "light",
    price: 999,
    annualPrice: 9990,
    maxConcurrentCalls: 2,
    refundLimit: 50,
    escalationThreshold: 70,
    supportedChannels: ["faq", "email", "chat", "sms"],
    aiTier: "light",
    targetAudience: "Small businesses",
    features: {
      canExecuteRefunds: false,
      hipaaCompliance: false,
      churnPrediction: false,
      maxTeams: 1,
      videoSupport: false,
      learningEnabled: false,
      analyticsDashboard: false,
    },
  };
}

/**
 * Get default PARWA Junior variant configuration.
 * Used for display purposes when API is not available.
 */
export function getParwaJuniorVariantConfig(): VariantConfig {
  return {
    id: "parwa",
    name: "PARWA Junior",
    tier: "medium",
    price: 2499,
    annualPrice: 24990,
    maxConcurrentCalls: 5,
    refundLimit: 500,
    escalationThreshold: 60,
    supportedChannels: ["faq", "email", "chat", "sms", "voice", "video"],
    aiTier: "medium",
    targetAudience: "Growing teams",
    features: {
      canExecuteRefunds: false,
      hipaaCompliance: false,
      churnPrediction: false,
      maxTeams: 2,
      videoSupport: true,
      learningEnabled: true,
      analyticsDashboard: true,
    },
  };
}

/**
 * Get default PARWA High variant configuration.
 * Used for display purposes when API is not available.
 */
export function getParwaHighVariantConfig(): VariantConfig {
  return {
    id: "parwa_high",
    name: "PARWA High",
    tier: "heavy",
    price: 3999,
    annualPrice: 39990,
    maxConcurrentCalls: 10,
    refundLimit: 2000,
    escalationThreshold: 50,
    supportedChannels: ["faq", "email", "chat", "sms", "voice", "video"],
    aiTier: "heavy",
    targetAudience: "Enterprise",
    features: {
      canExecuteRefunds: true,
      hipaaCompliance: true,
      churnPrediction: true,
      maxTeams: 5,
      videoSupport: true,
      learningEnabled: true,
      analyticsDashboard: true,
    },
  };
}

/**
 * Get all default variant configurations.
 * Used for display purposes when API is not available.
 */
export function getDefaultVariantConfigs(): VariantConfig[] {
  return [
    getMiniVariantConfig(),
    getParwaJuniorVariantConfig(),
    getParwaHighVariantConfig(),
  ];
}

export default variantsAPI;
