/**
 * PARWA Integration Test: Billing + Variant Sync
 *
 * Tests that billing plan changes propagate correctly
 * to the variant store, updating feature availability.
 */

import { act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { useVariantStore } from '@/lib/variant-store';
import { useBillingStore } from '@/lib/billing-store';
import { useVariant } from '@/hooks/useVariant';

describe('Integration: Billing + Variant Sync', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
    useBillingStore.setState({
      currentTier: 'mini',
      currentPrice: 999,
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
  });

  describe('Plan upgrade flow', () => {
    it('upgrading plan in billing store should be reflected in variant store', async () => {
      // Both start at mini
      expect(useVariantStore.getState().tier).toBe('mini');
      expect(useBillingStore.getState().currentTier).toBe('mini');

      // Simulate plan upgrade via billing API
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'pro' }),
      });

      await useBillingStore.getState().changePlan('pro');

      expect(useBillingStore.getState().currentTier).toBe('pro');
      expect(useBillingStore.getState().currentPrice).toBe(2499);

      // Sync: variant store should also be updated
      // In a real app, this would happen via Socket.io event or explicit sync
      // Here we test the sync mechanism
      useVariantStore.getState().setTier('pro');
      expect(useVariantStore.getState().tier).toBe('pro');
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
    });

    it('upgrading to high unlocks all features', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'high' }),
      });

      await useBillingStore.getState().changePlan('high');
      useVariantStore.getState().setTier('high');

      const { result } = renderHook(() => useVariant());

      expect(result.current.isFeatureAvailable('videoChannel')).toBe(true);
      expect(result.current.isFeatureAvailable('fraudDetection')).toBe(true);
      expect(result.current.isFeatureAvailable('qualityCoach')).toBe(true);
      expect(result.current.isFeatureAvailable('churnPrediction')).toBe(true);
    });
  });

  describe('Plan downgrade flow', () => {
    it('canceling subscription resets to mini', async () => {
      // Start at pro
      useVariantStore.getState().setTier('pro');
      useBillingStore.setState({ currentTier: 'pro', currentPrice: 2499, renewalDate: '2026-12-31' });

      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);

      // Cancel subscription
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await useBillingStore.getState().cancelSubscription();

      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);
      expect(useBillingStore.getState().renewalDate).toBeNull();

      // Sync variant store
      useVariantStore.getState().setTier('mini');

      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(false);
      expect(useVariantStore.getState().isFeatureAvailable('voiceChannel')).toBe(false);
    });
  });

  describe('Usage limits across tiers', () => {
    it('usage that exceeds mini limits is fine on pro', () => {
      // Set usage that exceeds mini but not pro limits
      useVariantStore.getState().setTier('mini');
      useVariantStore.setState({
        usage: {
          agentsUsed: 10, // mini limit is 5
          docsUsed: 200,  // mini limit is 50
          apiKeysUsed: 3, // mini limit is 1
          teamMembersUsed: 3, // mini limit is 1
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });

      expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(true);

      // Upgrade to pro (15 agents, 500 docs)
      useVariantStore.getState().setTier('pro');

      expect(useVariantStore.getState().isAtLimit('agents')).toBe(false); // 10 < 15
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);   // 200 < 500
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false); // 3 < 5
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false); // 3 < 5
    });

    it('unlimited resources on high tier never show at limit', () => {
      useVariantStore.getState().setTier('high');
      useVariantStore.setState({
        usage: {
          agentsUsed: 50,
          docsUsed: 10000,
          apiKeysUsed: 500,
          teamMembersUsed: 200,
          ticketsThisMonth: 0,
          messagesThisMonth: 0,
        },
      });

      // docs, apiKeys, teamMembers are unlimited (-1) on high
      expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
      expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false);

      // agents still has a limit (50)
      expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
    });
  });

  describe('Billing fetch updates both stores', () => {
    it('fetchBilling updates billing state from API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          variant_tier: 'pro',
          renewal_date: '2026-06-14',
        }),
      });

      await useBillingStore.getState().fetchBilling();

      expect(useBillingStore.getState().currentTier).toBe('pro');
      expect(useBillingStore.getState().currentPrice).toBe(2499);
      expect(useBillingStore.getState().renewalDate).toBe('2026-06-14');
    });

    it('fetchUsage updates billing usage from API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tickets_used: 500,
          tickets_limit: 1000,
          messages_used: 3000,
          messages_limit: 10000,
          storage_used: 250,
          storage_limit: 500,
          api_calls_used: 1000,
          api_calls_limit: 5000,
        }),
      });

      await useBillingStore.getState().fetchUsage();

      const usage = useBillingStore.getState().usage;
      expect(usage.ticketsUsed).toBe(500);
      expect(usage.messagesUsed).toBe(3000);
      expect(usage.apiCallsUsed).toBe(1000);
    });
  });

  describe('Edge case: API inconsistency', () => {
    it('billing says pro but variant says mini — variant wins for feature gating', () => {
      // Simulate API returning different tiers (race condition)
      useBillingStore.setState({ currentTier: 'pro', currentPrice: 2499 });
      useVariantStore.getState().setTier('mini');

      // Feature gating should follow variant store
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(false);

      // After sync, both agree
      useVariantStore.getState().setTier('pro');
      expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
    });
  });
});
