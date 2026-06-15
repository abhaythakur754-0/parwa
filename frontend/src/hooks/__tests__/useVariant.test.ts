/**
 * PARWA useVariant Hook — Unit Tests
 *
 * Tests the React hook wrapper around the variant Zustand store,
 * including auto-fetch, refetch, and computed properties.
 */

import { renderHook, act } from '@testing-library/react';
import { useVariant } from '@/hooks/useVariant';
import { useVariantStore } from '@/lib/variant-store';

describe('useVariant', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
  });

  describe('initial values', () => {
    it('returns default mini tier', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tier).toBe('mini');
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
    it('returns tierLabel for mini', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierLabel).toBe('Mini PARWA');
    });

    it('returns tierPrice for mini', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierPrice).toBe('$999/mo');
    });

    it('returns tierColor for mini', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.tierColor).toContain('from-blue');
    });

    it('updates computed properties when tier changes', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      expect(result.current.tierLabel).toBe('PARWA Pro');
      expect(result.current.tierPrice).toBe('$2,499/mo');
      expect(result.current.tierColor).toContain('from-purple');
    });
  });

  describe('isFeatureAvailable', () => {
    it('returns true for mini features on mini tier', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isFeatureAvailable('chatChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('emailChannel')).toBe(true);
    });

    it('returns false for pro features on mini tier', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isFeatureAvailable('smsChannel')).toBe(false);
      expect(result.current.isFeatureAvailable('voiceChannel')).toBe(false);
    });

    it('returns true for pro features on pro tier', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('pro');
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
    it('mini is at least mini', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isTierAtLeast('mini')).toBe(true);
    });

    it('mini is NOT at least pro', () => {
      const { result } = renderHook(() => useVariant());
      expect(result.current.isTierAtLeast('pro')).toBe(false);
    });

    it('pro is at least pro and mini but not high', () => {
      const { result } = renderHook(() => useVariant());

      act(() => {
        useVariantStore.getState().setTier('pro');
      });

      expect(result.current.isTierAtLeast('pro')).toBe(true);
      expect(result.current.isTierAtLeast('mini')).toBe(true);
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
    it('returns full feature map for current tier', () => {
      const { result } = renderHook(() => useVariant());
      const features = result.current.features;

      expect(features.chatChannel).toBe(true);
      expect(features.emailChannel).toBe(true);
      expect(features.smsChannel).toBe(false);
      expect(features.videoChannel).toBe(false);
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
      expect(features.maxAgents).toBe(50);
    });
  });
});
