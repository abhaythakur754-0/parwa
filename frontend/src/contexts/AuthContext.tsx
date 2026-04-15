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

// ── Storage Keys ────────────────────────────────────────────────────────

const AUTH_TOKEN_KEY = 'parwa_access_token';
const REFRESH_TOKEN_KEY = 'parwa_refresh_token';
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
      // Check for existing session
      const storedUser = localStorage.getItem(USER_KEY);
      const accessToken = localStorage.getItem(AUTH_TOKEN_KEY);

      if (storedUser && accessToken) {
        const user = JSON.parse(storedUser) as User;
        
        // Verify the session is still valid by fetching user profile
        // Use a short timeout (5s) for init check to avoid blocking the UI
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
          // Session invalid or backend unreachable, clear storage
          clearAuthStorage();
        }
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

  // ── Storage Helpers ──────────────────────────────────────────────────

  const storeAuthData = (authResponse: AuthResponse) => {
    localStorage.setItem(AUTH_TOKEN_KEY, authResponse.tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, authResponse.tokens.refresh_token);
    localStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
  };

  const clearAuthStorage = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
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
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        await authApi.logout({ refresh_token: refreshToken });
      }
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
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const tokens = await authApi.refresh({ refresh_token: refreshToken });
      localStorage.setItem(AUTH_TOKEN_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
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

  // ── D9-P12: Cross-tab token synchronisation ──────────────────────
  // Listen for parwa:session-expired dispatched by the 401 interceptor
  // (api.ts) so that all tabs log out together when the refresh token dies.
  // Also listen for native 'storage' events to detect token changes made
  // in another tab (login, logout, delete account).
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

    const handleStorageChange = (e: StorageEvent) => {
      // If another tab cleared the token, we must also log out
      if (e.key === AUTH_TOKEN_KEY && !e.newValue) {
        clearAuthStorage();
        setState({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          isInitialized: true,
        });
        router.push('/login');
      }
      // If another tab set a new token (fresh login), hydrate from storage
      if (e.key === AUTH_TOKEN_KEY && e.newValue) {
        hydrate();
      }
    };

    window.addEventListener('parwa:session-expired', handleSessionExpired);
    window.addEventListener('storage', handleStorageChange);
    return () => {
      window.removeEventListener('parwa:session-expired', handleSessionExpired);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [router, hydrate]);

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
