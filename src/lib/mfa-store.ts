/**
 * PARWA MFA Store — Zustand state for Multi-Factor Authentication
 *
 * Manages MFA enrollment, login verification, and disable flows.
 * All API failures show honest error states — NO demo fallbacks.
 * A fake MFA is worse than no MFA.
 */

import { create } from 'zustand';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────────

export type MFAStatus = 'idle' | 'enrolling' | 'verifying' | 'enrolled' | 'error';

export interface MFASetupData {
  secret: string;
  qrCodeUrl: string;
  backupCodes: string[];
}

interface MFAState {
  // State
  status: MFAStatus;
  setupData: MFASetupData | null;
  isEnrolled: boolean;
  error: string | null;
  isBackendUnavailable: boolean;

  // Actions
  initiateSetup: () => Promise<void>;
  verifyAndEnroll: (code: string) => Promise<boolean>;
  verifyLogin: (code: string, backupCode?: boolean) => Promise<boolean>;
  disableMfa: (password: string) => Promise<boolean>;
  resetError: () => void;
  clearState: () => void;
}

// ── Helpers ──────────────────────────────────────────────────────────

function isBackendUnavailable(status: number): boolean {
  return status === 404 || status === 502 || status === 503;
}

function backendUnavailableError(): string {
  return 'MFA service is currently unavailable. Please try again later.';
}

// ── Store ────────────────────────────────────────────────────────────

export const useMFAStore = create<MFAState>((set) => ({
  status: 'idle',
  setupData: null,
  isEnrolled: false,
  error: null,
  isBackendUnavailable: false,

  initiateSetup: async () => {
    set({ status: 'enrolling', error: null, isBackendUnavailable: false });
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/mfa/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });

      if (res.ok) {
        const data = await res.json();
        set({
          setupData: {
            secret: data.secret || '',
            qrCodeUrl: data.qr_code_url || data.qrCodeUrl || '',
            backupCodes: data.backup_codes || data.backupCodes || [],
          },
          status: 'enrolling', // stays enrolling until user verifies
        });
      } else if (isBackendUnavailable(res.status)) {
        // Backend unavailable — show honest error, NOT fake QR code
        set({
          status: 'error',
          error: backendUnavailableError(),
          isBackendUnavailable: true,
        });
      } else {
        const data = await res.json().catch(() => ({}));
        set({ status: 'error', error: data.detail || 'Failed to initiate MFA setup' });
      }
    } catch {
      // Network error — show honest error
      set({
        status: 'error',
        error: 'Unable to reach MFA service. Please check your connection and try again.',
        isBackendUnavailable: true,
      });
    }
  },

  verifyAndEnroll: async (code: string) => {
    if (!code || code.length < 4) {
      set({ error: 'Please enter a valid verification code' });
      return false;
    }
    set({ status: 'verifying', error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/mfa/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ code }),
      });

      if (res.ok) {
        set({ status: 'enrolled', isEnrolled: true, error: null, isBackendUnavailable: false });
        return true;
      } else if (isBackendUnavailable(res.status)) {
        // Backend unavailable — do NOT accept any code
        set({
          status: 'error',
          error: backendUnavailableError(),
          isBackendUnavailable: true,
        });
        return false;
      } else {
        const data = await res.json().catch(() => ({}));
        set({ status: 'error', error: data.detail || 'Invalid verification code' });
        return false;
      }
    } catch {
      // Network error — do NOT accept any code
      set({
        status: 'error',
        error: 'Unable to reach MFA service. Please check your connection and try again.',
        isBackendUnavailable: true,
      });
      return false;
    }
  },

  verifyLogin: async (code: string, backupCode = false) => {
    if (!code) {
      set({ error: 'Please enter a verification code' });
      return false;
    }
    set({ status: 'verifying', error: null });
    try {
      const endpoint = backupCode
        ? `${API_BASE}/api/v1/auth/mfa/backup`
        : `${API_BASE}/api/v1/auth/mfa/login`;
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(backupCode ? { backup_code: code } : { code }),
      });

      if (res.ok) {
        set({ status: 'idle', error: null, isBackendUnavailable: false });
        return true;
      } else if (isBackendUnavailable(res.status)) {
        // Backend unavailable — do NOT accept any code
        set({
          status: 'error',
          error: backendUnavailableError(),
          isBackendUnavailable: true,
        });
        return false;
      } else {
        const data = await res.json().catch(() => ({}));
        set({ status: 'error', error: data.detail || 'Invalid verification code' });
        return false;
      }
    } catch {
      // Network error — do NOT accept any code
      set({
        status: 'error',
        error: 'Unable to reach MFA service. Please check your connection and try again.',
        isBackendUnavailable: true,
      });
      return false;
    }
  },

  disableMfa: async (password: string) => {
    set({ error: null });
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/mfa/disable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        set({ isEnrolled: false, status: 'idle', setupData: null, error: null, isBackendUnavailable: false });
        return true;
      } else if (isBackendUnavailable(res.status)) {
        // Backend unavailable — do NOT silently disable
        set({
          error: backendUnavailableError(),
          isBackendUnavailable: true,
        });
        return false;
      }
      const data = await res.json().catch(() => ({}));
      set({ error: data.detail || 'Failed to disable MFA' });
      return false;
    } catch {
      set({
        error: 'Unable to reach MFA service. Cannot disable MFA while offline.',
        isBackendUnavailable: true,
      });
      return false;
    }
  },

  resetError: () => set({ error: null }),

  clearState: () => set({ status: 'idle', setupData: null, isEnrolled: false, error: null, isBackendUnavailable: false }),
}));
