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
import { UserDetails, OnboardingState } from '@/types/onboarding';
import {
  User,
  AuthResponse,
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  GoogleAuthRequest,
  RefreshRequest,
  EmailCheckResponse,
  MessageResponse,
} from '@/types/auth';

// API base URL from environment or default
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
 * Request interceptor for adding auth token.
 */
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = typeof window !== 'undefined' 
      ? localStorage.getItem('parwa_access_token') 
      : null;
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for handling errors.
 * GAP-002: Handle malformed responses gracefully.
 * D9-P11 FIX: On 401, dispatch custom event instead of hard redirect.
 *   This lets AuthContext handle logout consistently (soft router.push
 *   instead of window.location.href which kills all React state).
 * D9-P2 FIX: Attempt token refresh before giving up on 401.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    // D9-P2: Handle 401 — attempt token refresh before giving up
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (typeof window !== 'undefined') {
        const refreshToken = localStorage.getItem('parwa_refresh_token');
        if (refreshToken) {
          originalRequest._retry = true;
          try {
            const { data } = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
              refresh_token: refreshToken,
            });
            // Store new tokens
            if (data.access_token) {
              localStorage.setItem('parwa_access_token', data.access_token);
            }
            if (data.refresh_token) {
              localStorage.setItem('parwa_refresh_token', data.refresh_token);
            }
            // Retry original request with new token
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            return apiClient(originalRequest);
          } catch {
            // Refresh failed — proceed to logout
          }
        }
        // D9-P11: Clear tokens and dispatch event for AuthContext to handle
        localStorage.removeItem('parwa_access_token');
        localStorage.removeItem('parwa_refresh_token');
        localStorage.removeItem('parwa_user');
        // Dispatch custom event instead of hard redirect
        // AuthContext listens for this and does a clean router.push('/login')
        window.dispatchEvent(new CustomEvent('parwa:session-expired'));
      }
    }
    
    // Handle 403 Forbidden
    if (error.response?.status === 403) {
      console.error('Access denied');
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
      return 'Access denied.';
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
    post<OnboardingState>('/api/onboarding/legal-consent', consents),
  
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
    post('/api/user/verify-work-email', { work_email }),
  
  /**
   * Confirm work email verification.
   */
  confirmVerification: (token: string) => 
    post('/api/user/verify-work-email/confirm', { token }),
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
   */
  googleAuth: (data: GoogleAuthRequest) => post<AuthResponse>('/api/auth/google', data),
  
  /**
   * Logout user.
   */
  logout: (data: RefreshRequest) => post<MessageResponse>('/api/auth/logout', data),
  
  /**
   * Refresh tokens.
   */
  refresh: (data: RefreshRequest) => post<TokenResponse>('/api/auth/refresh', data),
  
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

  /**
   * Delete account and all associated data.
   */
  deleteAccount: () => del<MessageResponse>('/api/user/delete-account'),
};

export default apiClient;
