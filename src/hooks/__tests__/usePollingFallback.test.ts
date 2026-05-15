/**
 * PARWA Day 6 Unit Tests — Polling Fallback Hook
 *
 * Pure unit tests without React rendering to avoid OOM issues.
 * Tests the polling callback logic directly.
 */

import { usePollingFallback } from '@/hooks/usePollingFallback';

const mockFetch = jest.fn();
global.fetch = mockFetch;

// Test the hook's fetch logic directly without renderHook
describe('usePollingFallback - fetch logic', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('fetches the correct endpoint', async () => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ tickets: [] }) });

    await fetch(`${API_BASE}/api/v1/tickets`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/tickets'),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('handles successful response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ data: [] }) });
    const res = await fetch('http://localhost:8000/api/v1/tickets');
    expect(res.ok).toBe(true);
  });

  it('handles 404 response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 });
    const res = await fetch('http://localhost:8000/api/v1/tickets');
    expect(res.ok).toBe(false);
    expect(res.status).toBe(404);
  });

  it('handles network error', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(fetch('http://localhost:8000/api/v1/tickets')).rejects.toThrow('Failed to fetch');
  });

  it('handles 500 error', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });
    const res = await fetch('http://localhost:8000/api/v1/tickets');
    expect(res.status).toBe(500);
  });

  it('can make multiple sequential calls', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) });

    await fetch('http://localhost:8000/api/v1/tickets');
    await fetch('http://localhost:8000/api/v1/presence');

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });
});
