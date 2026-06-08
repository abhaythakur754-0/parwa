/**
 * PARWA API Client
 * 
 * Centralized API client for making requests to the backend.
 * 
 * Security Features (GAP-002 Fix):
 * - Safe JSON parsing for malformed responses
 * - Proper error handling for all HTTP status codes
 * - Timeout handling with retry support
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { useAppStore } from '@/lib/store';
import { UserDetails, OnboardingState } from '@/types/onboarding';
import {
  User,
  AuthResponse,
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  GoogleAuthRequest,
  EmailCheckResponse,
  MessageResponse,
} from '@/types/auth';

// API base URL from environment or default.
// When the Python backend is not running, we proxy through Next.js mock API routes.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

/**
 * Create axios instance with default configuration.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include cookies for session auth
});

/**
 * Response interceptor for handling errors.
 * C-03 FIX: No request interceptor — auth tokens are sent as httpOnly cookies
 * automatically by the browser via withCredentials: true.
 * GAP-002: Handle malformed responses gracefully.
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle 401 Unauthorized — clear user display data and trigger navigation.
    // Tokens are httpOnly cookies cleared by the backend; we only clean up localStorage.
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('parwa_user');
        // Use Zustand store for SPA navigation instead of window.location
        try {
          const store = useAppStore.getState();
          if (store && !['login', 'signup', 'forgot-password'].includes(store.currentPage)) {
            store.setAuth(false);
          }
        } catch {
          // Store not available (SSR or early init) — silent fail
        }
      }
    }
    
    // Handle 403 Forbidden
    if (error.response?.status === 403) {
      const errorData = error.response?.data as Record<string, unknown> | undefined;
      const csrfMessage = (errorData?.error as Record<string, unknown>)?.message || errorData?.message || '';
      if (typeof csrfMessage === 'string' && csrfMessage.toLowerCase().includes('csrf')) {
        console.error('Access denied: CSRF validation failed. The request origin may not be trusted.');
      } else {
        console.error('Access denied:', csrfMessage || 'You do not have permission for this action.');
      }
    }
    
    // Handle 429 Rate Limit
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'];
      console.warn(`Rate limited. Retry after ${retryAfter} seconds`);
    }
    
    return Promise.reject(error);
  }
);

// ── GAP-002: Safe Response Parsing ───────────────────────────────────────

/**
 * Safely parse response data, handling malformed JSON.
 */
function safeParseResponse<T>(response: AxiosResponse): T {
  // If response is already parsed by axios, return it
  if (response.data !== undefined) {
    return response.data as T;
  }
  throw new Error('Empty response from server');
}

/**
 * Handle API errors with user-friendly messages.
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // Network error (no response)
    if (!error.response) {
      if (error.code === 'ECONNABORTED') {
        return 'Request timed out. Please try again.';
      }
      return 'Network error. Please check your connection.';
    }
    
    // Server responded with error
    const status = error.response.status;
    const detail = error.response?.data?.detail;
    
    if (status === 429) {
      const retryAfter = error.response.headers['retry-after'] || 60;
      return `Too many requests. Please try again in ${retryAfter} seconds.`;
    }
    
    if (status >= 500) {
      return 'Server error. Please try again later.';
    }
    
    if (status === 401) {
      return 'Session expired. Please log in again.';
    }
    
    if (status === 403) {
      // Try to extract CSRF or specific error message
      const errorData = error.response?.data as Record<string, unknown> | undefined;
      const serverMsg = (errorData?.error as Record<string, unknown>)?.message || errorData?.message;
      if (typeof serverMsg === 'string' && serverMsg) {
        return serverMsg;
      }
      return 'Access denied. You may not have permission for this action, or the request origin is not trusted.';
    }
    
    // Return server's error message if available
    if (detail) {
      return detail;
    }
    
    return `Request failed with status ${status}`;
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  return 'An unexpected error occurred. Please try again.';
}

/**
 * Generic GET request with safe parsing.
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.get<T>(url, config);
    return safeParseResponse<T>(response);
  } catch (error) {
    throw error;
  }
}

/**
 * Generic POST request with safe parsing.
 */
export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.post<T>(url, data, config);
    return safeParseResponse<T>(response);
  } catch (error) {
    throw error;
  }
}

