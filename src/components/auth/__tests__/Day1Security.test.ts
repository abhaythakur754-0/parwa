/**
 * PARWA Day 1 Security Tests — Frontend
 *
 * Tests for C-02, C-03, H-02, H-03, M-20 fixes.
 */

import { jest } from '@jest/globals';

// ═══════════════════════════════════════════════════════════════
// C-02: Real JWT tokens (not UUIDs)
// ═══════════════════════════════════════════════════════════════

describe('C-02: JWT Utility', () => {
  it('signAccessToken returns a valid JWT with 3 parts', async () => {
    const { signAccessToken } = await import('@/lib/jwt');
    const token = await signAccessToken({
      sub: 'user-123',
      email: 'test@example.com',
      role: 'member',
      company_id: 'company-123',
    });
    // JWT format: base64url.base64url.base64url
    expect(token.split('.')).toHaveLength(3);
    expect(token).not.toContain('parwa_at_');
  });

  it('signRefreshToken returns a valid JWT with type=refresh', async () => {
    const { signRefreshToken, verifyToken } = await import('@/lib/jwt');
    const token = await signRefreshToken({
      sub: 'user-123',
      email: 'test@example.com',
      role: 'member',
    });
    const verified = await verifyToken(token);
    expect(verified).not.toBeNull();
    expect(verified?.payload.type).toBe('refresh');
  });

  it('verifyToken returns null for invalid tokens', async () => {
    const { verifyToken } = await import('@/lib/jwt');
    const result = await verifyToken('invalid.jwt.token');
    expect(result).toBeNull();
  });

  it('verifyToken returns payload for valid tokens', async () => {
    const { signAccessToken, verifyToken } = await import('@/lib/jwt');
    const token = await signAccessToken({
      sub: 'user-123',
      email: 'test@example.com',
      role: 'member',
    });
    const result = await verifyToken(token);
    expect(result).not.toBeNull();
    expect(result?.payload.sub).toBe('user-123');
    expect(result?.payload.email).toBe('test@example.com');
  });
});

// ═══════════════════════════════════════════════════════════════
// C-03: No tokens in localStorage (only httpOnly cookies)
// ═══════════════════════════════════════════════════════════════

describe('C-03: Tokens NOT in localStorage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (localStorage.getItem as jest.Mock).mockReturnValue(null);
  });

  it('login page does NOT store parwa_access_token', async () => {
    // Verify login page source does not contain token localStorage
    const fs = await import('fs');
    const path = await import('path');
    const loginPage = fs.readFileSync(
      path.join(process.cwd(), 'src/app/(auth)/login/page.tsx'),
      'utf-8'
    );
    expect(loginPage).not.toContain("localStorage.setItem('parwa_access_token'");
    expect(loginPage).not.toContain("localStorage.setItem('parwa_refresh_token'");
  });

  it('signup page does NOT store parwa_access_token', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const signupPage = fs.readFileSync(
      path.join(process.cwd(), 'src/app/(auth)/signup/page.tsx'),
      'utf-8'
    );
    expect(signupPage).not.toContain("localStorage.setItem('parwa_access_token'");
    expect(signupPage).not.toContain("localStorage.setItem('parwa_refresh_token'");
  });

  it('auth context does NOT store tokens in localStorage', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const authCtx = fs.readFileSync(
      path.join(process.cwd(), 'src/contexts/AuthContext.tsx'),
      'utf-8'
    );
    // Should not store tokens
    expect(authCtx).not.toContain("AUTH_TOKEN_KEY");
    expect(authCtx).not.toContain("REFRESH_TOKEN_KEY");
    // storeAuthData should not store tokens
    expect(authCtx).not.toMatch(/localStorage\.setItem\(.*access_token/);
    expect(authCtx).not.toMatch(/localStorage\.setItem\(.*refresh_token/);
  });
});

// ═══════════════════════════════════════════════════════════════
// H-02: Timing-safe OTP comparison
// ═══════════════════════════════════════════════════════════════

describe('H-02: Timing-safe OTP comparison', () => {
  it('timingSafeEqual returns true for matching OTPs', async () => {
    const { timingSafeEqual } = await import('@/lib/jwt');
    expect(timingSafeEqual('123456', '123456')).toBe(true);
  });

  it('timingSafeEqual returns false for non-matching OTPs', async () => {
    const { timingSafeEqual } = await import('@/lib/jwt');
    expect(timingSafeEqual('123456', '654321')).toBe(false);
  });

  it('timingSafeEqual returns false for different length strings', async () => {
    const { timingSafeEqual } = await import('@/lib/jwt');
    expect(timingSafeEqual('123', '123456')).toBe(false);
  });

  it('timingSafeEqual does not use !== for comparison', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const jwtFile = fs.readFileSync(
      path.join(process.cwd(), 'src/lib/jwt.ts'),
      'utf-8'
    );
    // Should use crypto.timingSafeEqual
    expect(jwtFile).toContain('timingSafeEqual');
    expect(jwtFile).toContain('crypto.timingSafeEqual');
  });
});

// ═══════════════════════════════════════════════════════════════
// M-20: Password complexity requirements
// ═══════════════════════════════════════════════════════════════

describe('M-20: Password complexity validation', () => {
  it('rejects passwords shorter than 8 characters', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('Ab1!');
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('rejects passwords without uppercase', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('abcdef1!');
    expect(result.valid).toBe(false);
  });

  it('rejects passwords without lowercase', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('ABCDEF1!');
    expect(result.valid).toBe(false);
  });

  it('rejects passwords without digits', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('Abcdefg!');
    expect(result.valid).toBe(false);
  });

  it('rejects passwords without special characters', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('Abcdef12');
    expect(result.valid).toBe(false);
  });

  it('accepts valid passwords with all requirements', async () => {
    const { validatePasswordStrength } = await import('@/lib/jwt');
    const result = validatePasswordStrength('Abcdef12!');
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// H-03: Registration creates unverified users
// ═══════════════════════════════════════════════════════════════

describe('H-03: Registration requires email verification', () => {
  it('register route sets is_verified to false', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const registerRoute = fs.readFileSync(
      path.join(process.cwd(), 'src/app/api/auth/register/route.ts'),
      'utf-8'
    );
    expect(registerRoute).toContain('is_verified: false');
  });

  it('register route generates verification token', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const registerRoute = fs.readFileSync(
      path.join(process.cwd(), 'src/app/api/auth/register/route.ts'),
      'utf-8'
    );
    expect(registerRoute).toContain('verification_token');
    expect(registerRoute).toContain('verificationToken');
  });
});
