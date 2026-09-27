/**
 * PARWA Variant Store — Unit Tests
 *
 * Tests tier logic, feature maps, usage limits, fetchTier,
 * isAtLimit, and all helper functions.
 *
 * Updated 2026-07-26: Mini PARWA removed — codebase now has 2 tiers
 * (parwa $2,499/mo + high $3,999/mo). All variants share the SAME AI
 * capabilities; tiers differ only in ticket volume / numeric limits.
 */

import { useVariantStore, isTierAtLeast, getTierLabel, getTierPrice, getTierColor, getFeatureMapForTier, TIER_ORDER, VariantTier } from '@/lib/variant-store';
import { useBillingStore } from '@/lib/billing-store';

// global.fetch mock — required for fetchTier/fetchUsage tests
// (variant-store.fetchTier delegates to billing-store.fetchBilling)
const mockFetch = jest.fn() as jest.Mock;
global.fetch = mockFetch;

// ── Helper Functions ──────────────────────────────────────────────

describe('isTierAtLeast', () => {
  it('returns true when current tier equals required tier', () => {
    expect(isTierAtLeast('parwa', 'parwa')).toBe(true);
    expect(isTierAtLeast('high', 'high')).toBe(true);
  });

  it('returns true when current tier exceeds required tier', () => {
    expect(isTierAtLeast('high', 'parwa')).toBe(true);
  });

  it('returns false when current tier is below required tier', () => {
    expect(isTierAtLeast('parwa', 'high')).toBe(false);
  });
});

describe('getTierLabel', () => {
  it('returns correct labels for each tier', () => {
    expect(getTierLabel('parwa')).toBe('PARWA');
    expect(getTierLabel('high')).toBe('PARWA High');
  });
});

describe('getTierPrice', () => {
  it('returns correct price strings for each tier', () => {
    expect(getTierPrice('parwa')).toBe('$2,499/mo');
    expect(getTierPrice('high')).toBe('$3,999/mo');
  });
});

describe('getTierColor', () => {
  it('returns Tailwind gradient classes for each tier', () => {
    expect(getTierColor('parwa')).toContain('from-purple');
    expect(getTierColor('high')).toContain('from-orange');
  });
});

describe('TIER_LIMITS (via getFeatureMapForTier)', () => {
  it('parwa tier has ALL channels including sms/voice/video', () => {
    const parwa = getFeatureMapForTier('parwa');
    expect(parwa.chatChannel).toBe(true);
    expect(parwa.emailChannel).toBe(true);
    expect(parwa.smsChannel).toBe(true);
    expect(parwa.voiceChannel).toBe(true);
    expect(parwa.videoChannel).toBe(true);
  });

  // Mini removed 2026-07-26 — test deleted (pro-tier "sms+voice but NOT video" no longer exists; parwa has all channels)

  it('high tier has ALL channels including video', () => {
    const high = getFeatureMapForTier('high');
    expect(high.chatChannel).toBe(true);
    expect(high.emailChannel).toBe(true);
    expect(high.smsChannel).toBe(true);
    expect(high.voiceChannel).toBe(true);
    expect(high.videoChannel).toBe(true);
  });

  it('parwa tier has ALL agent types (capabilities are unified across tiers)', () => {
    const parwa = getFeatureMapForTier('parwa');
    expect(parwa.faqAgent).toBe(true);
    expect(parwa.refundAgent).toBe(true);
    expect(parwa.technicalAgent).toBe(true);
    expect(parwa.complaintAgent).toBe(true);
    expect(parwa.fraudDetection).toBe(true);
    expect(parwa.qualityCoach).toBe(true);
    expect(parwa.churnPrediction).toBe(true);
  });

  // Mini removed 2026-07-26 — test deleted (pro-tier "refund/technical/complaint but NOT fraud/quality/churn" no longer exists; parwa has all agents)

  it('high tier has ALL agent types including fraud/quality/churn', () => {
    const high = getFeatureMapForTier('high');
    expect(high.fraudDetection).toBe(true);
    expect(high.qualityCoach).toBe(true);
    expect(high.churnPrediction).toBe(true);
  });

  it('limits increase with tier: parwa < high', () => {
    expect(getFeatureMapForTier('parwa').maxAgents).toBe(5);
    expect(getFeatureMapForTier('high').maxAgents).toBe(8);

    expect(getFeatureMapForTier('parwa').maxKnowledgeDocs).toBe(500);
    expect(getFeatureMapForTier('high').maxKnowledgeDocs).toBe(-1); // unlimited

    expect(getFeatureMapForTier('parwa').maxApiKeys).toBe(5);
    expect(getFeatureMapForTier('high').maxApiKeys).toBe(-1);

    expect(getFeatureMapForTier('parwa').maxTeamMembers).toBe(10);
    expect(getFeatureMapForTier('high').maxTeamMembers).toBe(-1);
  });
});

describe('TIER_ORDER', () => {
  it('parwa < high', () => {
    expect(TIER_ORDER.parwa).toBeLessThan(TIER_ORDER.high);
  });
});

// ── Store Actions ──────────────────────────────────────────────────

