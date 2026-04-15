'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  User,
  AuthResponse,
  AuthState,
  AuthContextType,
  RegisterRequest,
} from '@/types/auth';
import { authApi } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';

// ── Auth Context ────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ── Storage Keys (localStorage for user data ONLY, never tokens) ────────

const USER_KEY = 'parwa_user';

// ── Auth Provider ───────────────────────────────────────────────────────

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
    isInitialized: false,
  });

  // ── Initialize Auth State ────────────────────────────────────────────

  const initializeAuth = useCallback(async () => {
    try {
      // FIX A2: No longer check localStorage for tokens.
      // Tokens are stored exclusively in httpOnly cookies (parwa_session).
      // Instead, verify the session by calling /api/auth/me which reads the cookie.
      try {
        const currentUser = await Promise.race([
          authApi.getMe(),
          new Promise<never>((_, reject) => 
            setTimeout(() => reject(new Error('Auth check timeout')), 5000)
          ),
        ]);
        // Store user data in localStorage for UI hydration (not tokens)
        localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
        setState({
          user: currentUser,
          isAuthenticated: true,
          isLoading: false,
          isInitialized: true,
        });
        return;
      } catch {
        // Session invalid or backend unreachable, clear user data
        clearAuthStorage();
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  // ── Storage Helpers (user data only, NEVER tokens) ───────────────────

  const storeUserData = (authResponse: AuthResponse) => {
    // FIX A2: Store ONLY user data in localStorage, never tokens.
    // Tokens are handled exclusively via httpOnly cookies set by the server.
    localStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
  };

  const clearAuthStorage = () => {
    // FIX A2: Only clear user data, not tokens (tokens are httpOnly cookies)
    localStorage.removeItem(USER_KEY);
  };

  // ── Login ────────────────────────────────────────────────────────────

  const login = useCallback(async (email: string, password: string): Promise<AuthResponse> => {
    setState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await authApi.login({ email, password });
      storeUserData(response);

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
      storeUserData(response);

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
      storeUserData(response);

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
      // FIX A2: Call server-side logout to clear httpOnly cookie.
      // No need to send refresh_token from localStorage — the server
      // reads it from the httpOnly cookie.
      await authApi.logout({ refresh_token: '' });
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
      router.push('/login');
    }
  }, [router]);

  // ── Refresh Session ──────────────────────────────────────────────────

  const refreshSession = useCallback(async () => {
    // FIX A2: Token refresh is handled by the API interceptor in api.ts.
    // The interceptor calls /api/auth/refresh with the httpOnly cookie
    // and gets new cookies set automatically.
    // This method is kept for backwards compatibility but does nothing.
    try {
      await authApi.refresh({ refresh_token: '' });
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

  const hydrate = useCallback(() => {
    try {
      const storedUser = localStorage.getItem(USER_KEY);
      if (storedUser) {
        const user = JSON.parse(storedUser) as User;
        if (user && user.email) {
          setState({
            user,
            isAuthenticated: true,
            isLoading: false,
            isInitialized: true,
          });
          return;
        }
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

  // ── D9-P12: Cross-tab session synchronisation ──────────────────────
  useEffect(() => {
    const handleSessionExpired = () => {
      clearAuthStorage();
      setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        isInitialized: true,
      });
      router.push('/login');
    };

    // FIX A2: Listen for storage events to detect logout from another tab.
    // Since tokens are now in httpOnly cookies, we only sync user data state.
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === USER_KEY && !e.newValue) {
        clearAuthStorage();
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          isInitialized: true,
        });
        router.push('/login');
      }
    };

    window.addEventListener('parwa:session-expired', handleSessionExpired);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('parwa:session-expired', handleSessionExpired);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [router]);

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
