/**
 * PARWA Auth API
 *
 * Authentication API functions for login, register, logout, and password management.
 */

import { apiClient, APIError } from "./client";

/**
 * User object returned from auth endpoints.
 */
export interface User {
  /** Unique user ID */
  id: string;
  /** User's email address */
  email: string;
  /** User's display name */
  name: string;
  /** User's company ID */
  companyId?: string;
  /** User's role */
  role: "admin" | "agent" | "viewer";
  /** When the user was created */
  createdAt: string;
  /** Last login timestamp */
  lastLoginAt?: string;
}

/**
 * Login credentials.
 */
export interface LoginCredentials {
  /** User's email */
  email: string;
  /** User's password */
  password: string;
}

/**
 * Registration data.
 */
export interface RegisterData {
  /** User's name */
  name: string;
  /** User's email */
  email: string;
  /** User's password */
  password: string;
  /** Company name (optional) */
  companyName?: string;
}

/**
 * Auth response containing user and token.
 */
export interface AuthResponse {
  /** Authenticated user */
  user: User;
  /** JWT auth token */
  token: string;
  /** Refresh token (if applicable) */
  refreshToken?: string;
}

/**
 * Password reset request.
 */
export interface ForgotPasswordRequest {
  /** User's email */
  email: string;
}

/**
 * Password reset confirmation.
 */
export interface ResetPasswordRequest {
  /** Reset token from email */
  token: string;
  /** New password */
  password: string;
}

/**
 * Auth API functions.
 */
export const authAPI = {
  /**
   * Login with email and password.
   *
   * @param credentials - Login credentials
   * @returns Auth response with user and token
   * @throws APIError on failure
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>("/auth/login", credentials, {
      includeAuth: false,
    });

    // Store the auth token
    if (response.data.token) {
      apiClient.setAuthToken(response.data.token);
    }

    return response.data;
  },

  /**
   * Register a new user.
   *
   * @param data - Registration data
   * @returns Auth response with user and token
   * @throws APIError on failure
   */
  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>("/auth/register", data, {
      includeAuth: false,
    });

    // Store the auth token
    if (response.data.token) {
      apiClient.setAuthToken(response.data.token);
    }

    return response.data;
  },

  /**
   * Logout the current user.
   *
   * @returns void
   * @throws APIError on failure
   */
  async logout(): Promise<void> {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      // Always clear the token, even if the API call fails
      apiClient.clearAuthToken();
    }
  },

  /**
   * Request a password reset email.
   *
   * @param email - User's email address
   * @returns Success indicator
   * @throws APIError on failure
   */
  async forgotPassword(email: string): Promise<{ success: boolean }> {
    const response = await apiClient.post<{ success: boolean }>(
      "/auth/forgot-password",
      { email },
      { includeAuth: false }
    );

    return response.data;
  },

  /**
   * Reset password with token from email.
   *
   * @param data - Reset password data
   * @returns Success indicator
   * @throws APIError on failure
   */
  async resetPassword(data: ResetPasswordRequest): Promise<{ success: boolean }> {
    const response = await apiClient.post<{ success: boolean }>(
      "/auth/reset-password",
      data,
      { includeAuth: false }
    );

    return response.data;
  },

  /**
   * Get the current authenticated user.
   *
   * @returns Current user
   * @throws APIError on failure or if not authenticated
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>("/auth/me");

    return response.data;
  },

  /**
   * Refresh the auth token.
   *
   * @returns New auth response with fresh token
   * @throws APIError on failure
   */
  async refreshToken(): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>("/auth/refresh");

    // Store the new auth token
    if (response.data.token) {
      apiClient.setAuthToken(response.data.token);
    }

    return response.data;
  },

  /**
   * Update user profile.
   *
   * @param data - Profile update data
   * @returns Updated user
   * @throws APIError on failure
   */
  async updateProfile(data: Partial<Pick<User, "name" | "email">>): Promise<User> {
    const response = await apiClient.patch<User>("/auth/profile", data);

    return response.data;
  },

  /**
   * Change user password.
   *
   * @param currentPassword - Current password
   * @param newPassword - New password
   * @returns Success indicator
   * @throws APIError on failure
   */
  async changePassword(
    currentPassword: string,
    newPassword: string
  ): Promise<{ success: boolean }> {
    const response = await apiClient.post<{ success: boolean }>(
      "/auth/change-password",
      {
        currentPassword,
        newPassword,
      }
    );

    return response.data;
  },

  /**
   * Check if user is currently authenticated.
   *
   * @returns True if authenticated
   */
  isAuthenticated(): boolean {
    return apiClient.getAuthToken() !== null;
  },
};

export default authAPI;
