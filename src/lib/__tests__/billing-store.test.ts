/**
 * PARWA Billing Store — Unit Tests
 *
 * Tests fetchBilling, fetchInvoices, fetchUsage, changePlan,
 * cancelSubscription, and error handling.
 */

import { useBillingStore } from '@/lib/billing-store';

describe('useBillingStore', () => {
  beforeEach(() => {
    // Reset store to initial state
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

  describe('initial state', () => {
    it('defaults to mini tier at $999', () => {
      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);
    });

    it('has no renewal date initially', () => {
      expect(useBillingStore.getState().renewalDate).toBeNull();
    });

    it('has empty invoices and payment methods', () => {
      expect(useBillingStore.getState().invoices).toEqual([]);
      expect(useBillingStore.getState().paymentMethods).toEqual([]);
    });

    it('is not loading initially', () => {
      expect(useBillingStore.getState().isLoading).toBe(false);
    });

    it('has no error initially', () => {
      expect(useBillingStore.getState().error).toBeNull();
    });

    it('has default usage limits', () => {
      const usage = useBillingStore.getState().usage;
      expect(usage.ticketsLimit).toBe(1000);
      expect(usage.messagesLimit).toBe(10000);
      expect(usage.storageLimit).toBe(500);
      expect(usage.apiCallsLimit).toBe(5000);
    });
  });

  describe('fetchBilling', () => {
    it('fetches and sets tier from API (variant_tier field)', async () => {
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

    it('fetches tier from API (tier field)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tier: 'high',
          current_period_end: '2026-12-31',
        }),
      });

      await useBillingStore.getState().fetchBilling();

      expect(useBillingStore.getState().currentTier).toBe('high');
      expect(useBillingStore.getState().currentPrice).toBe(3999);
      expect(useBillingStore.getState().renewalDate).toBe('2026-12-31');
    });

    it('defaults to mini on error response (4xx/5xx)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await useBillingStore.getState().fetchBilling();

      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);
    });

    it('sets error on network failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await useBillingStore.getState().fetchBilling();

      expect(useBillingStore.getState().error).toBe('Network error');
      expect(useBillingStore.getState().isLoading).toBe(false);
    });

    it('sets isLoading during fetch', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => { resolvePromise = resolve; });
      (global.fetch as jest.Mock).mockReturnValueOnce(fetchPromise);

      const billingPromise = useBillingStore.getState().fetchBilling();
      expect(useBillingStore.getState().isLoading).toBe(true);

      resolvePromise!({
        ok: true,
        json: async () => ({ variant_tier: 'mini' }),
      });
      await billingPromise;
      expect(useBillingStore.getState().isLoading).toBe(false);
    });

    it('defaults to mini on invalid tier from API', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ tier: 'unknown' }),
      });

      await useBillingStore.getState().fetchBilling();

      // Invalid tier falls through to default pricing
      expect(useBillingStore.getState().currentPrice).toBe(999);
    });
  });

  describe('fetchInvoices', () => {
    it('fetches and maps invoices from array response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: 'inv_1',
            amount: 999,
            currency: 'USD',
            status: 'paid',
            date: '2026-01-01',
            description: 'Mini PARWA Monthly',
            download_url: 'https://example.com/invoice1.pdf',
          },
        ],
      });

      await useBillingStore.getState().fetchInvoices();

      const invoices = useBillingStore.getState().invoices;
      expect(invoices).toHaveLength(1);
      expect(invoices[0].id).toBe('inv_1');
      expect(invoices[0].amount).toBe(999);
      expect(invoices[0].status).toBe('paid');
      expect(invoices[0].downloadUrl).toBe('https://example.com/invoice1.pdf');
    });

    it('handles invoices wrapped in object response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          invoices: [
            { id: '2', amount: 2499, currency: 'USD', status: 'pending', date: '2026-02-01', description: 'Pro' },
          ],
        }),
      });

      await useBillingStore.getState().fetchInvoices();

      expect(useBillingStore.getState().invoices).toHaveLength(1);
      expect(useBillingStore.getState().invoices[0].amount).toBe(2499);
    });

    it('silently fails on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await useBillingStore.getState().fetchInvoices();

      // Should not throw, just silently fail
      expect(useBillingStore.getState().invoices).toEqual([]);
    });

    it('silently fails on non-ok response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await useBillingStore.getState().fetchInvoices();
      expect(useBillingStore.getState().invoices).toEqual([]);
    });
  });

  describe('fetchUsage', () => {
    it('fetches and maps usage from snake_case API', async () => {
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
      expect(usage.ticketsLimit).toBe(1000);
      expect(usage.messagesUsed).toBe(3000);
      expect(usage.apiCallsUsed).toBe(1000);
    });

    it('handles camelCase API response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ticketsUsed: 100,
          ticketsLimit: 500,
          messagesUsed: 2000,
          messagesLimit: 5000,
          storageUsed: 100,
          storageLimit: 250,
          apiCallsUsed: 500,
          apiCallsLimit: 2500,
        }),
      });

      await useBillingStore.getState().fetchUsage();

      const usage = useBillingStore.getState().usage;
      expect(usage.ticketsUsed).toBe(100);
      expect(usage.ticketsLimit).toBe(500);
    });

    it('silently fails on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      // Should not throw
      await expect(useBillingStore.getState().fetchUsage()).resolves.toBeUndefined();
    });
  });

  describe('changePlan', () => {
    it('updates tier and price on success', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'pro' }),
      });

      await useBillingStore.getState().changePlan('pro');

      expect(useBillingStore.getState().currentTier).toBe('pro');
      expect(useBillingStore.getState().currentPrice).toBe(2499);
    });

    it('sends PATCH request with new tier', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await useBillingStore.getState().changePlan('high');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/billing/subscription'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ variant_tier: 'high' }),
        })
      );
    });

    it('throws and sets error on failure', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 402,
      });

      await expect(useBillingStore.getState().changePlan('pro')).rejects.toThrow();
      expect(useBillingStore.getState().error).toContain('402');
    });

    it('throws and sets error on network failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      await expect(useBillingStore.getState().changePlan('pro')).rejects.toThrow('Network error');
      expect(useBillingStore.getState().error).toBe('Network error');
    });

    it('sets isLoading during plan change', async () => {
      let resolvePromise: (value: unknown) => void;
      const fetchPromise = new Promise((resolve) => { resolvePromise = resolve; });
      (global.fetch as jest.Mock).mockReturnValueOnce(fetchPromise);

      const changePromise = useBillingStore.getState().changePlan('pro');
      expect(useBillingStore.getState().isLoading).toBe(true);

      resolvePromise!({ ok: true, json: async () => ({}) });
      await changePromise;
      expect(useBillingStore.getState().isLoading).toBe(false);
    });
  });

  describe('cancelSubscription', () => {
    it('resets to mini tier on success', async () => {
      // Start at pro
      useBillingStore.setState({ currentTier: 'pro', currentPrice: 2499, renewalDate: '2026-12-31' });

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await useBillingStore.getState().cancelSubscription();

      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);
      expect(useBillingStore.getState().renewalDate).toBeNull();
    });

    it('sends DELETE request', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await useBillingStore.getState().cancelSubscription();

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/billing/subscription'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('throws and sets error on failure', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 403,
      });

      await expect(useBillingStore.getState().cancelSubscription()).rejects.toThrow();
      expect(useBillingStore.getState().error).toContain('403');
    });
  });

  describe('Billing lifecycle', () => {
    it('mini → upgrade to pro → cancel → back to mini', async () => {
      // Start at mini
      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);

      // Upgrade to pro
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ variant_tier: 'pro' }),
      });
      await useBillingStore.getState().changePlan('pro');
      expect(useBillingStore.getState().currentTier).toBe('pro');
      expect(useBillingStore.getState().currentPrice).toBe(2499);

      // Cancel subscription
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });
      await useBillingStore.getState().cancelSubscription();
      expect(useBillingStore.getState().currentTier).toBe('mini');
      expect(useBillingStore.getState().currentPrice).toBe(999);
    });
  });
});