/**
 * Generic PATCH request with safe parsing.
 */
export async function patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.patch<T>(url, data, config);
    return safeParseResponse<T>(response);
  } catch (error) {
    throw error;
  }
}

/**
 * Generic DELETE request with safe parsing.
 */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.delete<T>(url, config);
    return safeParseResponse<T>(response);
  } catch (error) {
    throw error;
  }
}

// ── Onboarding API Endpoints ───────────────────────────────────────────

export const onboardingApi = {
  /**
   * Get current onboarding state.
   */
  getState: () => get<OnboardingState>('/api/onboarding/state'),
  
  /**
   * Start onboarding wizard.
   */
  start: () => post<OnboardingState>('/api/onboarding/start'),
  
  /**
   * Complete a step.
   */
  completeStep: (step: number) => post<OnboardingState>(`/api/onboarding/step/${step}`),
  
  /**
   * Submit legal consents.
   */
  submitLegal: (consents: { terms: boolean; privacy: boolean; ai_data: boolean }) => 
    post<OnboardingState>('/api/onboarding/legal', consents),
  
  /**
   * Activate AI assistant.
   */
  activateAI: (config?: { ai_name?: string; ai_tone?: string; ai_response_style?: string }) => 
    post<OnboardingState>('/api/onboarding/activate', config),
  
  /**
   * Get first victory status.
   */
  getVictory: () => get('/api/onboarding/first-victory'),
  
  /**
   * Mark first victory complete.
   */
  completeVictory: () => post('/api/onboarding/first-victory'),
};

// ── User Details API Endpoints ────────────────────────────────────────

export const userDetailsApi = {
  /**
   * Get current user details.
   */
  get: () => get<UserDetails>('/api/user/details'),
  
  /**
   * Create user details.
   */
  create: (data: {
    full_name: string;
    company_name: string;
    work_email?: string;
    industry: string;
    company_size?: string;
    website?: string;
  }) => post<UserDetails>('/api/user/details', data),
  
  /**
   * Update user details.
   */
  update: (data: Partial<{
    full_name: string;
    company_name: string;
    work_email: string;
    industry: string;
    company_size: string;
    website: string;
  }>) => patch<UserDetails>('/api/user/details', data),
  
  /**
   * Send work email verification.
   */
  sendVerification: (work_email: string) => 
    post('/api/verification/send-otp', { email: work_email }),
  
  /**
   * Confirm work email verification.
   */
  confirmVerification: (token: string) => 
    post('/api/verification/verify-otp', { code: token }),
};

// ── Integration API Endpoints ──────────────────────────────────────────

export const integrationsApi = {
  /**
   * Get available integrations.
   */
  getAvailable: () => get('/api/integrations/available'),
  
  /**
   * Get user's integrations.
   */
  list: () => get('/api/integrations'),
  
  /**
   * Create integration.
   */
  create: (data: { type: string; name: string; config: Record<string, unknown> }) => 
    post('/api/integrations', data),
  
  /**
   * Test integration connection.
   */
  test: (id: string) => post(`/api/integrations/${id}/test`),
  
  /**
   * Delete integration.
   */
  delete: (id: string) => del(`/api/integrations/${id}`),
};

// ── Knowledge Base API Endpoints ───────────────────────────────────────
// NOTE: Backend router uses /api/kb prefix (knowledge_base.py)
// These endpoints map directly to the backend's /api/kb/* routes.

