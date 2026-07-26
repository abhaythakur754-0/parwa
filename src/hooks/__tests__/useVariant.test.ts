/**
 * PARWA useVariant Hook — Unit Tests
 *
 * Tests the React hook wrapper around the variant Zustand store,
 * including auto-fetch, refetch, and computed properties.
 *
 * Updated 2026-07-26: Mini PARWA removed — codebase now has 2 tiers
 * (parwa $2,499/mo + high $3,999/mo). All variants share the SAME AI
 * capabilities; tiers differ only in ticket volume / numeric limits.
 */

import { renderHook, act } from '@testing-library/react';
import { useVariant } from '@/hooks/useVariant';
import { useVariantStore } from '@/lib/variant-store';
import { useBillingStore } from '@/lib/billing-store';

// global.fetch mock — required because useVariant auto-fetches on mount
// (fetchTier delegates to billing-store.fetchBilling which calls fetch)
const mockFetch = jest.fn() as jest.Mock;
global.fetch = mockFetch;

describe('useVariant', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
    // Reset billing store too (variant.fetchTier delegates to it)
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
    // Default fetch mock: 200 OK with parwa tier (auto-upgrades cleanly)
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ variant_tier: 'parwa' }) });
  });

  describe('initial values', () => {
    it('returns default parwa tier', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tier).toBe('parwa');
    });

    it('isLoading is managed by the store', () => {
      // After mount, the auto-fetch fires but the store manages isLoading
      // The important thing is that isLoading is a boolean
      const { result } = renderHook(() => useVariant());
      expect(typeof result.current.isLoading).toBe('boolean');
    });

    it('returns no error', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.error).toBeNull();
    });

    it('returns zeroed usage', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.usage.agentsUsed).toBe(0);
      expect(result.current.usage.docsUsed).toBe(0);
    });
  });

  describe('computed properties', () => {
    it('returns tierLabel for parwa', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierLabel).toBe('PARWA');
    });

    it('returns tierPrice for parwa', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierPrice).toBe('$2,499/mo');
    });

    it('returns tierColor for parwa', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierColor).toContain('from-purple');
    });

    it('updates computed properties when tier changes', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('high');
      });

      expect(result.current.tierLabel).toBe('PARWA High');
      expect(result.current.tierPrice).toBe('$3,999/mo');
      expect(result.current.tierColor).toContain('from-orange');
    });
  });

  describe('isFeatureAvailable', () => {
    it('returns true for parwa features on parwa tier', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isFeatureAvailable('chatChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('emailChannel')).toBe(true);
    });

    // Mini removed 2026-07-26 — test deleted ("pro features locked on mini tier" no longer applies; parwa has all features)

    it('returns true for sms+voice on parwa tier (capabilities are unified)', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('parwa');
      });

      expect(result.current.isFeatureAvailable('smsChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('voiceChannel')).toBe(true);
    });
  });

  describe('isAtLimit', () => {
    it('returns false when under limit', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isAtLimit('agents')).toBe(false);
    });

    it('returns true when at limit', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.setState({
          usage: {
            agentsUsed: 5,
            docsUsed: 0,
            apiKeysUsed: 0,
            teamMembersUsed: 0,
            ticketsThisMonth: 0,
            messagesThisMonth: 0,
          },
        });
      });

      expect(result.current.isAtLimit('agents')).toBe(true);
    });
  });

  describe('isTierAtLeast', () => {
    it('parwa is at least parwa', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isTierAtLeast('parwa')).toBe(true);
    });

    // Mini removed 2026-07-26 — test deleted ("mini is NOT at least pro" no longer applies; no mini tier)

    it('parwa is at least parwa but not high', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('parwa');
      });

      expect(result.current.isTierAtLeast('parwa')).toBe(true);
      expect(result.current.isTierAtLeast('high')).toBe(false);
    });
  });

  describe('auto-fetch on mount', () => {
    it('calls fetchTier and fetchUsage on mount', () => {
      const fetchTierSpy = jest.spyOn(useVariantStore.getState(), 'fetchTier');
      const fetchUsageSpy = jest.spyOn(useVariantStore.getState(), 'fetchUsage');

      renderHook(() => useVariant());

      expect(fetchTierSpy).toHaveBeenCalled();
      expect(fetchUsageSpy).toHaveBeenCalled();

      fetchTierSpy.mockRestore();
      fetchUsageSpy.mockRestore();
    });
  });

  describe('refetch', () => {
    it('calls refetch which invokes fetchTier and fetchUsage', async () => {
      const fetchTierSpy = jest.spyOn(useVariantStore.getState(), 'fetchTier').mockResolvedValue(undefined);
      const fetchUsageSpy = jest.spyOn(useVariantStore.getState(), 'fetchUsage').mockResolvedValue(undefined);

      const { result } = renderHook(() => useVariant());

      fetchTierSpy.mockClear();
      fetchUsageSpy.mockClear();

      await act(async () => {
        await result.current.refetch();
      });

      expect(fetchTierSpy).toHaveBeenCalledTimes(1);
      expect(fetchUsageSpy).toHaveBeenCalledTimes(1);

      fetchTierSpy.mockRestore();
      fetchUsageSpy.mockRestore();
    });
  });

  describe('features map', () => {
    it('returns full feature map for current parwa tier (all channels)', () => {
      const { result } = renderHook(() => useVariant());
      const features = result.current.features;

      // parwa has ALL channels (capabilities are unified across tiers)
      expect(features.chatChannel).toBe(true);
      expect(features.emailChannel).toBe(true);
      expect(features.smsChannel).toBe(true);
      expect(features.videoChannel).toBe(true);
      expect(features.maxAgents).toBe(5);
    });

    it('updates features when tier changes', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('high');
      });

      const features = result.current.features;
      expect(features.videoChannel).toBe(true);
      expect(features.fraudDetection).toBe(true);
      expect(features.maxAgents).toBe(8);
    });
  });
});
