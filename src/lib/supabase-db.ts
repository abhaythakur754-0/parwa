/**
 * PARWA Database Utility - Supabase Direct
 * 
 * Uses Supabase REST API directly (no Prisma dependency)
 * All data persists to PostgreSQL in Supabase cloud
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://fmpibdauppnzfisodkhp.supabase.co';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZtcGliZGF1cHBuemZpc29ka2hwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0NjQ5MjE3NCwiZXhwIjoyMDAyMDY4MTc0fQ.qBGnJkO4LWHtB7p7NBnS-6UQLkXjJvnvZ0wqYZGPJvI';

interface DbConfig {
  table: string;
  schema?: string;
}

interface QueryOptions {
  select?: string;
  filter?: Record<string, unknown>;
  orderBy?: { column: string; ascending?: boolean };
  limit?: number;
  offset?: number;
  single?: boolean;
}

/**
 * Base database client for Supabase REST API
 */
export class SupabaseClient {
  private baseUrl: string;
  private headers: HeadersInit;

  constructor() {
    this.baseUrl = `${SUPABASE_URL}/rest/v1`;
    this.headers = {
      'Content-Type': 'application/json',
      'apikey': SUPABASE_SERVICE_KEY,
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
      'Prefer': 'return=representation',
    };
  }

  /**
   * Fetch records from a table
   */
  async from(table: string) {
    const url = `${this.baseUrl}/${table}`;
    
    return {
      select: async (columns = '*', options?: QueryOptions) => {
        let queryUrl = `${url}?select=${columns}`;
        
        if (options?.filter) {
          Object.entries(options.filter).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              queryUrl += `&${key}=eq.${encodeURIComponent(String(value))}`;
            }
          });
        }
        
        if (options?.orderBy) {
          queryUrl += `&order=${options.orderBy.column}.${options.orderBy.ascending ? 'asc' : 'desc'}`;
        }
        
        if (options?.limit) {
          queryUrl += `&limit=${options.limit}`;
        }
        
        if (options?.offset) {
          queryUrl += `&offset=${options.offset}`;
        }
        
        const response = await fetch(queryUrl, { headers: this.headers });
        
        if (!response.ok) {
          throw new Error(`Query error: ${response.status} ${await response.text()}`);
        }
        
        const data = await response.json();
        return options?.single ? data[0] : data;
      },

      insert: async (data: Record<string, unknown> | Record<string, unknown>[]) => {
        const response = await fetch(url, {
          method: 'POST',
          headers: this.headers,
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw new Error(`Insert error: ${response.status} ${await response.text()}`);
        }

        return response.json();
      },

      update: async (data: Record<string, unknown>, filter?: Record<string, unknown>) => {
        let updateUrl = url;
        if (filter) {
          updateUrl += '?' + Object.entries(filter)
            .map(([key, value]) => `${key}=eq.${encodeURIComponent(String(value))}`)
            .join('&');
        }

        const response = await fetch(updateUrl, {
          method: 'PATCH',
          headers: {
            ...this.headers,
            'Prefer': 'return=representation',
          },
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw new Error(`Update error: ${response.status} ${await response.text()}`);
        }

        return response.json();
      },

      delete: async (filter?: Record<string, unknown>) => {
        let deleteUrl = url;
        if (filter) {
          deleteUrl += '?' + Object.entries(filter)
            .map(([key, value]) => `${key}=eq.${encodeURIComponent(String(value))}`)
            .join('&');
        }

        const response = await fetch(deleteUrl, {
          method: 'DELETE',
          headers: this.headers,
        });

        if (!response.ok) {
          throw new Error(`Delete error: ${response.status} ${await response.text()}`);
        }

        return true;
      },
    };
  }

  /**
   * Execute raw SQL (requires rpc function)
   */
  async rpc(functionName: string, params?: Record<string, unknown>) {
    const url = `${SUPABASE_URL}/rest/v1/rpc/${functionName}`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(params || {}),
    });

    if (!response.ok) {
      throw new Error(`RPC error: ${response.status} ${await response.text()}`);
    }

    return response.json();
  }
}

// Singleton instance
export const db = new SupabaseClient();

// ── Convenience functions for Onboarding ────────────────────────────

export interface OnboardingSessionData {
  user_id: string;
  status?: string;
  current_step?: number;
  completed_steps?: number[];
  details_completed?: boolean;
  integration_completed?: boolean;
  kb_completed?: boolean;
  first_victory_completed?: boolean;
  ai_name?: string;
  selected_variant?: string;
  selected_industry?: string;
}

export async function getOnboardingSession(userId: string) {
  try {
    return await db.from('onboarding_sessions')
      .select('*', { filter: { user_id: userId }, single: true });
  } catch (error) {
    console.error('[DB] Error fetching onboarding session:', error);
    return null;
  }
}

export async function createOrUpdateOnboardingSession(data: OnboardingSessionData) {
  try {
    const existing = await getOnboardingSession(data.user_id);
    
    if (existing) {
      return await db.from('onboarding_sessions')
        .update(
          { 
            ...data, 
            updated_at: new Date().toISOString() 
          } as unknown as Record<string, unknown>,
          { user_id: data.user_id }
        );
    } else {
      return await db.from('onboarding_sessions')
        .insert(data as unknown as Record<string, unknown>);
    }
  } catch (error) {
    console.error('[DB] Error saving onboarding session:', error);
    throw error;
  }
}

