/**
 * PARWA Variant Store — Unit Tests
 *
 * Tests tier logic, feature maps, usage limits, fetchTier,
 * isAtLimit, and all helper functions.
 */

import { useVariantStore, isTierAtLeast, getTierLabel, getTierPrice, getTierColor, TIER_FEATURES, TIER_ORDER, VariantTier } from '@/lib/variant-store';

// ── Helper Functions ──────────────────────────────────────────────

describe('isTierAtLeast', () => {
  it('returns true when current tier equals required tier', () => {
    expect(isTierAtLeast('mini', 'mini')).toBe(true);
    expect(isTierAtLeast('pro', 'pro')).toBe(true);
    expect(isTierAtLeast('high', 'high')).toBe(true);
  });

  it('returns true when current tier exceeds required tier', () => {
    expect(isTierAtLeast('pro', 'mini')).toBe(true);
    expect(isTierAtLeast('high', 'mini')).toBe(true);
    expect(isTierAtLeast('high', 'pro')).toBe(true);
  });

  it('returns false when current tier is below required tier', () => {
    expect(isTierAtLeast('mini', 'pro')).toBe(false);
    expect(isTierAtLeast('mini', 'high')).toBe(false);
    expect(isTierAtLeast('pro', 'high')).toBe(false);
  });
});

describe('getTierLabel', () => {
  it('returns correct labels for each tier', () => {
    expect(getTierLabel('mini')).toBe('Mini PARWA');
    expect(getTierLabel('pro')).toBe('PARWA Pro');
    expect(getTierLabel('high')).toBe('PARWA High');
  });
});

describe('getTierPrice', () => {
  it('returns correct price strings for each tier', () => {
    expect(getTierPrice('mini')).toBe('$999/mo');
    expect(getTierPrice('pro')).toBe('$2,499/mo');
    expect(getTierPrice('high')).toBe('$3,999/mo');
  });
});

describe('getTierColor', () => {
  it('returns Tailwind gradient classes for each tier', () => {
    expect(getTierColor('mini')).toContain('from-blue');
    expect(getTierColor('pro')).toContain('from-purple');
    expect(getTierColor('high')).toContain('from-orange');
  });
});

describe('TIER_FEATURES', () => {
  it('mini tier has chat+email channels but NOT sms/voice/video', () => {
    const mini = TIER_FEATURES.mini;
    expect(mini.chatChannel).toBe(true);
    expect(mini.emailChannel).toBe(true);
    expect(mini.smsChannel).toBe(false);
    expect(mini.voiceChannel).toBe(false);
    expect(mini.videoChannel).toBe(false);
  });

  it('pro tier adds sms+voice but NOT video', () => {
    const pro = TIER_FEATURES.pro;
    expect(pro.chatChannel).toBe(true);
    expect(pro.emailChannel).toBe(true);
    expect(pro.smsChannel).toBe(true);
    expect(pro.voiceChannel).toBe(true);
    expect(pro.videoChannel).toBe(false);
  });

  it('high tier has ALL channels including video', () => {
    const high = TIER_FEATURES.high;
    expect(high.chatChannel).toBe(true);
    expect(high.emailChannel).toBe(true);
    expect(high.smsChannel).toBe(true);
    expect(high.voiceChannel).toBe(true);
    expect(high.videoChannel).toBe(true);
  });

  it('mini tier has only faq agent', () => {
    const mini = TIER_FEATURES.mini;
    expect(mini.faqAgent).toBe(true);
    expect(mini.refundAgent).toBe(false);
    expect(mini.technicalAgent).toBe(false);
    expect(mini.complaintAgent).toBe(false);
    expect(mini.fraudDetection).toBe(false);
    expect(mini.qualityCoach).toBe(false);
    expect(mini.churnPrediction).toBe(false);
  });

  it('pro tier adds refund/technical/complaint agents but NOT fraud/quality/churn', () => {
    const pro = TIER_FEATURES.pro;
    expect(pro.faqAgent).toBe(true);
    expect(pro.refundAgent).toBe(true);
    expect(pro.technicalAgent).toBe(true);
    expect(pro.complaintAgent).toBe(true);
    expect(pro.fraudDetection).toBe(false);
    expect(pro.qualityCoach).toBe(false);
    expect(pro.churnPrediction).toBe(false);
  });

  it('high tier has ALL agent types including fraud/quality/churn', () => {
    const high = TIER_FEATURES.high;
    expect(high.fraudDetection).toBe(true);
    expect(high.qualityCoach).toBe(true);
    expect(high.churnPrediction).toBe(true);
  });

  it('limits increase with tier: mini < pro < high', () => {
    expect(TIER_FEATURES.mini.maxAgents).toBe(5);
    expect(TIER_FEATURES.pro.maxAgents).toBe(15);
    expect(TIER_FEATURES.high.maxAgents).toBe(50);

    expect(TIER_FEATURES.mini.maxKnowledgeDocs).toBe(50);
    expect(TIER_FEATURES.pro.maxKnowledgeDocs).toBe(500);
    expect(TIER_FEATURES.high.maxKnowledgeDocs).toBe(-1); // unlimited

    expect(TIER_FEATURES.mini.maxApiKeys).toBe(1);
    expect(TIER_FEATURES.pro.maxApiKeys).toBe(5);
    expect(TIER_FEATURES.high.maxApiKeys).toBe(-1);

    expect(TIER_FEATURES.mini.maxTeamMembers).toBe(1);
    expect(TIER_FEATURES.pro.maxTeamMembers).toBe(5);
    expect(TIER_FEATURES.high.maxTeamMembers).toBe(-1);
  });
});

