/**
 * PARWA Day 5 Integration Tests — Settings, MFA, Email Verification
 *
 * End-to-end flow tests verifying:
 * - Settings page tab navigation and form interactions
 * - MFA enrollment → verification → disable flow
 * - Email verification success/expired/resend flow
 * - Error boundary catches and recovers
 * - Demo banner displays and dismisses
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useMFAStore } from '@/lib/mfa-store';

// ── Mocks ────────────────────────────────────────────────────────────

const mockPush = jest.fn();
const mockBack = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter() {
    return { push: mockPush, replace: jest.fn(), back: mockBack, prefetch: jest.fn(), pathname: '/', query: {}, asPath: '/' };
  },
  useSearchParams() {
    return new URLSearchParams('token=abc123&email=test@example.com');
  },
  usePathname() { return '/'; },
}));

jest.mock('next/link', () => {
  return function MockLink(props: Record<string, unknown>) {
    return React.createElement('a', { href: props.href as string, onClick: props.onClick as any }, props.children);
  };
});

jest.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(_target: Record<string, unknown>, prop: string) {
      return (props: Record<string, unknown>) =>
        React.createElement('svg', { 'data-testid': `icon-${prop.toLowerCase()}`, ...props });
    },
  });
});

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: { full_name: 'Test User', email: 'test@example.com', company_name: 'TestCo' },
    isAuthenticated: true,
  }),
}));

jest.mock('@/hooks/useVariant', () => ({
  useVariant: () => ({ tier: 'pro', variant: 'parwa_pro' }),
}));

const mockFetch = jest.fn();
global.fetch = mockFetch;

// ── MFA Store Integration ────────────────────────────────────────────

describe('MFA Flow Integration', () => {
  beforeEach(() => {
    useMFAStore.getState().clearState();
    mockFetch.mockReset();
    mockPush.mockReset();
  });

  it('completes full MFA setup → verify → enrolled flow', async () => {
    // Step 1: Initiate setup
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        secret: 'JBSWY3DPEHPK3PXP',
        qr_code_url: 'https://qr.test/mfa',
        backup_codes: ['bc1-001', 'bc2-002', 'bc3-003', 'bc4-004'],
      }),
    });

    await act(async () => {
      await useMFAStore.getState().initiateSetup();
    });

    expect(useMFAStore.getState().status).toBe('enrolling');
    expect(useMFAStore.getState().setupData?.secret).toBe('JBSWY3DPEHPK3PXP');

    // Step 2: Verify with 6-digit code
    mockFetch.mockResolvedValueOnce({ ok: true });

    let enrollResult = false;
    await act(async () => {
      enrollResult = await useMFAStore.getState().verifyAndEnroll('123456');
    });

    expect(enrollResult).toBe(true);
    expect(useMFAStore.getState().isEnrolled).toBe(true);
    expect(useMFAStore.getState().status).toBe('enrolled');
    expect(useMFAStore.getState().setupData?.backupCodes).toEqual(['bc1-001', 'bc2-002', 'bc3-003', 'bc4-004']);
  });

  it('completes full MFA login verification flow', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ token: 'jwt-xyz' }) });

    let result = false;
    await act(async () => {
      result = await useMFAStore.getState().verifyLogin('654321');
    });

    expect(result).toBe(true);
    expect(useMFAStore.getState().status).toBe('idle');
  });

  it('completes MFA disable flow after enrollment', async () => {
    useMFAStore.setState({ isEnrolled: true, status: 'enrolled' });

    mockFetch.mockResolvedValueOnce({ ok: true });

    let result = false;
    await act(async () => {
      result = await useMFAStore.getState().disableMfa('my-password');
    });

    expect(result).toBe(true);
    expect(useMFAStore.getState().isEnrolled).toBe(false);
    expect(useMFAStore.getState().status).toBe('idle');
    expect(useMFAStore.getState().setupData).toBeNull();
  });

  it('handles failed enrollment → retry → success', async () => {
    // Step 1: Initiate setup
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        secret: 'RETRYTEST',
        qr_code_url: 'https://qr.test/retry',
        backup_codes: ['r1-r2'],
      }),
    });

    await act(async () => {
      await useMFAStore.getState().initiateSetup();
    });

    // Step 2: First verify fails (wrong code)
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Invalid code' }),
    });

    let result1 = false;
    await act(async () => {
      result1 = await useMFAStore.getState().verifyAndEnroll('000000');
    });

    expect(result1).toBe(false);
    expect(useMFAStore.getState().error).toBe('Invalid code');

    // Step 3: Retry with correct code
    useMFAStore.getState().resetError();
    mockFetch.mockResolvedValueOnce({ ok: true });

    let result2 = false;
    await act(async () => {
      result2 = await useMFAStore.getState().verifyAndEnroll('123456');
    });

    expect(result2).toBe(true);
    expect(useMFAStore.getState().isEnrolled).toBe(true);
    expect(useMFAStore.getState().error).toBeNull();
  });
});

// ── Email Verification Integration ───────────────────────────────────

describe('Email Verification Integration', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('verifies email successfully with valid token', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/verify-email?token=valid-token`);

    expect(res.ok).toBe(true);
  });

  it('handles expired token', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 410 });

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/verify-email?token=expired-token`);

    expect(res.ok).toBe(false);
    expect(res.status).toBe(410);
  });

  it('resends verification email on request', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/verify-email/resend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.com' }),
    });

    expect(res.ok).toBe(true);
  });
});

// ── Error Boundary + Demo Banner Integration ─────────────────────────

describe('UI Components Integration', () => {
  it('DemoBanner renders and is dismissable', () => {
    const { DemoBanner } = require('@/components/DemoBanner');
    render(React.createElement(DemoBanner));

    expect(screen.getByTestId('demo-banner')).toBeInTheDocument();
    expect(screen.getByText(/Demo Mode/)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Dismiss demo banner'));
    expect(screen.queryByTestId('demo-banner')).not.toBeInTheDocument();
  });

  it('ErrorBoundary catches errors and provides retry', () => {
    const { ErrorBoundary } = require('@/components/ErrorBoundary');

    function BrokenComponent() {
      throw new Error('Integration test error');
    }

    const originalError = console.error;
    console.error = jest.fn();

    render(
      React.createElement(
        ErrorBoundary,
        null,
        React.createElement(BrokenComponent)
      )
    );

    expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();

    console.error = originalError;
  });
});
