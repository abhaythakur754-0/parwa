'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  company_id: string;
  company_name: string;
  industry: string;
  subscription_variant: string;
  is_active: boolean;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  refreshAuth: () => Promise<void>;
}

interface RegisterData {
  company_name: string;
  industry: string;
  user_name: string;
  email: string;
  password: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const API_BASE = '/api/v1';

async function authFetch(path: string, options: RequestInit = {}) {
  const url = `${API_BASE}${path}${path.includes('?') ? '&' : '?'}XTransformPort=8000`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(body.detail || `Request failed with status ${res.status}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load tokens from localStorage on mount
  useEffect(() => {
    try {
      const savedTokens = localStorage.getItem('parwa-tokens');
      const savedUser = localStorage.getItem('parwa-user');

      if (savedTokens && savedUser) {
        const parsedTokens = JSON.parse(savedTokens);
        const parsedUser = JSON.parse(savedUser);
        setTokens(parsedTokens);
        setUser(parsedUser);
      }
    } catch {
      // ignore parse errors
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!tokens?.refresh_token) return;

    // Refresh every 25 minutes (tokens expire at 30 min)
    refreshTimerRef.current = setInterval(async () => {
      try {
        await refreshAuth();
      } catch {
        // If refresh fails, logout
        logout();
      }
    }, 25 * 60 * 1000);

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [tokens?.refresh_token]);

  // Save tokens to localStorage whenever they change
  useEffect(() => {
    if (tokens && user) {
      localStorage.setItem('parwa-tokens', JSON.stringify(tokens));
      localStorage.setItem('parwa-user', JSON.stringify(user));
    } else {
      localStorage.removeItem('parwa-tokens');
      localStorage.removeItem('parwa-user');
    }
  }, [tokens, user]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    const newTokens: AuthTokens = {
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    };
    setTokens(newTokens);

    // Fetch user info
    const userInfo = await authFetch('/auth/me', {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    setUser(userInfo);
  }, []);

  const register = useCallback(async (data: RegisterData) => {
    const res = await authFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });

    const newTokens: AuthTokens = {
      access_token: res.access_token,
      refresh_token: res.refresh_token,
    };
    setTokens(newTokens);

    // Fetch user info
    const userInfo = await authFetch('/auth/me', {
      headers: { Authorization: `Bearer ${res.access_token}` },
    });
    setUser(userInfo);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setTokens(null);
    localStorage.removeItem('parwa-tokens');
    localStorage.removeItem('parwa-user');
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
    }
    router.push('/auth/login');
  }, [router]);

  const refreshAuth = useCallback(async () => {
    if (!tokens?.refresh_token) {
      logout();
      return;
    }

    try {
      const data = await authFetch('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      });

      const newTokens: AuthTokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      };
      setTokens(newTokens);

      // Re-fetch user info with new token
      const userInfo = await authFetch('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      setUser(userInfo);
    } catch {
      logout();
    }
  }, [tokens?.refresh_token, logout]);

  const value: AuthContextType = {
    user,
    tokens,
    isLoading,
    isAuthenticated: !!user && !!tokens,
    login,
    register,
    logout,
    refreshAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// ---------------------------------------------------------------------------
// Auth helper for API calls
// ---------------------------------------------------------------------------

export function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  try {
    const saved = localStorage.getItem('parwa-tokens');
    if (!saved) return {};
    const tokens = JSON.parse(saved);
    return { Authorization: `Bearer ${tokens.access_token}` };
  } catch {
    return {};
  }
}
