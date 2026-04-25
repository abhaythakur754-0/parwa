/**
 * Mini Parwa Variant Types
 * 
 * Defines variant limits, features, and usage tracking for Mini Parwa.
 */

export type VariantType = 'mini_parwa' | 'parwa' | 'high_parwa';

export interface VariantLimits {
  monthly_tickets: number;
  ai_agents: number;
  team_members: number;
  voice_slots: number;
  kb_docs: number;
  model_tiers: ('light' | 'medium' | 'heavy')[];
  technique_tiers: number[];
  rag_top_k: number;
  api_access: 'readonly' | 'readwrite' | 'full';
}

export interface VariantUsage {
  tickets_used: number;
  tickets_remaining: number;
  ai_agents_used: number;
  team_members_used: number;
  kb_docs_used: number;
  utilization_pct: number;
  is_near_limit: boolean;  // >80% usage
  is_at_limit: boolean;    // 100% usage
}

export interface VariantInfo {
  type: VariantType;
  display_name: string;
  limits: VariantLimits;
  usage: VariantUsage;
  blocked_features: string[];
  features: string[];
}

// ── Variant Limits Configuration ─────────────────────────────────────────

export const VARIANT_LIMITS: Record<VariantType, VariantLimits> = {
  mini_parwa: {
    monthly_tickets: 2000,
    ai_agents: 1,
    team_members: 3,
    voice_slots: 0,
    kb_docs: 100,
    model_tiers: ['light'],
    technique_tiers: [1],
    rag_top_k: 3,
    api_access: 'readonly',
  },
  parwa: {
    monthly_tickets: 5000,
    ai_agents: 3,
    team_members: 10,
    voice_slots: 2,
    kb_docs: 500,
    model_tiers: ['light', 'medium'],
    technique_tiers: [1, 2],
    rag_top_k: 5,
    api_access: 'readwrite',
  },
  high_parwa: {
    monthly_tickets: 15000,
    ai_agents: 5,
    team_members: 25,
    voice_slots: 5,
    kb_docs: 2000,
    model_tiers: ['light', 'medium', 'heavy'],
    technique_tiers: [1, 2, 3],
    rag_top_k: 10,
    api_access: 'full',
  },
};

// ── Feature Sets by Variant ─────────────────────────────────────────────

export const VARIANT_FEATURES: Record<VariantType, Set<string>> = {
  mini_parwa: new Set([
    // Core Features
    'ticket_management',
    'ticket_create',
    'ticket_update',
    'ticket_close',
    'ticket_assign',
    'ticket_merge',
    'ticket_bulk_actions',
    
    // Channels
    'email_channel',
    'chat_widget',
    
    // AI Pipeline (Light model only)
    'ai_resolution',
    'ai_classification',
    'ai_sentiment',
    'ai_intent_detection',
    'ai_suggested_responses',
    'ai_kb_search',
    
    // AI Techniques (Tier 1 only)
    'technique_chain_of_thought',
    'technique_basic_react',
    
    // Knowledge Base
    'kb_upload',
    'kb_search',
    'kb_categories',
    
    // Authentication & Security
    'email_password_auth',
    'email_verification',
    'password_reset',
    'mfa_totp',
    'api_keys_readonly',
    'audit_logs',
    'rate_limiting',
    
    // Shadow Mode
    'shadow_mode',
    'shadow_preview',
    'shadow_approve_reject',
    'shadow_auto_execute',
    'shadow_log',
    
    // Billing
    'billing_monthly',
    'billing_yearly',
    'billing_upgrade',
    'billing_downgrade',
    'billing_cancel',
    'billing_invoices',
    
    // Analytics (Basic)
    'analytics_dashboard',
    'analytics_ticket_volume',
    'analytics_response_time',
    'analytics_agent_performance',
    
    // Settings
    'settings_company',
    'settings_user_management',
    'settings_notifications',
    'settings_branding_basic',
    
    // Industry Add-ons
    'industry_addons',
    'industry_ecommerce',
    'industry_saas',
    'industry_logistics',
  ]),
  
  parwa: new Set([
    // Inherits Mini Parwa features +
    'sms_channel',
    'ai_model_medium',
    'technique_tree_of_thoughts',
    'technique_least_to_most',
    'technique_step_back',
    'rag_reranking',
    'rag_deep_search',
    'custom_system_prompts',
    'brand_voice',
    'api_readwrite',
    'analytics_export',
    'analytics_reports',
    'agent_training',
    'lightning_training',
    'custom_integrations',
    'incoming_webhooks',
  ]),
  
  high_parwa: new Set([
    // Inherits Parwa features +
    'voice_ai_channel',
    'ai_model_heavy',
    'technique_self_consistency',
    'technique_reflexion',
    'technique_universe_of_thoughts',
    'technique_crp',
    'quality_coach',
    'custom_guardrails',
    'ai_guardrails',
    'api_full',
    'outgoing_webhooks',
    'analytics_custom',
    'analytics_realtime',
    'dedicated_csm',
    'premium_sla',
    'priority_routing',
  ]),
};