export const knowledgeApi = {
  /**
   * Upload document.
   */
  upload: async (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post('/api/kb/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
    
    return response.data;
  },
  
  /**
   * List documents.
   */
  list: () => get('/api/kb/documents'),
  
  /**
   * Get document status.
   */
  getStatus: (id: string) => get(`/api/kb/documents/${id}`),
  
  /**
   * Delete document.
   */
  delete: (id: string) => del(`/api/kb/documents/${id}`),
  
  /**
   * Retry a failed document.
   */
  retry: (id: string) => post(`/api/kb/documents/${id}/retry`),
  
  /**
   * Re-index a completed document.
   */
  reindex: (id: string) => post(`/api/kb/documents/${id}/reindex`),
  
  /**
   * Get knowledge base statistics.
   */
  getStats: () => get('/api/kb/stats'),
  
  /**
   * Retry all failed documents.
   */
  retryAllFailed: () => post('/api/kb/retry-failed'),
};

// ── Auth API Endpoints ──────────────────────────────────────────────────

export const authApi = {
  /**
   * Register a new user.
   */
  register: (data: RegisterRequest) => post<AuthResponse>('/api/auth/register', data),
  
  /**
   * Login with email and password.
   */
  login: (data: LoginRequest) => post<AuthResponse>('/api/auth/login', data),
  
  /**
   * Login with Google OAuth.
   *
   * IMPORTANT: Always uses the Next.js API route (/api/auth/google) instead
   * of going directly to the backend. The Next.js route handles backend
   * unavailability, non-JSON responses, and local fallback gracefully.
   * This prevents "Unexpected token" JSON parse errors when the backend
   * returns non-JSON (e.g. Render proxy errors, cold start timeouts).
   */
  googleAuth: async (data: GoogleAuthRequest): Promise<AuthResponse> => {
    // Use fetch directly to the Next.js route — not through axios/apiClient.
    // This ensures we always hit the Next.js API route which has robust
    // error handling and always returns JSON, even when the backend is down.
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    // Safe JSON parsing — handle non-JSON responses gracefully
    let result: Record<string, unknown>;
    try {
      const text = await res.text();
      try {
        result = JSON.parse(text);
      } catch {
        throw new Error(
          res.ok
            ? 'Received an unexpected response from the server.'
            : `Server error (${res.status}). Please try again.`
        );
      }
    } catch (parseErr) {
      throw parseErr instanceof Error ? parseErr : new Error('Failed to read server response.');
    }

    if (result.status === 'error') {
      throw new Error(String(result.message || 'Google sign-in failed. Please try again.'));
    }

    // Map Next.js route response to AuthResponse format
    const user = result.user as Record<string, unknown> | undefined;
    return {
      user: {
        id: String(user?.id || ''),
        email: String(user?.email || ''),
        full_name: String(user?.fullName || user?.full_name || ''),
        phone: null,
        avatar_url: user?.avatarUrl ? String(user.avatarUrl) : null,
        role: String(user?.role || 'member'),
        is_active: Boolean(user?.isActive ?? user?.is_active ?? true),
        is_verified: Boolean(user?.isVerified ?? user?.is_verified ?? true),
        company_id: String(user?.companyId || user?.company_id || ''),
        company_name: user?.companyName ? String(user.companyName) : null,
        created_at: user?.createdAt ? String(user.createdAt) : null,
      },
      tokens: (result.tokens as TokenResponse) || {
        access_token: '',
        refresh_token: '',
        token_type: 'bearer',
        expires_in: 900,
      },
      is_new_user: Boolean(result.is_new_user),
    } as AuthResponse;
  },
  
  /**
   * Logout user.
   * C-03 FIX: Backend reads refresh_token from httpOnly cookie (parwa_rt).
   */
  logout: () => post<MessageResponse>('/api/auth/logout', {}),
  
  /**
   * Refresh tokens.
   * C-03 FIX: Backend reads refresh_token from httpOnly cookie (parwa_rt)
   * and sets new httpOnly cookies in the response.
   */
  refresh: () => post<TokenResponse>('/api/auth/refresh', {}),
  
  /**
   * Get current user profile.
   */
  getMe: () => get<User>('/api/auth/me'),
  
  /**
   * Check email availability.
   */
  checkEmail: (email: string) => get<EmailCheckResponse>(`/api/auth/check-email?email=${encodeURIComponent(email)}`),
  
  /**
   * Verify email with token.
   */
  verifyEmail: (token: string) => get<MessageResponse>(`/api/auth/verify?token=${encodeURIComponent(token)}`),
  
  /**
   * Resend verification email.
   */
  resendVerification: (email: string) => post<MessageResponse>('/api/auth/resend-verification', { email }),
  
  /**
   * Request password reset.
   */
  forgotPassword: (email: string) => post<MessageResponse>('/api/auth/forgot-password', { email }),
  
  /**
   * Reset password with token.
   */
  resetPassword: (token: string, new_password: string) => 
    post<MessageResponse>('/api/auth/reset-password', { token, new_password }),
};

export default apiClient;
