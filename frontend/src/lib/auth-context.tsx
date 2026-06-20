'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

interface AuthState {
  tenantId: string;
  tenantName: string;
  adminEmail: string;
  jwtToken: string;
  apiKey: string;
  tier: string;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: { tenantId: string; tenantName: string; adminEmail: string; jwtToken: string; apiKey: string; tier?: string }) => void;
  logout: () => void;
  setAuth: (data: Partial<AuthState>) => void;
}

const STORAGE_KEY = 'parwa_auth';

const defaultState: AuthState = {
  tenantId: '',
  tenantName: '',
  adminEmail: '',
  jwtToken: '',
  apiKey: '',
  tier: '',
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
  setAuth: () => {},
};

const AuthContext = createContext<AuthState>(defaultState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setState({
          ...defaultState,
          ...parsed,
          isLoading: false,
          isAuthenticated: !!(parsed.tenantId && (parsed.jwtToken || parsed.apiKey)),
        });
      } else {
        setState((prev) => ({ ...prev, isLoading: false }));
      }
    } catch {
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  // Persist to localStorage when auth state changes
  useEffect(() => {
    if (state.isLoading) return;
    try {
      if (state.isAuthenticated) {
        const toStore = {
          tenantId: state.tenantId,
          tenantName: state.tenantName,
          adminEmail: state.adminEmail,
          jwtToken: state.jwtToken,
          apiKey: state.apiKey,
          tier: state.tier,
          isAuthenticated: state.isAuthenticated,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // Storage full or blocked
    }
  }, [state.isAuthenticated, state.tenantId, state.tenantName, state.adminEmail, state.jwtToken, state.apiKey, state.tier, state.isLoading]);

  const login = useCallback((data: {
    tenantId: string;
    tenantName: string;
    adminEmail: string;
    jwtToken: string;
    apiKey: string;
    tier?: string;
  }) => {
    setState({
      ...defaultState,
      isLoading: false,
      isAuthenticated: true,
      tenantId: data.tenantId,
      tenantName: data.tenantName,
      adminEmail: data.adminEmail,
      jwtToken: data.jwtToken,
      apiKey: data.apiKey,
      tier: data.tier || '',
    });
    // Set cookie for middleware (edge can't read localStorage)
    if (typeof document !== 'undefined') {
      document.cookie = `parwa_auth_jwt=${data.jwtToken}; path=/; max-age=86400; SameSite=Lax`;
    }
  }, []);

  const logout = useCallback(() => {
    setState({
      ...defaultState,
      isLoading: false,
    });
    if (typeof document !== 'undefined') {
      document.cookie = 'parwa_auth_jwt=; path=/; max-age=0';
    }
  }, []);

  const setAuth = useCallback((data: Partial<AuthState>) => {
    setState((prev) => ({
      ...prev,
      ...data,
      isAuthenticated: data.tenantId ? (prev.isAuthenticated || !!(data.jwtToken || data.apiKey || prev.jwtToken || prev.apiKey)) : prev.isAuthenticated,
      isLoading: false,
    }));
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, setAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Module-level helper for hooks that can't use React context
let _currentTenantId = 'default_tenant';

export function getCurrentTenantId(): string {
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.tenantId) {
          _currentTenantId = parsed.tenantId;
          return parsed.tenantId;
        }
      }
    } catch {
      // Fall through
    }
  }
  return _currentTenantId;
}

export function setCurrentTenantId(id: string) {
  _currentTenantId = id;
}
