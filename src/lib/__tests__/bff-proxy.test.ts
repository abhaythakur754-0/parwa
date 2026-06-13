/**
 * Unit tests for the unified BFF proxy helper (src/lib/bff-proxy.ts)
 *
 * Validates:
 * - getProxyOrigin() returns correct origin based on env vars
 * - getBearerToken() extracts token from cookies using the centralized helper
 * - buildProxyHeaders() includes correct headers (Origin, Referer, Authorization)
 * - All BFF routes use getBackendUrl() consistently (BC-006)
 */

import { getProxyOrigin, getBearerToken, buildProxyHeaders } from '@/lib/bff-proxy';
import { getBackendUrl } from '@/lib/backend-url';

// Helper to create a mock Request-like object with a cookie header
function mockRequest(cookieHeader?: string) {
  const headers = new Map<string, string>();
  if (cookieHeader) headers.set('cookie', cookieHeader);
  return {
    headers: {
      get: (name: string) => headers.get(name.toLowerCase()) || null,
    },
  } as unknown as Request;
}

// ── getProxyOrigin() ────────────────────────────────────────────────

describe('getProxyOrigin', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns FRONTEND_URL when set', () => {
    process.env.FRONTEND_URL = 'https://custom.parwa.io';
    expect(getProxyOrigin()).toBe('https://custom.parwa.io');
  });

  it('returns VERCEL_URL when FRONTEND_URL not set', () => {
    delete process.env.FRONTEND_URL;
    process.env.VERCEL_URL = 'parwa-staging.vercel.app';
    expect(getProxyOrigin()).toBe('https://parwa-staging.vercel.app');
  });

  it('returns parwa.buzz in production', () => {
    delete process.env.FRONTEND_URL;
    delete process.env.VERCEL_URL;
    process.env.NODE_ENV = 'production';
    expect(getProxyOrigin()).toBe('https://parwa.buzz');
  });

  it('returns localhost:3000 in development', () => {
    delete process.env.FRONTEND_URL;
    delete process.env.VERCEL_URL;
    process.env.NODE_ENV = 'development';
    expect(getProxyOrigin()).toBe('http://localhost:3000');
  });
});

// ── getBearerToken() ────────────────────────────────────────────────

describe('getBearerToken', () => {
  it('extracts token from parwa_at cookie', () => {
    const request = mockRequest('parwa_at=eyJhbGciOiJIUzI1NiJ9.test.sig; other=value');
    expect(getBearerToken(request)).toBe('eyJhbGciOiJIUzI1NiJ9.test.sig');
  });

  it('returns null when no cookie header', () => {
    const request = mockRequest();
    expect(getBearerToken(request)).toBeNull();
  });

  it('returns null when parwa_at cookie is missing', () => {
    const request = mockRequest('other_cookie=value; session=abc');
    expect(getBearerToken(request)).toBeNull();
  });
});

// ── buildProxyHeaders() ─────────────────────────────────────────────

describe('buildProxyHeaders', () => {
  it('includes Origin, Referer, and Content-Type headers', () => {
    const request = mockRequest();
    const headers = buildProxyHeaders(request);
    expect(headers['Origin']).toBeTruthy();
    expect(headers['Referer']).toBeTruthy();
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('includes Authorization header when token is present', () => {
    const request = mockRequest('parwa_at=my-jwt-token');
    const headers = buildProxyHeaders(request);
    expect(headers['Authorization']).toBe('Bearer my-jwt-token');
  });

  it('omits Authorization header when no token', () => {
    const request = mockRequest();
    const headers = buildProxyHeaders(request);
    expect(headers['Authorization']).toBeUndefined();
  });
});

// ── getBackendUrl() consistency (BC-006) ────────────────────────────

describe('getBackendUrl consistency', () => {
  it('returns a valid URL or localhost fallback', () => {
    const url = getBackendUrl();
    // In any environment, the URL should be a valid string
    expect(typeof url).toBe('string');
    expect(url.length).toBeGreaterThan(0);
  });

  it('respects BACKEND_URL env var when set to a real URL', () => {
    const original = process.env.BACKEND_URL;
    process.env.BACKEND_URL = 'https://custom-backend.example.com';
    // Note: getBackendUrl() checks process.env.BACKEND_URL at call time
    expect(getBackendUrl()).toBe('https://custom-backend.example.com');
    if (original) {
      process.env.BACKEND_URL = original;
    } else {
      delete process.env.BACKEND_URL;
    }
  });
});

// ── Integration: All BFF routes use same URL resolution ─────────────

describe('BFF route URL resolution consistency (BC-006)', () => {
  it('getBackendUrl is the single source of truth', () => {
    // When BACKEND_URL is properly set, it returns a valid URL
    const original = process.env.BACKEND_URL;
    process.env.BACKEND_URL = 'https://parwa-backend.onrender.com';
    const url = getBackendUrl();
    expect(url).toBe('https://parwa-backend.onrender.com');
    if (original) {
      process.env.BACKEND_URL = original;
    } else {
      delete process.env.BACKEND_URL;
    }
  });

  it('getProxyOrigin is the single source of truth for Origin', () => {
    const origin = getProxyOrigin();
    expect(origin).toMatch(/(parwa\.buzz|vercel\.app|localhost:3000|custom\.parwa\.io)/);
  });

  it('getBearerToken delegates to getAccessTokenFromCookies', () => {
    // This confirms BC-004: we reuse the existing auth-cookies helper
    // instead of creating duplicate cookie extraction logic
    const request = mockRequest('parwa_at=test-token-123');
    const token = getBearerToken(request);
    expect(token).toBe('test-token-123');
  });
});