describe('useVariantStore', () => {
  beforeEach(() => {
    // Reset both stores to initial state (variant-store.fetchTier delegates to billing-store)
    useVariantStore.getState().reset();
    useBillingStore.setState({
      currentTier: 'parwa',
      currentPrice: 2499,
      renewalDate: null,
      invoices: [],
      paymentMethods: [],
      usage: {
        ticketsUsed: 0,
        ticketsLimit: 1000,
        messagesUsed: 0,
        messagesLimit: 10000,
        storageUsed: 0,
        storageLimit: 500,
        apiCallsUsed: 0,
        apiCallsLimit: 5000,
      },
      isLoading: false,
      error: null,
    });
    mockFetch.mockReset();
  });

  describe('initial state', () => {
    it('defaults to parwa tier', () => {
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('is not loading initially', () => {
      expect(useVariantStore.getState().isLoading).toBe(false);
    });

    it('has no error initially', () => {
      expect(useVariantStore.getState().error).toBeNull();
    });

    it('has never been fetched', () => {
      expect(useVariantStore.getState().lastFetched).toBeNull();
    });

    it('has zeroed usage metrics', () => {
      const usage = useVariantStore.getState().usage;
      expect(usage.agentsUsed).toBe(0);
      expect(usage.docsUsed).toBe(0);
      expect(usage.apiKeysUsed).toBe(0);
      expect(usage.teamMembersUsed).toBe(0);
      expect(usage.ticketsThisMonth).toBe(0);
      expect(usage.messagesThisMonth).toBe(0);
    });
  });

  describe('setTier', () => {
    it('updates the tier', () => {
      useVariantStore.getState().setTier('parwa');
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('sets lastFetched timestamp', () => {
      const before = Date.now();
      useVariantStore.getState().setTier('high');
      const after = Date.now();
      const lastFetched = useVariantStore.getState().lastFetched;
      expect(lastFetched).toBeGreaterThanOrEqual(before);
      expect(lastFetched).toBeLessThanOrEqual(after);
    });
  });

  describe('getFeatureMap', () => {
    it('returns parwa feature map when tier is parwa', () => {
      useVariantStore.getState().setTier('parwa');
      const features = useVariantStore.getState().getFeatureMap();
      expect(features).toEqual(getFeatureMapForTier('parwa'));
    });

    it('returns high feature map when tier is high', () => {
      useVariantStore.getState().setTier('high');
      const features = useVariantStore.getState().getFeatureMap();
      expect(features).toEqual(getFeatureMapForTier('high'));
    });
  });

  describe('isFeatureAvailable', () => {
    it('returns true for parwa features on parwa tier', () => {
      useVariantStore.getState().setTier('parwa');
      expect(useVariantStore.getState().isFeatureAvailable('chatChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('faqAgent')).toBe(true);
    });

    // Mini removed 2026-07-26 — test deleted ("pro features locked on mini tier" no longer applies; parwa has all features)

    it('returns true for all AI features on parwa tier (capabilities are unified)', () => {
      useVariantStore.getState().setTier('parwa');
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('refundAgent')).toBe(true);
    });

    // Mini removed 2026-07-26 — test deleted ("high features locked on pro tier" no longer applies; parwa has all features)

    it('returns true for all features on high tier', () => {
      useVariantStore.getState().setTier('high');
      expect(useVariantStore.getState().isFeatureAvailable('videoChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('fraudDetection')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('qualityCoach')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('churnPrediction')).toBe(true);
    });

    it('returns true for numeric limit fields (they are always "available")', () => {
      useVariantStore.getState().setTier('parwa');
      expect(useVariantStore.getState().isFeatureAvailable('maxAgents')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('maxKnowledgeDocs')).toBe(true);
    });
  });

  describe('isAtLimit', () => {
    it('returns false when usage is below limit', () => {
      useVariantStore.getState().setTier('parwa');
      // Default usage is 0 for everything, parwa maxAgents is 5
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false);
    });

    it('returns true when usage equals limit', () => {
      useVariantStore.getState().setTier('parwa');
      // Set usage to exactly the parwa limit
      useVariantStore.setState({
        usage: {
          agentsUsed: 5,
          docsUsed: 500,
          apiKeysUsed: 5,
          teamMembersUsed: 10,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(true);
    });

    it('returns true when usage exceeds limit', () => {
      useVariantStore.getState().setTier('parwa');
      useVariantStore.setState({
        usage: {
          agentsUsed: 10,
          docsUsed: 1000,
          apiKeysUsed: 10,
          teamMembersUsed: 20,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(true);
    });

    it('returns false for unlimited resources on high tier (-1)', () => {
      useVariantStore.getState().setTier('high');
      useVariantStore.setState({
        usage: {
          agentsUsed: 8,
          docsUsed: 99999,
          apiKeysUsed: 99999,
          teamMembersUsed: 99999,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });
      // docs, apiKeys, teamMembers are unlimited on high (-1)
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false);
    });

    it('parwa tier respects its own limits', () => {
      useVariantStore.getState().setTier('parwa');
      useVariantStore.setState({
        usage: {
          agentsUsed: 5,
          docsUsed: 499,
          apiKeysUsed: 4,
          teamMembersUsed: 10,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(true);
    });
  });

  describe('fetchTier', () => {
    it('sets isLoading true during fetch', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => { resolvePromise = resolve; });
      mockFetch.mockReturnValueOnce(fetchPromise);

      const fetchTierPromise = useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().isLoading).toBe(true);

      resolvePromise!({
        ok: true,
        json: async () => ({ variant_tier: 'parwa' }),
      });
      await fetchTierPromise;
      expect(useVariantStore.getState().isLoading).toBe(false);
    });

    it('updates tier from API response (variant_tier field)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'parwa' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('updates tier from API response (tier field)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tier: 'high' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('high');
    });

    it('defaults to parwa on 404', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      useVariantStore.getState().setTier('high'); // Start at high
      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('defaults to parwa on 502/503 (backend down)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 502,
      });

      useVariantStore.getState().setTier('high');
      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('keeps tier aligned with billing store on network error (does not crash)', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      useVariantStore.getState().setTier('parwa');
      await useVariantStore.getState().fetchTier();
      // fetchBilling swallows the network error internally; variant-store.tier
      // reflects billing-store.currentTier (parwa default after beforeEach reset)
      expect(useVariantStore.getState().tier).toBe('parwa');
      expect(useVariantStore.getState().isLoading).toBe(false);
    });

    it('defaults to parwa on invalid tier value from API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tier: 'enterprise' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('auto-upgrades legacy "mini" tier value to parwa', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'mini' }),
      });

      await useVariantStore.getState().fetchTier();
      // Legacy mini records auto-upgrade to parwa via billing-store nameMap
      expect(useVariantStore.getState().tier).toBe('parwa');
    });

    it('sets lastFetched timestamp on success', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'parwa' }),
      });

      const before = Date.now();
      await useVariantStore.getState().fetchTier();
      const after = Date.now();
      const lastFetched = useVariantStore.getState().lastFetched;
      expect(lastFetched).toBeGreaterThanOrEqual(before);
      expect(lastFetched).toBeLessThanOrEqual(after);
    });
  });

  describe('fetchUsage', () => {
    it('updates usage metrics from API (mapped from billing usage)', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tickets_used: 150,
          tickets_limit: 1000,
          messages_used: 2500,
          messages_limit: 10000,
          storage_used: 250,
          storage_limit: 500,
          api_calls_used: 1000,
          api_calls_limit: 5000,
        }),
      });

      await useVariantStore.getState().fetchUsage();
      const usage = useVariantStore.getState().usage;
      // variant-store maps billing usage: agentsUsed=0, docsUsed=floor(storageUsed/10)
      expect(usage.agentsUsed).toBe(0);
      expect(usage.docsUsed).toBe(25); // 250/10
      expect(usage.apiKeysUsed).toBe(0);
      expect(usage.teamMembersUsed).toBe(0);
      expect(usage.ticketsThisMonth).toBe(150);
      expect(usage.messagesThisMonth).toBe(2500);
    });

    it('handles camelCase API response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ticketsUsed: 500,
          ticketsLimit: 1000,
          messagesUsed: 8000,
          messagesLimit: 10000,
          storageUsed: 100,
          storageLimit: 500,
          apiCallsUsed: 500,
          apiCallsLimit: 5000,
        }),
      });

      await useVariantStore.getState().fetchUsage();
      const usage = useVariantStore.getState().usage;
      expect(usage.ticketsThisMonth).toBe(500);
      expect(usage.messagesThisMonth).toBe(8000);
      expect(usage.docsUsed).toBe(10); // 100/10
    });

    it('silently fails on error (overwrites with billing defaults)', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      useVariantStore.setState({
        usage: {
          agentsUsed: 5,
          docsUsed: 30,
          apiKeysUsed: 2,
          teamMembersUsed: 1,
          ticketsThisMonth: 100,
          messagesThisMonth: 1000,
        },
      });

      await useVariantStore.getState().fetchUsage();
      // fetchBilling.fetchUsage silently swallows the error; variant.fetchUsage
      // still overwrites variant.usage with mapped billing.usage (defaults 0)
      expect(useVariantStore.getState().usage.agentsUsed).toBe(0);
      expect(useVariantStore.getState().usage.ticketsThisMonth).toBe(0);
    });

    it('silently fails on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await useVariantStore.getState().fetchUsage();
      // Usage stays at default zeros (billing.fetchUsage returns early on non-ok)
      expect(useVariantStore.getState().usage.agentsUsed).toBe(0);
    });
  });

  describe('reset', () => {
    it('resets all state to defaults', () => {
      useVariantStore.getState().setTier('high');
      useVariantStore.setState({
        isLoading: true,
        error: 'some error',
        usage: {
          agentsUsed: 10,
          docsUsed: 500,
          apiKeysUsed: 5,
          teamMembersUsed: 5,
          ticketsThisMonth: 100,
          messagesThisMonth: 2000,
        },
      });

      useVariantStore.getState().reset();

      const state = useVariantStore.getState();
      expect(state.tier).toBe('parwa');
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.lastFetched).toBeNull();
      expect(state.usage.agentsUsed).toBe(0);
    });
  });
});