describe('TIER_ORDER', () => {
  it('mini < pro < high', () => {
    expect(TIER_ORDER.mini).toBeLessThan(TIER_ORDER.pro);
    expect(TIER_ORDER.pro).toBeLessThan(TIER_ORDER.high);
  });
});

// ── Store Actions ──────────────────────────────────────────────────

describe('useVariantStore', () => {
  beforeEach(() => {
    // Reset store to initial state before each test
    useVariantStore.getState().reset();
  });

  describe('initial state', () => {
    it('defaults to mini tier', () => {
      expect(useVariantStore.getState().tier).toBe('mini');
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
      useVariantStore.getState().setTier('pro');
      expect(useVariantStore.getState().tier).toBe('pro');
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
    it('returns mini feature map when tier is mini', () => {
      useVariantStore.getState().setTier('mini');
      const features = useVariantStore.getState().getFeatureMap();
      expect(features).toEqual(TIER_FEATURES.mini);
    });

    it('returns pro feature map when tier is pro', () => {
      useVariantStore.getState().setTier('pro');
      const features = useVariantStore.getState().getFeatureMap();
      expect(features).toEqual(TIER_FEATURES.pro);
    });

    it('returns high feature map when tier is high', () => {
      useVariantStore.getState().setTier('high');
      const features = useVariantStore.getState().getFeatureMap();
      expect(features).toEqual(TIER_FEATURES.high);
    });
  });

  describe('isFeatureAvailable', () => {
    it('returns true for mini features on mini tier', () => {
      useVariantStore.getState().setTier('mini');
      expect(useVariantStore.getState().isFeatureAvailable('chatChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('faqAgent')).toBe(true);
    });

    it('returns false for pro features on mini tier', () => {
      useVariantStore.getState().setTier('mini');
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(false);
      expect(useVariantStore.getState().isFeatureAvailable('voiceChannel')).toBe(false);
      expect(useVariantStore.getState().isFeatureAvailable('refundAgent')).toBe(false);
    });

    it('returns true for pro features on pro tier', () => {
      useVariantStore.getState().setTier('pro');
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('refundAgent')).toBe(true);
    });

    it('returns false for high features on pro tier', () => {
      useVariantStore.getState().setTier('pro');
      expect(useVariantStore.getState().isFeatureAvailable('videoChannel')).toBe(false);
      expect(useVariantStore.getState().isFeatureAvailable('fraudDetection')).toBe(false);
    });

    it('returns true for all features on high tier', () => {
      useVariantStore.getState().setTier('high');
      expect(useVariantStore.getState().isFeatureAvailable('videoChannel')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('fraudDetection')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('qualityCoach')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('churnPrediction')).toBe(true);
    });

    it('returns true for numeric limit fields (they are always "available")', () => {
      useVariantStore.getState().setTier('mini');
      expect(useVariantStore.getState().isFeatureAvailable('maxAgents')).toBe(true);
      expect(useVariantStore.getState().isFeatureAvailable('maxKnowledgeDocs')).toBe(true);
    });
  });

  describe('isAtLimit', () => {
    it('returns false when usage is below limit', () => {
      useVariantStore.getState().setTier('mini');
      // Default usage is 0 for everything, mini maxAgents is 5
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false);
    });

    it('returns true when usage equals limit', () => {
      useVariantStore.getState().setTier('mini');
      // Set usage to exactly the mini limit
      useVariantStore.setState({
        usage: {
          agentsUsed: 5,
          docsUsed: 50,
          apiKeysUsed: 1,
          teamMembersUsed: 1,
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
      useVariantStore.getState().setTier('mini');
      useVariantStore.setState({
        usage: {
          agentsUsed: 10,
          docsUsed: 100,
          apiKeysUsed: 3,
          teamMembersUsed: 5,
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
          agentsUsed: 50,
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

    it('pro tier respects its own limits', () => {
      useVariantStore.getState().setTier('pro');
      useVariantStore.setState({
        usage: {
          agentsUsed: 15,
          docsUsed: 499,
          apiKeysUsed: 4,
          teamMembersUsed: 5,
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
      (global.fetch as jest.Mock).mockReturnValueOnce(fetchPromise);

      const fetchTierPromise = useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().isLoading).toBe(true);

      resolvePromise!({
        ok: true,
        json: async () => ({ variant_tier: 'pro' }),
      });
      await fetchTierPromise;
      expect(useVariantStore.getState().isLoading).toBe(false);
    });

    it('updates tier from API response (variant_tier field)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'pro' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('pro');
    });

    it('updates tier from API response (tier field)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tier: 'high' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('high');
    });

    it('defaults to mini on 404', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 404,
      });

      useVariantStore.getState().setTier('pro'); // Start at pro
      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('mini');
    });

    it('defaults to mini on 502/503 (backend down)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 502,
      });

      useVariantStore.getState().setTier('high');
      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('mini');
    });

    it('keeps existing tier on network error (does not reset)', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      useVariantStore.getState().setTier('pro');
      await useVariantStore.getState().fetchTier();
      // Should keep pro, not reset to mini
      expect(useVariantStore.getState().tier).toBe('pro');
      expect(useVariantStore.getState().error).toBe('Network error');
    });

    it('defaults to mini on invalid tier value from API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tier: 'enterprise' }),
      });

      await useVariantStore.getState().fetchTier();
      expect(useVariantStore.getState().tier).toBe('mini');
    });

    it('sets lastFetched timestamp on success', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'mini' }),
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
    it('updates usage metrics from API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agents_used: 3,
          docs_used: 25,
          api_keys_used: 1,
          team_members_used: 1,
          tickets_this_month: 150,
          messages_this_month: 2500,
        }),
      });

      await useVariantStore.getState().fetchUsage();
      const usage = useVariantStore.getState().usage;
      expect(usage.agentsUsed).toBe(3);
      expect(usage.docsUsed).toBe(25);
      expect(usage.apiKeysUsed).toBe(1);
      expect(usage.teamMembersUsed).toBe(1);
      expect(usage.ticketsThisMonth).toBe(150);
      expect(usage.messagesThisMonth).toBe(2500);
    });

    it('handles camelCase API response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          agentsUsed: 10,
          docsUsed: 200,
          apiKeysUsed: 3,
          teamMembersUsed: 4,
          ticketsThisMonth: 500,
          messagesThisMonth: 8000,
        }),
      });

      await useVariantStore.getState().fetchUsage();
      const usage = useVariantStore.getState().usage;
      expect(usage.agentsUsed).toBe(10);
      expect(usage.docsUsed).toBe(200);
    });

    it('silently fails on error (keeps existing usage)', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

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
      // Should keep existing usage
      expect(useVariantStore.getState().usage.agentsUsed).toBe(5);
    });

    it('silently fails on non-ok response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await useVariantStore.getState().fetchUsage();
      // Usage stays at default zeros
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
      expect(state.tier).toBe('mini');
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(state.lastFetched).toBeNull();
      expect(state.usage.agentsUsed).toBe(0);
    });
  });
});
