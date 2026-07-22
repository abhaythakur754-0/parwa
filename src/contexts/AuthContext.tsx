'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
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

  // ── Initialize Auth State ────────────────────────────────────────────
  // CRITICAL: We must NOT trust stale localStorage data if the backend
  // explicitly rejects the auth (401). This was causing infinite redirect
  // loops because the client thought it was authenticated but the
  // middleware kept rejecting requests (no valid cookie).

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

      // We have cached user data — verify with backend.
      //
      // Timeout strategy (Render cold starts can take 10-30 seconds):
      //   - First attempt: 8 second timeout (was 3s — too short for cold start)
      //   - Retry ONLY if first attempt timed out (transient slowness)
      //   - Skip retry on network error (backend definitely down — retrying wastes time)
      //   - Retry attempt: 8 second timeout
      //   - Max total wait: ~16 seconds
      const verifyWithBackend = async (): Promise<Response | null> => {
        const doFetch = (ms: number) =>
          fetch('/api/auth/me-proxy', {
            method: 'GET',
            credentials: 'include',
            signal: AbortSignal.timeout(ms),
          });

        try {
          return await doFetch(8000);
        } catch (err) {
          // If it was a timeout (AbortError), the backend might be slow
          // (Render cold start). Retry once. If it was a network error
          // (TypeError: Failed to fetch), the backend is definitely down
          // — don't waste time retrying.
          const isTimeout =
            err instanceof Error &&
            (err.name === 'TimeoutError' || err.name === 'AbortError');
          if (!isTimeout) return null;

          try {
            return await doFetch(8000);
          } catch {
            return null;
          }
        }
      };

      try {
        const response = await verifyWithBackend();

        if (response && response.ok) {
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
              backendUnreachable: false,
            });
            return;
          }
          // JSON parse succeeded but no valid user — fall through
        }

        // If response is null, the backend was unreachable on both attempts.
        if (response === null) {
          console.warn('[AuthContext] Backend unreachable (2 retries exhausted) — using cached data, staying logged in');
          setState({
            user: cachedUser,
            isAuthenticated: true, // Stay logged in with cached data (Netflix-style — don't log out on cold start)
            isLoading: false,
            isInitialized: true,
            backendUnreachable: true, // UI can show "backend warming up" banner
          });
          return;
        }

        // Backend returned 401/403 — access token may be expired.
        // Try to refresh the token using the refresh token (parwa_rt cookie).
        // Only if refresh ALSO fails do we log the user out.
        if (response && (response.status === 401 || response.status === 403)) {
          console.warn('[AuthContext] Access token expired — attempting refresh');
          try {
            const refreshRes = await fetch('/api/auth/refresh', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: '{}',
              signal: AbortSignal.timeout(5000),
            });

            if (refreshRes.ok) {
              // Refresh succeeded — retry the me-proxy call to get user data
              const retryRes = await fetch('/api/auth/me-proxy', {
                method: 'GET',
                credentials: 'include',
                signal: AbortSignal.timeout(3000),
              });

              if (retryRes.ok) {
                let retryUser: User | null = null;
                try {
                  const text = await retryRes.text();
                  retryUser = JSON.parse(text) as User;
                } catch { /* non-JSON */ }

                if (retryUser) {
                  console.warn('[AuthContext] Token refreshed — staying logged in');
                  setState({
                    user: retryUser,
                    isAuthenticated: true,
                    isLoading: false,
                    isInitialized: true,
                    backendUnreachable: false,
                  });
                  return;
                }
              }
            }

            // Refresh also failed — session is truly invalid
            console.warn('[AuthContext] Token refresh failed — logging out');
            localStorage.removeItem(USER_KEY);
          } catch (refreshErr) {
            // Refresh endpoint unreachable — stay logged in with cached data
            // (Netflix-style — don't log out during backend cold start)
            console.warn('[AuthContext] Refresh endpoint unreachable — staying logged in with cached data');
            setState({
              user: cachedUser,
              isAuthenticated: true,
              isLoading: false,
              isInitialized: true,
              backendUnreachable: true,
            });
            return;
          }
        } else {
          // Non-401 error (e.g. 500, non-JSON) — stay logged in with cached data
          console.warn('[AuthContext] Backend returned non-401 error — staying logged in with cached data');
          setState({
            user: cachedUser,
            isAuthenticated: true,
            isLoading: false,
            isInitialized: true,
            backendUnreachable: true,
          });
          return;
        }
      } catch (networkError) {
        // Network error after retries — backend unreachable.
        // Stay logged in with cached data so user isn't bounced to /login
        // (Netflix-style — don't log out during backend cold start).
        console.warn('[AuthContext] Backend unreachable — staying logged in with cached data');
        setState({
          user: cachedUser,
          isAuthenticated: true, // Stay logged in (don't log out on cold start)
          isLoading: false,
          isInitialized: true,
          backendUnreachable: true,
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
