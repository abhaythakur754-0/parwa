/**
 * PARWA Day 1 Security Tests — Dashboard Auth (C-01 Fix)
 *
 * Tests that dashboard API routes use real JWT verification,
 * not the old fake requireAuth() that only checked header existence.
 */

import { SignJWT } from 'jose';

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET_KEY || 'dev-jwt-secret-key-change-in-prod-32c'
);

// Helper to create test JWTs
async function createTestToken(overrides: Record<string, unknown> = {}, isRefresh = false) {
  const payload = {
    sub: 'user-123',
    email: 'test@example.com',
    role: 'owner',
    company_id: 'company-123',
    ...overrides,
  };
  return new SignJWT({ ...payload, type: isRefresh ? 'refresh' : undefined })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setIssuer('parwa:frontend')
    .setAudience('parwa:app')
    .setExpirationTime(isRefresh ? '7d' : '15m')
    .sign(JWT_SECRET);
}

function createMockRequest(headers: Record<string, string> = {}, cookies: Record<string, string> = {}) {
  const cookieStr = Object.entries(cookies)
    .map(([k, v]) => `${k}=${v}`)
    .join('; ');
  return {
    headers: {
      get: (name: string) => {
        if (name.toLowerCase() === 'authorization') return headers.authorization || null;
        if (name.toLowerCase() === 'cookie') return cookieStr || null;
        return null;
      },
    },
  } as any;
}

describe('C-01: Dashboard Auth Utility', () => {
  let verifyAuth: (req: any) => Promise<any>;

  beforeAll(async () => {
    const mod = await import('../auth');
    verifyAuth = mod.verifyAuth;
  });

  it('rejects requests with no auth header and no cookie', async () => {
    const req = createMockRequest();
    const result = await verifyAuth(req);
    expect(result).toBeNull();
  });

  it('rejects requests with garbage Bearer token', async () => {
    const req = createMockRequest({ authorization: 'Bearer garbage-token' });
    const result = await verifyAuth(req);
    expect(result).toBeNull();
  });

  it('rejects expired tokens', async () => {
    const expiredToken = await new SignJWT({ sub: 'user-123', email: 'test@test.com' })
      .setProtectedHeader({ alg: 'HS256' })
      .setIssuer('parwa:frontend')
      .setAudience('parwa:app')
      .setIssuedAt()
      .setExpirationTime('-1s')
      .sign(JWT_SECRET);

    const req = createMockRequest({ authorization: `Bearer ${expiredToken}` });
    const result = await verifyAuth(req);
    expect(result).toBeNull();
  });

  it('accepts valid token from Authorization header', async () => {
    const token = await createTestToken();
    const req = createMockRequest({ authorization: `Bearer ${token}` });
    const result = await verifyAuth(req);
    expect(result).not.toBeNull();
    expect(result.sub).toBe('user-123');
    expect(result.email).toBe('test@example.com');
  });

  it('reads token from parwa_at cookie as fallback', async () => {
    const token = await createTestToken();
    const req = createMockRequest({}, { parwa_at: token });
    const result = await verifyAuth(req);
    expect(result).not.toBeNull();
    expect(result.sub).toBe('user-123');
  });

  it('rejects refresh tokens (type=refresh)', async () => {
    const refreshToken = await createTestToken({}, true);
    const req = createMockRequest({ authorization: `Bearer ${refreshToken}` });
    const result = await verifyAuth(req);
    expect(result).toBeNull();
  });
});
