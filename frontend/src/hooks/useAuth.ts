/**
 * PARWA useAuth Hook
 *
 * Custom hook for authentication operations.
 * Wraps the auth store with additional functionality and convenience methods.
 *
 * Features:
 * - Login/logout/register functionality
 * - Session management
 * - Token refresh handling
 * - Auth state access
 */

import { useCallback, useEffect } from "react";
import { useAuthStore } from "../stores/authStore";
import { useUIStore } from "../stores/uiStore";
import type { User } from "../services/api/auth";

/**
 * Auth hook return type.
 */
export interface UseAuthReturn {
  /** Current authenticated user */
  user: User | null;
  /** Whether user is authenticated */
  isAuthenticated: boolean;
  /** Loading state for auth operations */
  isLoading: boolean;
  /** Error message from last auth operation */
  error: string | null;

  // Actions
  /** Login with email and password */
  login: (email: string, password: string) => Promise<void>;
  /** Register new user */
  register: (name: string, email: string, password: string) => Promise<void>;
  /** Logout current user */
  logout: () => Promise<void>;
  /** Check and restore session */
  checkAuth: () => Promise<void>;
  /** Refresh auth token */
  refreshToken: () => Promise<void>;
  /** Update user profile */
  updateProfile: (data: Partial<Pick<User, "name" | "email">>) => Promise<void>;
  /** Clear any errors */
  clearError: () => void;
}

/**
 * Custom hook for authentication operations.
 *
 * Provides a convenient interface for authentication state and actions.
 * Automatically handles session restoration and token refresh.
 *
 * @returns Authentication state and actions
 *
 * @example
 * ```tsx
 * function LoginPage() {
 *   const { login, isLoading, error, isAuthenticated } = useAuth();
 *
 *   const handleSubmit = async (email: string, password: string) => {
 *     try {
 *       await login(email, password);
 *       // Redirect on success
 *     } catch {
 *       // Error is already in error state
 *     }
 *   };
 *
 *   if (isAuthenticated) {
 *     return <Navigate to="/dashboard" />;
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       {error && <div className="error">{error}</div>}
 *       <button type="submit" disabled={isLoading}>
 *         {isLoading ? "Logging in..." : "Login"}
 *       </button>
 *     </form>
 *   );
 * }
 * ```
 */
export function useAuth(): UseAuthReturn {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    restoreSession,
    updateProfile,
    clearError,
    setToken,
  } = useAuthStore();

  const { addToast } = useUIStore();

  /**
   * Login wrapper with toast notification.
   */
  const handleLogin = useCallback(
    async (email: string, password: string): Promise<void> => {
      try {
        await login(email, password);
        addToast({
          title: "Welcome back!",
          description: `Logged in as ${email}`,
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Login failed";
        addToast({
          title: "Login failed",
          description: message,
          variant: "error",
        });
        throw err;
      }
    },
    [login, addToast]
  );

  /**
   * Register wrapper with toast notification.
   */
  const handleRegister = useCallback(
    async (name: string, email: string, password: string): Promise<void> => {
      try {
        await register(name, email, password);
        addToast({
          title: "Account created!",
          description: `Welcome to PARWA, ${name}!`,
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Registration failed";
        addToast({
          title: "Registration failed",
          description: message,
          variant: "error",
        });
        throw err;
      }
    },
    [register, addToast]
  );

  /**
   * Logout wrapper with toast notification.
   */
  const handleLogout = useCallback(async (): Promise<void> => {
    try {
      await logout();
      addToast({
        title: "Logged out",
        description: "You have been logged out successfully.",
        variant: "default",
      });
    } catch (err) {
      // Still show toast even if API call fails
      addToast({
        title: "Logged out",
        description: "You have been logged out.",
        variant: "default",
      });
    }
  }, [logout, addToast]);

  /**
   * Check auth and restore session if token exists.
   */
  const checkAuth = useCallback(async (): Promise<void> => {
    await restoreSession();
  }, [restoreSession]);

  /**
   * Refresh the auth token.
   */
  const refreshToken = useCallback(async (): Promise<void> => {
    try {
      // Import authAPI dynamically to avoid circular dependencies
      const { authAPI } = await import("../services/api/auth");
      const response = await authAPI.refreshToken();
      setToken(response.token);
    } catch (err) {
      // Token refresh failed - logout user
      await logout();
      throw err;
    }
  }, [setToken, logout]);

  /**
   * Update profile wrapper with toast notification.
   */
  const handleUpdateProfile = useCallback(
    async (data: Partial<Pick<User, "name" | "email">>): Promise<void> => {
      try {
        await updateProfile(data);
        addToast({
          title: "Profile updated",
          description: "Your profile has been updated successfully.",
          variant: "success",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Profile update failed";
        addToast({
          title: "Update failed",
          description: message,
          variant: "error",
        });
        throw err;
      }
    },
    [updateProfile, addToast]
  );

  /**
   * Auto-restore session on mount.
   */
  useEffect(() => {
    if (!isAuthenticated) {
      restoreSession();
    }
  }, [isAuthenticated, restoreSession]);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
    checkAuth,
    refreshToken,
    updateProfile: handleUpdateProfile,
    clearError,
  };
}

export default useAuth;
