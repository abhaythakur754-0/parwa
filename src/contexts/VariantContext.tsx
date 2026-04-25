'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';
import {
  VariantType,
  VariantInfo,
  VariantLimits,
  VariantUsage,
  VARIANT_LIMITS,
  VARIANT_DISPLAY_NAMES,
  BLOCKED_FEATURES,
  VARIANT_FEATURES,
  calculateUsage,
} from '@/types/variant';
import { get } from '@/lib/api';

// ── Context Types ─────────────────────────────────────────────────────────

interface VariantContextValue {
  // Variant Info
  variant: VariantType;
  variantInfo: VariantInfo | null;
  limits: VariantLimits;
  usage: VariantUsage;
  
  // Feature Checks
  isFeatureAvailable: (feature: string) => boolean;
  isFeatureBlocked: (feature: string) => boolean;
  getUpgradePrompt: (feature: string) => string | null;
  
  // Limit Checks
  canCreateTicket: () => boolean;
  canAddAgent: () => boolean;
  canAddTeamMember: () => boolean;
  canUploadDoc: () => boolean;
  
  // Usage Warnings
  getTicketWarning: () => { show: boolean; message: string; severity: 'warning' | 'critical' };
  
  // Loading State
  isLoading: boolean;
  
  // Refresh Usage
  refreshUsage: () => Promise<void>;
}

const VariantContext = createContext<VariantContextValue | null>(null);

// ── Usage API Response ────────────────────────────────────────────────────

interface UsageApiResponse {
  tickets_used: number;
  tickets_remaining: number;
  ai_agents_used: number;
  team_members_used: number;
  kb_docs_used: number;
  period_start: string;
  period_end: string;
}

// ── Provider Component ────────────────────────────────────────────────────

export function VariantProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [variant, setVariant] = useState<VariantType>('mini_parwa');
  const [usage, setUsage] = useState<VariantUsage>({
    tickets_used: 0,
    tickets_remaining: 2000,
    ai_agents_used: 0,
    team_members_used: 0,
    kb_docs_used: 0,
    utilization_pct: 0,
    is_near_limit: false,
    is_at_limit: false,
  });
  const [isLoading, setIsLoading] = useState(true);

  // Get limits for current variant
  const limits = VARIANT_LIMITS[variant];

  // Fetch usage data from backend
  const refreshUsage = useCallback(async () => {
    if (!user) return;
    
    try {
      const response = await get<UsageApiResponse>('/api/billing/usage');
      
      const newUsage = calculateUsage(limits, {
        tickets: response.tickets_used,
        agents: response.ai_agents_used,
        team_members: response.team_members_used,
        kb_docs: response.kb_docs_used,
      });
      
      setUsage(newUsage);
    } catch (error) {
      // If API fails, use default values
      console.warn('Failed to fetch usage data, using defaults');
    } finally {
      setIsLoading(false);
    }
  }, [user, limits]);

  // Initialize variant from user data
  useEffect(() => {
    if (user?.variant_type) {
      const userVariant = user.variant_type as VariantType;
      if (['mini_parwa', 'parwa', 'high_parwa'].includes(userVariant)) {
        setVariant(userVariant);
      }
    }
  }, [user]);

  // Fetch usage on mount and variant change
  useEffect(() => {
    refreshUsage();
  }, [refreshUsage]);

  // ── Feature Check Functions ─────────────────────────────────────────────

  const isFeatureAvailableFn = useCallback((feature: string): boolean => {
    const features = VARIANT_FEATURES[variant];
    return features.has(feature);
  }, [variant]);

  const isFeatureBlockedFn = useCallback((feature: string): boolean => {
    const blocked = BLOCKED_FEATURES[variant];
    return blocked.has(feature);
  }, [variant]);

  const getUpgradePrompt = useCallback((feature: string): string | null => {
    if (!isFeatureBlockedFn(feature)) return null;
    
    const tierOrder: VariantType[] = ['mini_parwa', 'parwa', 'high_parwa'];
    const currentIdx = tierOrder.indexOf(variant);
    const upgradeTiers = tierOrder.slice(currentIdx + 1).filter(tier => 
      VARIANT_FEATURES[tier].has(feature)
    );
    
    if (upgradeTiers.length === 0) return null;
    
    const upgradeTo = upgradeTiers[0];
    const displayName = VARIANT_DISPLAY_NAMES[upgradeTo];
    
    return `Upgrade to ${displayName} to unlock this feature.`;
  }, [variant, isFeatureBlockedFn]);

  // ── Limit Check Functions ───────────────────────────────────────────────

  const canCreateTicket = useCallback((): boolean => {
    return usage.tickets_used < limits.monthly_tickets;
  }, [usage.tickets_used, limits.monthly_tickets]);

  const canAddAgent = useCallback((): boolean => {
    return usage.ai_agents_used < limits.ai_agents;
  }, [usage.ai_agents_used, limits.ai_agents]);

  const canAddTeamMember = useCallback((): boolean => {
    return usage.team_members_used < limits.team_members;
  }, [usage.team_members_used, limits.team_members]);

  const canUploadDoc = useCallback((): boolean => {
    return usage.kb_docs_used < limits.kb_docs;
  }, [usage.kb_docs_used, limits.kb_docs]);

  // ── Warning Functions ───────────────────────────────────────────────────

  const getTicketWarning = useCallback((): { show: boolean; message: string; severity: 'warning' | 'critical' } => {
    if (usage.is_at_limit) {
      return {
        show: true,
        message: `You've reached your monthly ticket limit of ${limits.monthly_tickets.toLocaleString()} tickets. Upgrade to continue.`,
        severity: 'critical',
      };
    }
    
    if (usage.is_near_limit) {
      return {
        show: true,
        message: `You've used ${usage.utilization_pct}% of your monthly ticket limit. Consider upgrading soon.`,
        severity: 'warning',
      };
    }
    
    return { show: false, message: '', severity: 'warning' };
  }, [usage, limits.monthly_tickets]);

  // ── Build Variant Info ──────────────────────────────────────────────────

  const variantInfo: VariantInfo | null = user ? {
    type: variant,
    display_name: VARIANT_DISPLAY_NAMES[variant],
    limits,
    usage,
    blocked_features: Array.from(BLOCKED_FEATURES[variant]),
    features: Array.from(VARIANT_FEATURES[variant]),
  } : null;

  // ── Context Value ───────────────────────────────────────────────────────

  const value: VariantContextValue = {
    variant,
    variantInfo,
    limits,
    usage,
    isFeatureAvailable: isFeatureAvailableFn,
    isFeatureBlocked: isFeatureBlockedFn,
    getUpgradePrompt,
    canCreateTicket,
    canAddAgent,
    canAddTeamMember,
    canUploadDoc,
    getTicketWarning,
    isLoading,
    refreshUsage,
  };

  return (
    <VariantContext.Provider value={value}>
      {children}
    </VariantContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useVariant(): VariantContextValue {
  const context = useContext(VariantContext);
  if (!context) {
    throw new Error('useVariant must be used within a VariantProvider');
  }
  return context;
}

// ── Feature Gate Hook ─────────────────────────────────────────────────────

export function useFeatureGate(feature: string): {
  isAvailable: boolean;
  isBlocked: boolean;
  upgradePrompt: string | null;
} {
  const { isFeatureAvailable, isFeatureBlocked, getUpgradePrompt } = useVariant();
  
  return {
    isAvailable: isFeatureAvailable(feature),
    isBlocked: isFeatureBlocked(feature),
    upgradePrompt: getUpgradePrompt(feature),
  };
}

export default VariantContext;
