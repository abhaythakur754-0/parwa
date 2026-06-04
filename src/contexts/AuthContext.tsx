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

// ── Storage Keys ────────────────────────────────────────────────────────
// Tokens are stored ONLY in httpOnly cookies (parwa_at, parwa_rt) set by the backend.
// Only non-sensitive user display data is kept in localStorage / cookie.

const USER_KEY = 'parwa_user';

/** Read a cookie value by name (non-httpOnly cookies only). */
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Read user data from the non-httpOnly parwa_user cookie, falling back to localStorage. */
function readUserData(): User | null {
  // Try cookie first (set by backend)
  const cookieVal = getCookie('parwa_user');
  if (cookieVal) {
    try {
      const user = JSON.parse(cookieVal) as User;
      if (user && user.email) return user;
    } catch {
      // corrupt cookie — fall through
    }
  }
  // Fallback to localStorage
  const stored = localStorage.getItem(USER_KEY);
  if (stored) {
    try {
      const user = JSON.parse(stored) as User;
      if (user && user.email) return user;
    } catch {
      // corrupt data
    }
  }
  return null;
}

// ── Auth Provider ───────────────────────────────────────────────────────

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    isInitialized: false,
  });

  // ── Initialize Auth State ────────────────────────────────────────────

  const initializeAuth = useCallback(async () => {
    try {
      // Read user data from cookie or localStorage
      const user = readUserData();

      if (user) {
        // Best-effort verification with the backend (httpOnly cookie carries the token)
        try {
          const currentUser = await Promise.race([
            authApi.getMe(),
            new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error('Auth check timeout')), 5000)
            ),
          ]);
          setState({
            user: currentUser,
            isAuthenticated: true,
            isLoading: false,
            isInitialized: true,
          });
          return;
        } catch {
          // Backend unreachable or token expired — still trust cached user data
        }

        setState({
          user,
          isAuthenticated: true,
          isLoading: false,
          isInitialized: true,
        });
        return;
      }
    } catch (error) {
      console.error('Auth initialization error:', error);
      clearAuthStorage();
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
    // Only store non-sensitive user data. Tokens live in httpOnly cookies.
    localStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
  };

  const clearAuthStorage = () => {
    // Only clear user display data. Tokens are httpOnly cookies cleared by the backend.
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
      // Call logout API — backend clears httpOnly cookies (parwa_at, parwa_rt, parwa_user).
      // The refresh token is read from the httpOnly cookie, not localStorage.
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
      // Use Zustand store for SPA navigation instead of hash routing
      if (typeof window !== 'undefined') {
        try {
          useAppStore.getState().setAuth(false);
        } catch {
          // Store not available — silent fail
        }
      }
    }
  }, []);

  // ── Refresh Session ──────────────────────────────────────────────────

  const refreshSession = useCallback(async () => {
    try {
      // Call refresh endpoint — backend reads refresh_token from httpOnly cookie (parwa_rt)
      // and sets new httpOnly cookies automatically. No localStorage token handling.
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

  const hydrate = useCallback(() => {
    try {
      // Read user from cookie first, then localStorage
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

  const value = useMemo<AuthContextType>(() => ({
    ...state,
    login,
    register,
    loginWithGoogle,
    logout,
    refreshSession,
    checkEmailAvailability,
    hydrate,
  }), [
    state,
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

// ── Export ──────────────────────────────────────────────────────────────

export default AuthContext;
