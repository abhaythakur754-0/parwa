/**
 * PARWA Auth Store
 *
 * Zustand store for managing authentication state.
 * Handles user, token, and authentication status.
 */

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User } from "../services/api/auth";
import { authAPI } from "../services/api/auth";
import { apiClient } from "../services/api/client";

/**
 * Auth state interface.
 */
export interface AuthState {
  /** Current authenticated user */
  user: User | null;
  /** Auth token */
  token: string | null;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  /** Loading state for auth operations */
  isLoading: boolean;
  /** Error message from last auth operation */
  error: string | null;

  // Actions
  /** Login with credentials */
  login: (email: string, password: string) => Promise<void>;
  /** Register new user */
  register: (name: string, email: string, password: string) => Promise<void>;
  /** Logout current user */
  logout: () => Promise<void>;
  /** Set user directly */
  setUser: (user: User | null) => void;
  /** Set token directly */
  setToken: (token: string | null) => void;
  /** Clear any errors */
  clearError: () => void;
  /** Check and restore session */
  restoreSession: () => Promise<void>;
  /** Update user profile */
  updateProfile: (data: Partial<Pick<User, "name" | "email">>) => Promise<void>;
}

/**
 * Initial auth state.
 */
const initialState = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
};

/**
 * Auth store using Zustand with persistence.
 *
 * @example
 * ```tsx
 * function LoginPage() {
 *   const { login, isLoading, error } = useAuthStore();
 *
 *   const handleLogin = async (email: string, password: string) => {
 *     try {
 *       await login(email, password);
 *       // Redirect to dashboard
 *     } catch (e) {
 *       // Error is already set in store
 *     }
 *   };
 *
 *   return <form>...</form>;
 * }
 * ```
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...initialState,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authAPI.login({ email, password });

          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Set token in API client
          apiClient.setAuthToken(response.token);
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Login failed";
          set({
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },

      register: async (name: string, email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          const response = await authAPI.register({
            name,
            email,
            password,
          });

          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });

          // Set token in API client
          apiClient.setAuthToken(response.token);
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Registration failed";
          set({
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true });

        try {
          await authAPI.logout();
        } catch {
          // Ignore logout errors - we'll clear local state anyway
        } finally {
          set({
            ...initialState,
            isLoading: false,
          });
          apiClient.clearAuthToken();
        }
      },

      setUser: (user: User | null) => {
        set({
          user,
          isAuthenticated: user !== null,
        });
      },

      setToken: (token: string | null) => {
        set({ token });
        if (token) {
          apiClient.setAuthToken(token);
        } else {
          apiClient.clearAuthToken();
        }
      },

      clearError: () => {
        set({ error: null });
      },

      restoreSession: async () => {
        const { token } = get();

        if (!token) {
          return;
        }

        set({ isLoading: true });

        try {
          // Set token in API client first
          apiClient.setAuthToken(token);

          // Fetch current user
          const user = await authAPI.getCurrentUser();

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          // Token is invalid - clear state
          set({
            ...initialState,
            isLoading: false,
          });
          apiClient.clearAuthToken();
        }
      },

      updateProfile: async (data: Partial<Pick<User, "name" | "email">>) => {
        set({ isLoading: true, error: null });

        try {
          const updatedUser = await authAPI.updateProfile(data);

          set({
            user: updatedUser,
            isLoading: false,
          });
        } catch (error) {
          const message =
            error instanceof Error ? error.message : "Profile update failed";
          set({
            isLoading: false,
            error: message,
          });
          throw error;
        }
      },
    }),
    {
      name: "parwa-auth",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

/**
 * Hook to get just the user.
 */
export function useUser() {
  return useAuthStore((state) => state.user);
}

/**
 * Hook to check if authenticated.
 */
export function useIsAuthenticated() {
  return useAuthStore((state) => state.isAuthenticated);
}

/**
 * Hook to get auth loading state.
 */
export function useAuthLoading() {
  return useAuthStore((state) => state.isLoading);
}

/**
 * Hook to get auth error.
 */
export function useAuthError() {
  return useAuthStore((state) => state.error);
}

export default useAuthStore;
