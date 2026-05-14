/**
 * PARWA Day 5 Unit Tests — MFA Store
 *
 * Tests the Zustand MFA store: initiateSetup, verifyAndEnroll,
 * verifyLogin, disableMfa, error handling, demo mode fallback.
 */

import { useMFAStore } from '@/lib/mfa-store';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Helper to reset store between tests
function resetStore() {
  useMFAStore.setState({
    status: 'idle',
    setupData: null,
    isEnrolled: false,
    error: null,
  });
}

describe('MFA Store', () => {
  beforeEach(() => {
    resetStore();
    mockFetch.mockReset();
  });

  // ── Initial State ──────────────────────────────────────────────────

  describe('initial state', () => {
    it('starts with idle status', () => {
      expect(useMFAStore.getState().status).toBe('idle');
    });

    it('starts with no setup data', () => {
      expect(useMFAStore.getState().setupData).toBeNull();
    });

    it('starts not enrolled', () => {
      expect(useMFAStore.getState().isEnrolled).toBe(false);
    });

    it('starts with no error', () => {
      expect(useMFAStore.getState().error).toBeNull();
    });
  });

  // ── initiateSetup ──────────────────────────────────────────────────

  describe('initiateSetup', () => {
    it('sets status to enrolling', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          secret: 'ABC123',
          qr_code_url: 'https://qr.example.com',
          backup_codes: ['code1', 'code2'],
        }),
      });

      await useMFAStore.getState().initiateSetup();
      expect(useMFAStore.getState().status).toBe('enrolling');
    });

    it('stores setup data from API response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          secret: 'ABC123',
          qr_code_url: 'https://qr.example.com/mfa',
          backup_codes: ['aa1-bb2', 'cc3-dd4'],
        }),
      });

      await useMFAStore.getState().initiateSetup();
      const data = useMFAStore.getState().setupData;
      expect(data).not.toBeNull();
      expect(data?.secret).toBe('ABC123');
      expect(data?.qrCodeUrl).toBe('https://qr.example.com/mfa');
      expect(data?.backupCodes).toEqual(['aa1-bb2', 'cc3-dd4']);
    });

    it('handles camelCase API response keys', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          secret: 'XYZ789',
          qrCodeUrl: 'https://qr.example.com/alt',
          backupCodes: ['ee5-ff6'],
        }),
      });

      await useMFAStore.getState().initiateSetup();
      const data = useMFAStore.getState().setupData;
      expect(data?.secret).toBe('XYZ789');
      expect(data?.qrCodeUrl).toBe('https://qr.example.com/alt');
      expect(data?.backupCodes).toEqual(['ee5-ff6']);
    });

    it('generates demo data when backend returns 404', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

      await useMFAStore.getState().initiateSetup();
      const data = useMFAStore.getState().setupData;
      expect(data).not.toBeNull();
      expect(data?.secret).toBeTruthy();
      expect(data?.qrCodeUrl).toContain('otpauth');
      expect(data?.backupCodes.length).toBeGreaterThan(0);
      expect(useMFAStore.getState().status).toBe('enrolling');
    });

    it('generates demo data on network error', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      await useMFAStore.getState().initiateSetup();
      const data = useMFAStore.getState().setupData;
      expect(data).not.toBeNull();
      expect(data?.secret).toBeTruthy();
      expect(useMFAStore.getState().status).toBe('enrolling');
    });

    it('sets error on non-404 server error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
      });

      await useMFAStore.getState().initiateSetup();
      expect(useMFAStore.getState().status).toBe('error');
      expect(useMFAStore.getState().error).toBe('Server error');
    });

    it('clears previous error on new setup attempt', async () => {
      useMFAStore.setState({ error: 'Previous error' });
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      await useMFAStore.getState().initiateSetup();
      expect(useMFAStore.getState().error).toBeNull();
    });
  });

  // ── verifyAndEnroll ────────────────────────────────────────────────

  describe('verifyAndEnroll', () => {
    it('returns false and sets error for short codes', async () => {
      const result = await useMFAStore.getState().verifyAndEnroll('12');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Please enter a valid verification code');
    });

    it('returns false for empty code', async () => {
      const result = await useMFAStore.getState().verifyAndEnroll('');
      expect(result).toBe(false);
    });

    it('sets status to verifying during API call', () => {
      mockFetch.mockReturnValueOnce(new Promise(() => {})); // never resolves
      useMFAStore.getState().verifyAndEnroll('123456');
      expect(useMFAStore.getState().status).toBe('verifying');
    });

    it('marks enrolled on successful verification', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      const result = await useMFAStore.getState().verifyAndEnroll('123456');
      expect(result).toBe(true);
      expect(useMFAStore.getState().status).toBe('enrolled');
      expect(useMFAStore.getState().isEnrolled).toBe(true);
    });

    it('accepts 6-digit code in demo mode (404)', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

      const result = await useMFAStore.getState().verifyAndEnroll('654321');
      expect(result).toBe(true);
      expect(useMFAStore.getState().isEnrolled).toBe(true);
    });

    it('rejects non-6-digit code in demo mode', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

      const result = await useMFAStore.getState().verifyAndEnroll('1234');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Invalid verification code');
    });

    it('accepts 6-digit code on network error', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const result = await useMFAStore.getState().verifyAndEnroll('111111');
      expect(result).toBe(true);
      expect(useMFAStore.getState().isEnrolled).toBe(true);
    });

    it('sets error on server rejection', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Code expired' }),
      });

      const result = await useMFAStore.getState().verifyAndEnroll('123456');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Code expired');
    });
  });

  // ── verifyLogin ────────────────────────────────────────────────────

  describe('verifyLogin', () => {
    it('returns false for empty code', async () => {
      const result = await useMFAStore.getState().verifyLogin('');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Please enter a verification code');
    });

    it('successfully verifies login with TOTP code', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      const result = await useMFAStore.getState().verifyLogin('123456');
      expect(result).toBe(true);
      expect(useMFAStore.getState().status).toBe('idle');
    });

    it('successfully verifies login with backup code', async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({}) });

      const result = await useMFAStore.getState().verifyLogin('aa1-bb2', true);
      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/mfa/backup'),
        expect.objectContaining({
          body: JSON.stringify({ backup_code: 'aa1-bb2' }),
        })
      );
    });

    it('accepts valid backup code in demo mode', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false, status: 503 });

      const result = await useMFAStore.getState().verifyLogin('abcd', true);
      expect(result).toBe(true);
    });

    it('rejects invalid code and sets error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Invalid code' }),
      });

      const result = await useMFAStore.getState().verifyLogin('000000');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Invalid code');
    });

    it('accepts 6-digit code in demo network error', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const result = await useMFAStore.getState().verifyLogin('999999');
      expect(result).toBe(true);
    });

    it('rejects wrong-length code on network error', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const result = await useMFAStore.getState().verifyLogin('123');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Network error — please try again');
    });
  });

  // ── disableMfa ─────────────────────────────────────────────────────

  describe('disableMfa', () => {
    it('disables MFA on success', async () => {
      useMFAStore.setState({ isEnrolled: true, status: 'enrolled' });
      mockFetch.mockResolvedValueOnce({ ok: true });

      const result = await useMFAStore.getState().disableMfa('mypassword');
      expect(result).toBe(true);
      expect(useMFAStore.getState().isEnrolled).toBe(false);
      expect(useMFAStore.getState().status).toBe('idle');
      expect(useMFAStore.getState().setupData).toBeNull();
    });

    it('disables MFA on 404 (backend unavailable)', async () => {
      useMFAStore.setState({ isEnrolled: true });
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });

      const result = await useMFAStore.getState().disableMfa('mypassword');
      expect(result).toBe(true);
      expect(useMFAStore.getState().isEnrolled).toBe(false);
    });

    it('returns false on server error', async () => {
      useMFAStore.setState({ isEnrolled: true });
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Wrong password' }),
      });

      const result = await useMFAStore.getState().disableMfa('wrong');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Wrong password');
      expect(useMFAStore.getState().isEnrolled).toBe(true);
    });

    it('returns false on network error', async () => {
      useMFAStore.setState({ isEnrolled: true });
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const result = await useMFAStore.getState().disableMfa('pass');
      expect(result).toBe(false);
      expect(useMFAStore.getState().error).toBe('Network error — cannot disable MFA offline');
    });
  });

  // ── resetError / clearState ────────────────────────────────────────

  describe('resetError', () => {
    it('clears the error', () => {
      useMFAStore.setState({ error: 'Some error' });
      useMFAStore.getState().resetError();
      expect(useMFAStore.getState().error).toBeNull();
    });
  });

  describe('clearState', () => {
    it('resets everything to initial state', () => {
      useMFAStore.setState({
        status: 'enrolled',
        setupData: { secret: 'X', qrCodeUrl: 'Y', backupCodes: ['Z'] },
        isEnrolled: true,
        error: 'old error',
      });

      useMFAStore.getState().clearState();

      expect(useMFAStore.getState().status).toBe('idle');
      expect(useMFAStore.getState().setupData).toBeNull();
      expect(useMFAStore.getState().isEnrolled).toBe(false);
      expect(useMFAStore.getState().error).toBeNull();
    });
  });
});