// ── Blocked Features by Variant ─────────────────────────────────────────

export const BLOCKED_FEATURES: Record<VariantType, Set<string>> = {
  mini_parwa: new Set([
    'voice_ai_channel',
    'sms_channel',
    'ai_model_medium',
    'ai_model_heavy',
    'technique_tree_of_thoughts',
    'technique_least_to_most',
    'technique_self_consistency',
    'technique_reflexion',
    'rag_reranking',
    'custom_system_prompts',
    'brand_voice',
    'api_readwrite',
    'api_full',
    'outgoing_webhooks',
    'custom_integrations',
    'quality_coach',
    'custom_guardrails',
    'analytics_export',
    'analytics_custom',
    'agent_training',
    'dedicated_csm',
  ]),
  parwa: new Set([
    'voice_ai_channel',
    'ai_model_heavy',
    'technique_self_consistency',
    'technique_reflexion',
    'quality_coach',
    'custom_guardrails',
    'api_full',
    'outgoing_webhooks',
    'dedicated_csm',
  ]),
  high_parwa: new Set(),
};

// ── Display Names ───────────────────────────────────────────────────────

export const VARIANT_DISPLAY_NAMES: Record<VariantType, string> = {
  mini_parwa: 'Mini Parwa',
  parwa: 'Parwa',
  high_parwa: 'High Parwa',
};

// ── Helper Functions ─────────────────────────────────────────────────────

export function getVariantLimits(variantType: VariantType): VariantLimits {
  return VARIANT_LIMITS[variantType] || VARIANT_LIMITS.mini_parwa;
}

export function isFeatureAvailable(variantType: VariantType, feature: string): boolean {
  const features = VARIANT_FEATURES[variantType] || VARIANT_FEATURES.mini_parwa;
  return features.has(feature);
}

export function isFeatureBlocked(variantType: VariantType, feature: string): boolean {
  const blocked = BLOCKED_FEATURES[variantType] || BLOCKED_FEATURES.mini_parwa;
  return blocked.has(feature);
}

export function getUpgradeRequired(variantType: VariantType, feature: string): VariantType[] {
  if (!isFeatureBlocked(variantType, feature)) return [];
  
  const tierOrder: VariantType[] = ['mini_parwa', 'parwa', 'high_parwa'];
  const currentIdx = tierOrder.indexOf(variantType);
  
  return tierOrder.slice(currentIdx + 1).filter(tier => 
    isFeatureAvailable(tier, feature)
  );
}

export function calculateUsage(limits: VariantLimits, current: {
  tickets?: number;
  agents?: number;
  team_members?: number;
  kb_docs?: number;
}): VariantUsage {
  const ticketsUsed = current.tickets || 0;
  const ticketsRemaining = Math.max(0, limits.monthly_tickets - ticketsUsed);
  const utilizationPct = limits.monthly_tickets > 0 
    ? Math.round((ticketsUsed / limits.monthly_tickets) * 100) 
    : 0;
  
  return {
    tickets_used: ticketsUsed,
    tickets_remaining: ticketsRemaining,
    ai_agents_used: current.agents || 0,
    team_members_used: current.team_members || 0,
    kb_docs_used: current.kb_docs || 0,
    utilization_pct: utilizationPct,
    is_near_limit: utilizationPct >= 80,
    is_at_limit: utilizationPct >= 100,
  };
}
