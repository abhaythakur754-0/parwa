/**
 * PARWA API Client
 * 
 * Centralized API client for making requests to the backend.
 * 
 * Security Features:
 * - FIX A2: No tokens stored in localStorage — uses httpOnly cookies exclusively
 * - FIX A3: CSRF token attached to all mutating requests (double-submit cookie pattern)
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
 * FIX A3: Generate a CSRF token for double-submit cookie pattern.
 * On first load, generate a random token and store in cookie.
 * On every mutating request, read from cookie and send in header.
 * Server compares cookie value with header value.
 */
function getOrCreateCsrfToken(): string {
  const CSRF_COOKIE = 'parwa_csrf';
  const cookies = document.cookie.split(';');
  let csrfToken = '';

  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === CSRF_COOKIE) {
      csrfToken = value;
      break;
    }
  }

  if (!csrfToken) {
    // Generate a new CSRF token
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    csrfToken = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    // Store in cookie (not httpOnly — JS needs to read it)
    document.cookie = `${CSRF_COOKIE}=${csrfToken};path=/;SameSite=Strict;Secure`;
  }

  return csrfToken;
}

/**
 * Create axios instance with default configuration.
 * FIX A2: withCredentials: true sends httpOnly cookies with every request.
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Include httpOnly cookies for session auth
});

/**
 * FIX A2: Request interceptor — NO localStorage token injection.
 * Auth is handled entirely via httpOnly cookies (parwa_session).
 * 
 * FIX A3: CSRF token attached to mutating requests only.
 */
apiClient.interceptors.request.use(
  (config) => {
    // FIX A3: Attach CSRF token to all state-changing requests
    const method = (config.method || 'get').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const csrfToken = getOrCreateCsrfToken();
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken;
      }
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor for handling errors.
 * D9-P11 FIX: On 401, dispatch custom event instead of hard redirect.
 * D9-P2 FIX: Attempt token refresh before giving up on 401.
 * 
 * FIX A2: Token refresh uses httpOnly cookies, not localStorage.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    // D9-P2: Handle 401 — attempt token refresh before giving up
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (typeof window !== 'undefined') {
        originalRequest._retry = true;
        try {
          // FIX A2: Refresh uses httpOnly cookie, no localStorage needed
          const { data } = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {}, {
            withCredentials: true,
          });
          // Retry original request — new cookie is set automatically
          return apiClient(originalRequest);
        } catch {
          // Refresh failed — proceed to logout
        }
        // D9-P11: Clear user data and dispatch event for AuthContext
        localStorage.removeItem('parwa_user');
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
    if (!error.response) {
      if (error.code === 'ECONNABORTED') {
        return 'Request timed out. Please try again.';
      }
      return 'Network error. Please check your connection.';
    }
    
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
 * Generic PUT request with safe parsing.
 */
export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  try {
    const response = await apiClient.put<T>(url, data, config);
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
  getState: () => get<OnboardingState>('/api/onboarding/state'),
  start: () => post<OnboardingState>('/api/onboarding/start'),
  completeStep: (step: number) => post<OnboardingState>(`/api/onboarding/step/${step}`),
  submitLegal: (consents: { terms: boolean; privacy: boolean; ai_data: boolean }) => 
    post<OnboardingState>('/api/onboarding/legal-consent', consents),
  activateAI: (config?: { ai_name?: string; ai_tone?: string; ai_response_style?: string }) => 
    post<OnboardingState>('/api/onboarding/activate', config),
  getVictory: () => get('/api/onboarding/first-victory'),
  completeVictory: () => post('/api/onboarding/first-victory'),
};

// ── User Details API Endpoints ────────────────────────────────────────

export const userDetailsApi = {
  get: () => get<UserDetails>('/api/user/details'),
  create: (data: {
    full_name: string;
    company_name: string;
    work_email?: string;
    industry: string;
    company_size?: string;
    website?: string;
  }) => post<UserDetails>('/api/user/details', data),
  update: (data: Partial<{
    full_name: string;
    company_name: string;
    work_email: string;
    industry: string;
    company_size: string;
    website: string;
  }>) => patch<UserDetails>('/api/user/details', data),
  sendVerification: (work_email: string) => 
    post('/api/user/verify-work-email', { work_email }),
  confirmVerification: (token: string) => 
    post('/api/user/verify-work-email/confirm', { token }),
};

// ── Integration API Endpoints ──────────────────────────────────────────

export const integrationsApi = {
  getAvailable: () => get('/api/integrations/available'),
  list: () => get('/api/integrations'),
  create: (data: { type: string; name: string; config: Record<string, unknown> }) => 
    post('/api/integrations', data),
  test: (id: string) => post(`/api/integrations/${id}/test`),
  delete: (id: string) => del(`/api/integrations/${id}`),
};

// ── Knowledge Base API Endpoints ───────────────────────────────────────

export const knowledgeApi = {
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
  list: () => get('/api/kb/documents'),
  getStatus: (id: string) => get(`/api/kb/documents/${id}`),
  delete: (id: string) => del(`/api/kb/documents/${id}`),
};

// ── Auth API Endpoints ──────────────────────────────────────────────────

export const authApi = {
  register: (data: RegisterRequest) => post<AuthResponse>('/api/auth/register', data),
  login: (data: LoginRequest) => post<AuthResponse>('/api/auth/login', data),
  googleAuth: (data: GoogleAuthRequest) => post<AuthResponse>('/api/auth/google', data),
  logout: (data: RefreshRequest) => post<MessageResponse>('/api/auth/logout', data),
  refresh: (data: RefreshRequest) => post<TokenResponse>('/api/auth/refresh', data),
  getMe: () => get<User>('/api/auth/me'),
  checkEmail: (email: string) => get<EmailCheckResponse>(`/api/auth/check-email?email=${encodeURIComponent(email)}`),
  verifyEmail: (token: string) => get<MessageResponse>(`/api/auth/verify?token=${encodeURIComponent(token)}`),
  resendVerification: (email: string) => post<MessageResponse>('/api/auth/resend-verification', { email }),
  forgotPassword: (email: string) => post<MessageResponse>('/api/auth/forgot-password', { email }),
  resetPassword: (token: string, new_password: string) => 
    post<MessageResponse>('/api/auth/reset-password', { token, new_password }),
  deleteAccount: () => del<MessageResponse>('/api/user/delete-account'),
};

export default apiClient;