export async function completeOnboardingStep(userId: string, step: number) {
  const session = await getOnboardingSession(userId);
  
  if (!session) {
    throw new Error('No onboarding session found');
  }

  const completedSteps = [...(session.completed_steps || [])];
  if (!completedSteps.includes(step)) {
    completedSteps.push(step);
  }

  const updates: Partial<OnboardingSessionData> & Record<string, unknown> = {
    completed_steps: completedSteps,
    current_step: Math.min(session.current_step + 1, 4),
    updated_at: new Date().toISOString(),
  };

  // Mark specific steps as complete
  switch (step) {
    case 1:
      updates.details_completed = true;
      break;
    case 2:
      updates.integration_completed = true;
      break;
    case 3:
      updates.kb_completed = true;
      break;
    case 4:
      updates.first_victory_completed = true;
      updates.status = 'completed';
      updates.completed_at = new Date().toISOString();
      break;
  }

  return createOrUpdateOnboardingSession({
    user_id: userId,
    ...updates,
  } as OnboardingSessionData);
}

// ── User Details (Step 1) ──────────────────────────────────────────

export interface UserDetailsData {
  user_id: string;
  full_name: string;
  company_name?: string;
  company_url?: string;
  work_email?: string;
  work_email_verified?: boolean;
  industry?: string;
  website?: string;
}

export async function saveUserDetails(data: UserDetailsData) {
  try {
    const existing = await db.from('user_details')
      .select('*', { filter: { user_id: data.user_id }, single: true });

    if (existing) {
      return await db.from('user_details')
        .update(
          { ...data, updated_at: new Date().toISOString() } as unknown as Record<string, unknown>,
          { user_id: data.user_id }
        );
    } else {
      return await db.from('user_details')
        .insert(data as unknown as Record<string, unknown>);
    }
  } catch (error) {
    console.error('[DB] Error saving user details:', error);
    throw error;
  }
}

export async function getUserDetails(userId: string) {
  try {
    return await db.from('user_details')
      .select('*', { filter: { user_id: userId }, single: true });
  } catch (error) {
    console.error('[DB] Error fetching user details:', error);
    return null;
  }
}

// ── Legal Consents ─────────────────────────────────────────────────

export async function saveLegalConsent(
  userDetailsId: string,
  consentType: 'terms' | 'privacy' | 'ai_data',
  ipAddress?: string,
  userAgent?: string
) {
  return db.from('legal_consents').insert({
    user_details_id: userDetailsId,
    consent_type: consentType,
    ip_address: ipAddress,
    user_agent: userAgent,
  });
}

// ── Integrations (Step 2) ──────────────────────────────────────────

export interface IntegrationData {
  user_id: string;
  type: string;
  name: string;
  status?: string;
  config?: Record<string, unknown>;
  kb_connected_id?: string;
}

export async function saveIntegration(data: IntegrationData) {
  return db.from('integrations').insert(data as unknown as Record<string, unknown>);
}

export async function getIntegrations(userId: string) {
  return db.from('integrations').select('*', { filter: { user_id: userId } });
}

// ── Knowledge Base (Step 3) ────────────────────────────────────────

export interface KnowledgeBaseData {
  user_id: string;
  name: string;
  description?: string;
  type?: string;
  source_url?: string;
  crm_type?: string;
}

export async function createKnowledgeBase(data: KnowledgeBaseData) {
  return db.from('knowledge_bases').insert(data as unknown as Record<string, unknown>);
}

export async function getKnowledgeBases(userId: string) {
  return db.from('knowledge_bases').select('*', { filter: { user_id: userId } });
}

export async function connectExistingKB(
  userId: string,
  kbId: string,
  name: string,
  crmType?: string
) {
  // Create a linked KB entry pointing to existing CRM KB
  return createKnowledgeBase({
    user_id: userId,
    name: name || `Connected KB (${crmType})`,
    type: 'connected',
    crm_type: crmType,
    source_url: kbId,
  });
}

// ── Payments ───────────────────────────────────────────────────────

export interface PaymentData {
  user_id: string;
  subscription_id?: string;
  amount: number;
  currency?: string;
  status?: string;
  payment_method?: string;
  razorpay_order_id?: string;
  razorpay_payment_id?: string;
  razorpay_signature?: string;
}

export async function createPayment(data: PaymentData) {
  return db.from('payments').insert(data as unknown as Record<string, unknown>);
}

export async function updatePaymentStatus(
  paymentId: string,
  status: string,
  extraData?: Record<string, unknown>
) {
  return db.from('payments').update(
    { 
      status, 
      ...extraData,
      updated_at: new Date().toISOString() 
    } as unknown as Record<string, unknown>,
    { id: paymentId }
  );
}

export async function getUserPayments(userId: string) {
  return db.from('payments').select('*', { 
    filter: { user_id: userId },
    orderBy: { column: 'created_at', ascending: false }
  });
}

// ── Subscriptions ──────────────────────────────────────────────────

export interface SubscriptionData {
  user_id: string;
  plan_id: string;
  plan_name: string;
  billing_cycle?: string;
  amount: number;
  currency?: string;
  trial_ends_at?: string;
}

export async function createSubscription(data: SubscriptionData) {
  return db.from('subscriptions').insert(data as unknown as Record<string, unknown>);
}

export async function getUserSubscription(userId: string) {
  const subs = await db.from('subscriptions').select('*', { 
    filter: { user_id: userId, status: 'active' },
    single: true
  });
  return subs;
}

export default db;
