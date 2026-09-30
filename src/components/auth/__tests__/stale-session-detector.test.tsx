/**
 * Stale-session detector — tests for the fix that clears httpOnly cookies
 * when the refresh token is genuinely invalid (401/403).
 *
 * Bug (from STATE.md): after a DB wipe, the browser still has a stale
 * `parwa_at` cookie. Middleware (presence-only check) lets the user through
 * to /dashboard → me-proxy 401s → refresh 401s → localStorage cleared BUT
 * httpOnly cookies survive → next nav → middleware lets user through again
 * → infinite redirect loop.
 *
 * Fix: when refresh returns 401/403, call /api/auth/logout to clear the
 * httpOnly cookies server-side (via Set-Cookie Max-Age=0) before clearing
 * localStorage.
 */

import React from 'react';
import { render, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';

// ── Mocks ───────────────────────────────────────────────────────────────

jest.mock('@/lib/api', () => ({
  authApi: {
    login: jest.fn(),
    register: jest.fn(),
    googleAuth: jest.fn(),
    logout: jest.fn(),
    refresh: jest.fn(),
    getMe: jest.fn(),
    checkEmail: jest.fn().mockResolvedValue({ available: true }),
  },
  getErrorMessage: jest.fn(() => 'error'),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock global.fetch so we can simulate the me-proxy + refresh + logout calls.
// Returns plain objects (not Response instances) for reliable jsdom behavior.
function mockResponse(status: number, body: string = '') {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => body,
    json: async () => {
      try { return JSON.parse(body); } catch { return {}; }
    },
  };
}

const fetchMock = jest.fn();
global.fetch = fetchMock as unknown as typeof fetch;

// Test component
function TestComponent() {
  const { isAuthenticated, isInitialized } = useAuth();
  return (
    <div>
      <span data-testid="authed">{String(isAuthenticated)}</span>
      <span data-testid="init">{String(isInitialized)}</span>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────

function seedCachedUser() {
  localStorageMock.setItem(
    'parwa_user',
    JSON.stringify({ email: 'stale@example.com', id: 'u1' })
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <TestComponent />
    </AuthProvider>
  );
}

// ── Tests ───────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  localStorageMock.clear();
});

describe('Stale-session detector', () => {
  it('clears httpOnly cookies via /api/auth/logout when refresh returns 401', async () => {
    seedCachedUser();

    // me-proxy → 401 (stale access token)
    // refresh → 401 (stale refresh token = session truly dead)
    // logout  → 200 (clears cookies server-side)
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/auth/me-proxy') {
        return mockResponse(401, 'Unauthorized');
      }
      if (url === '/api/auth/refresh') {
        return mockResponse(401, 'Unauthorized');
      }
      if (url === '/api/auth/logout') {
        return mockResponse(200, '{"status":"success"}');
      }
      return mockResponse(404, '');
    });

    const { getByTestId } = renderProvider();

    // Wait for initialization to complete.
    await waitFor(() => {
      expect(getByTestId('init').textContent).toBe('true');
    });

    // User must be logged out (not stuck in a loop).
    expect(getByTestId('authed').textContent).toBe('false');

    // The logout endpoint MUST have been called to clear httpOnly cookies.
    // This is the core of the stale-session fix.
    const logoutCalls = fetchMock.mock.calls.filter(
      ([url]) => url === '/api/auth/logout'
    );
    expect(logoutCalls).toHaveLength(1);

    // localStorage must be cleared.
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('parwa_user');
  });

  it('does NOT call logout when refresh fails with 503 (cold start)', async () => {
    seedCachedUser();

    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/auth/me-proxy') {
        return mockResponse(401, 'Unauthorized');
      }
      if (url === '/api/auth/refresh') {
        // 503 = backend cold start, NOT an invalid session
        return mockResponse(503, 'Service Unavailable');
      }
      return mockResponse(404, '');
    });

    const { getByTestId } = renderProvider();

    await waitFor(() => {
      expect(getByTestId('init').textContent).toBe('true');
    });

    // User stays logged in (Netflix-style — don't log out on cold start).
    expect(getByTestId('authed').textContent).toBe('true');

    // The logout endpoint must NOT have been called.
    const logoutCalls = fetchMock.mock.calls.filter(
      ([url]) => url === '/api/auth/logout'
    );
    expect(logoutCalls).toHaveLength(0);

    // localStorage must NOT be cleared.
    expect(localStorageMock.removeItem).not.toHaveBeenCalledWith('parwa_user');
  });

  it('logs out cleanly when no cached user exists (no stale cookies to clear)', async () => {
    // No localStorage entry → no cached user → should not hit backend at all.
    const { getByTestId } = renderProvider();

    await waitFor(() => {
      expect(getByTestId('init').textContent).toBe('true');
    });

    expect(getByTestId('authed').textContent).toBe('false');
    // No fetch calls should happen (no user to verify).
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
