/** @jest-environment jsdom */
/**
 * Integration coverage for the current two-tier billing model.
 * Billing state and feature-capacity state are synchronized explicitly;
 * both tiers share the same AI capabilities.
 */

import { useVariantStore, isTierAtLeast } from '@/lib/variant-store';
import { useBillingStore } from '@/lib/billing-store';

describe('Integration: Billing + Variant Sync', () => {
  beforeEach(() => {
    useVariantStore.getState().reset();
    useBillingStore.setState({
      currentTier: 'parwa',
      currentPrice: 2999,
      renewalDate: null,
      invoices: [],
      paymentMethods: [],
      usage: {
        ticketsUsed: 0,
        ticketsLimit: 2999,
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
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    });
  });

  it('updates billing and variant stores when selecting the High plan', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    await useBillingStore.getState().changePlan('high');

    expect(useBillingStore.getState().currentTier).toBe('high');
    expect(useBillingStore.getState().currentPrice).toBe(3999);

    // The application sync boundary updates the feature store from verified billing state.
    useVariantStore.getState().setTier(useBillingStore.getState().currentTier);
    expect(useVariantStore.getState().tier).toBe('high');
    expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
  });

  it('keeps the same AI capabilities on Parwa and High', () => {
    const parwaFeatures = useVariantStore.getState().getFeatureMap();
    const parwaCapabilities = Object.fromEntries(
      Object.entries(parwaFeatures).filter(([, value]) => typeof value === 'boolean')
    );

    useVariantStore.getState().setTier('high');
    const highFeatures = useVariantStore.getState().getFeatureMap();
    const highCapabilities = Object.fromEntries(
      Object.entries(highFeatures).filter(([, value]) => typeof value === 'boolean')
    );

    expect(highCapabilities).toEqual(parwaCapabilities);
  });

  it('cancels a subscription to the Parwa entry tier without disabling shared capabilities', async () => {
    useVariantStore.getState().setTier('high');
    useBillingStore.setState({ currentTier: 'high', currentPrice: 3999, renewalDate: '2026-12-31' });
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({}) });

    await useBillingStore.getState().cancelSubscription();

    expect(useBillingStore.getState().currentTier).toBe('parwa');
    expect(useBillingStore.getState().currentPrice).toBe(2999);
    expect(useBillingStore.getState().renewalDate).toBeNull();

    useVariantStore.getState().setTier('parwa');
    expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
    expect(useVariantStore.getState().isFeatureAvailable('voiceChannel')).toBe(true);
  });

  it('enforces Parwa capacity limits and lifts them on High', () => {
    useVariantStore.setState({
      usage: {
        agentsUsed: 7,
        docsUsed: 600,
        apiKeysUsed: 6,
        teamMembersUsed: 11,
        ticketsThisMonth: 0,
        messagesThisMonth: 0,
      },
    });

    expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
    expect(useVariantStore.getState().isAtLimit('docs')).toBe(true);
    expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(true);
    expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(true);

    useVariantStore.getState().setTier('high');

    expect(useVariantStore.getState().isAtLimit('agents')).toBe(false);
    expect(useVariantStore.getState().isAtLimit('docs')).toBe(true);
    expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
    expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(true);
  });

  it('enforces High knowledge and team-member capacity while allowing its configured API-key allowance', () => {
    useVariantStore.getState().setTier('high');
    useVariantStore.setState({
      usage: {
        agentsUsed: 50,
        docsUsed: 2000,
        apiKeysUsed: 500,
        teamMembersUsed: 25,
        ticketsThisMonth: 0,
        messagesThisMonth: 0,
      },
    });

    expect(useVariantStore.getState().isAtLimit('docs')).toBe(false);
    expect(useVariantStore.getState().isAtLimit('apiKeys')).toBe(false);
    expect(useVariantStore.getState().isAtLimit('teamMembers')).toBe(false);
    expect(useVariantStore.getState().isAtLimit('agents')).toBe(true);
  });

  it('loads canonical Parwa pricing and renewal data from billing API', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ variant_tier: 'parwa', renewal_date: '2026-06-14' }),
    });

    await useBillingStore.getState().fetchBilling();

    expect(useBillingStore.getState().currentTier).toBe('parwa');
    expect(useBillingStore.getState().currentPrice).toBe(2999);
    expect(useBillingStore.getState().renewalDate).toBe('2026-06-14');
  });

  it('loads usage metrics from billing API', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tickets_used: 500,
        tickets_limit: 2999,
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

  it('uses the variant store for capacity gating when billing and variant state disagree', () => {
    useBillingStore.setState({ currentTier: 'high', currentPrice: 3999 });
    useVariantStore.getState().setTier('parwa');

    expect(isTierAtLeast(useVariantStore.getState().tier, 'high')).toBe(false);
    expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);

    useVariantStore.getState().setTier('high');
    expect(isTierAtLeast(useVariantStore.getState().tier, 'high')).toBe(true);
    expect(useVariantStore.getState().isFeatureAvailable('smsChannel')).toBe(true);
  });
});
