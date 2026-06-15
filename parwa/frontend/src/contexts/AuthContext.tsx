'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  User,
  AuthResponse,
  AuthState,
  AuthContextType,
  RegisterRequest,
} from '@/types/auth';
import { authApi } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';
import { useAppStore } from '@/lib/store';

// ── Auth Context ────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const USER_KEY = 'parwa_user';

/**
 * Grace period (ms) after a hydrate() call during which initializeAuth()
 * will NOT overwrite the auth state.  This prevents the race condition
 * where a slow me-proxy response clears the state that hydrate() just set.
 */
const HYDRATION_GRACE_MS = 30_000;

/** Read user data from localStorage (non-sensitive display data only). */
function readUserData(): User | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem(USER_KEY);
    if (stored) {
      const user = JSON.parse(stored) as User;
      if (user && user.email) return user;
    }
  } catch {
    // corrupt data
  }
  return null;
}

// ── Auth Provider ───────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    isInitialized: false,
  });

  // Track the last time hydrate() was called so initializeAuth()
  // doesn't overwrite a freshly-hydrated state (race condition fix).
  const lastHydratedAt = useRef<number>(0);

  // ── Initialize Auth State ────────────────────────────────────────────
  // CRITICAL: We must NOT trust stale localStorage data if the backend
  // explicitly rejects the auth (401). This was causing infinite redirect
  // loops because the client thought it was authenticated but the
  // middleware kept rejecting requests (no valid cookie).
  //
  // RACE CONDITION FIX: If hydrate() was called recently (within
  // HYDRATION_GRACE_MS), we skip the backend check entirely because
  // hydrate() is called right after login/signup and its state should
  // be trusted over a slow/stale me-proxy response.

  const initializeAuth = useCallback(async () => {
    try {
      const cachedUser = readUserData();

      if (!cachedUser) {
        // No cached data — definitely not authenticated
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          isInitialized: true,
        });
        return;
      }

      // ── Race condition guard ──
      // If hydrate() was called recently (e.g. after login/signup),
      // trust that state instead of making a backend call that might
      // fail and clear it.
      const timeSinceHydration = Date.now() - lastHydratedAt.current;
      if (timeSinceHydration < HYDRATION_GRACE_MS) {
        console.log('[AuthContext] Skipping me-proxy — recent hydrate() within grace period');
        // State was already set by hydrate(); just mark as initialized
        setState(prev => ({ ...prev, isLoading: false, isInitialized: true }));
        return;
      }

      // We have cached user data — verify with backend
      try {
        const response = await fetch('/api/auth/me-proxy', {
          method: 'GET',
          credentials: 'include', // Send httpOnly cookies
        });

        // Re-check hydration guard AFTER the async call —
        // hydrate() may have been called while we were waiting.
        if (Date.now() - lastHydratedAt.current < HYDRATION_GRACE_MS) {
          console.log('[AuthContext] me-proxy completed but hydrate() was called during fetch — keeping hydrated state');
          setState(prev => ({ ...prev, isLoading: false, isInitialized: true }));
          return;
        }

        if (response.ok) {
          // Backend confirmed — user is authenticated
          // Safely parse JSON — guard against non-JSON responses
          let currentUser: User | null = null;
          try {
            const text = await response.text();
            currentUser = JSON.parse(text) as User;
          } catch {
            // Non-JSON response — treat as unverified
            console.warn('[AuthContext] me-proxy returned non-JSON');
          }
          if (currentUser) {
            setState({
              user: currentUser,
              isAuthenticated: true,
              isLoading: false,
              isInitialized: true,
            });
            return;
          }
          // JSON parse succeeded but no valid user — fall through
        }

        // Backend returned 401/403 or non-JSON — session is INVALID.
        // MUST clear stale cache to prevent redirect loops.
        console.warn('[AuthContext] Backend rejected auth — clearing stale cache');
        localStorage.removeItem(USER_KEY);
      } catch (networkError) {
        // Network error (backend unreachable / cold start).
        // In this case ONLY, tentatively trust cached data.
        // But we mark that it's unverified so the login page doesn't
        // auto-redirect to protected routes (which would loop).
        console.warn('[AuthContext] Backend unreachable — using cached data (unverified)');
        setState({
          user: cachedUser,
          isAuthenticated: false, // Don't claim authenticated — prevents redirect loop
          isLoading: false,
          isInitialized: true,
        });
        return;
      }
    } catch (error) {
      console.error('Auth initialization error:', error);
      localStorage.removeItem(USER_KEY);
    }

    setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      isInitialized: true,
    });
  }, []);

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  // ── Storage Helpers ──────────────────────────────────────────────────

  const storeAuthData = (authResponse: AuthResponse) => {
    localStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
  };

  const clearAuthStorage = () => {
    localStorage.removeItem(USER_KEY);
  };

  // ── Login ────────────────────────────────────────────────────────────

  const login = useCallback(async (email: string, password: string): Promise<AuthResponse> => {
    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await authApi.login({ email, password });
      storeAuthData(response);

      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });

      return response;
    } catch (error) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(getErrorMessage(error));
    }
  }, []);

  // ── Register ─────────────────────────────────────────────────────────

  const register = useCallback(async (data: RegisterRequest): Promise<AuthResponse> => {
    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await authApi.register(data);
      storeAuthData(response);

      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });

      return response;
    } catch (error) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(getErrorMessage(error));
    }
  }, []);

  // ── Login with Google ────────────────────────────────────────────────

  const loginWithGoogle = useCallback(async (idToken: string): Promise<AuthResponse> => {
    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await authApi.googleAuth({ id_token: idToken });
      storeAuthData(response);

      setState({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });

      return response;
    } catch (error) {
      setState(prev => ({ ...prev, isLoading: false }));
      throw new Error(getErrorMessage(error));
    }
  }, []);

  // ── Logout ───────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    try {
      await authApi.logout().catch(() => {});
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      clearAuthStorage();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        isInitialized: true,
      });
      // Redirect to home page after logout
      if (typeof window !== 'undefined') {
        try {
          useAppStore.getState().setAuth(false);
        } catch {
          // Store not available
        }
        // Only redirect if we're on a protected page
        if (window.location.pathname.startsWith('/dashboard') || window.location.pathname.startsWith('/onboarding')) {
          window.location.href = '/';
        }
      }
    }
  }, []);

  // ── Refresh Session ──────────────────────────────────────────────────

  const refreshSession = useCallback(async () => {
    try {
      await authApi.refresh();
    } catch (error) {
      clearAuthStorage();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        isInitialized: true,
      });
      throw error;
    }
  }, []);

  // ── Check Email Availability ─────────────────────────────────────────

  const checkEmailAvailability = useCallback(async (email: string): Promise<boolean> => {
    try {
      const response = await authApi.checkEmail(email);
      return response.available;
    } catch {
      return false;
    }
  }, []);

  // ── Hydrate from localStorage ────────────────────────────────────────
  // Called after login/signup via Next.js API routes that write directly to localStorage.
  // This ONLY sets authenticated=true if called right after a successful login.

  const hydrate = useCallback(() => {
    // Record hydration time so initializeAuth() doesn't overwrite us
    lastHydratedAt.current = Date.now();

    try {
      const user = readUserData();
      if (user) {
        setState({
          user,
          isAuthenticated: true,
          isLoading: false,
          isInitialized: true,
        });
        return;
      }
    } catch {
      // ignore
    }
    setState(prev => ({
      ...prev,
      isAuthenticated: false,
      isLoading: false,
      isInitialized: true,
    }));
  }, []);

  // ── Context Value ────────────────────────────────────────────────────

  const { user, isAuthenticated, isLoading, isInitialized } = state;

  const value = useMemo<AuthContextType>(() => ({
    user,
    isAuthenticated,
    isLoading,
    isInitialized,
    login,
    register,
    loginWithGoogle,
    logout,
    refreshSession,
    checkEmailAvailability,
    hydrate,
  }), [
    user,
    isAuthenticated,
    isLoading,
    isInitialized,
    login,
    register,
    loginWithGoogle,
    logout,
    refreshSession,
    checkEmailAvailability,
    hydrate,
  ]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// ── useAuth Hook ────────────────────────────────────────────────────────

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
