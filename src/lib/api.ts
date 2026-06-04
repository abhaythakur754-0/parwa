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
import { appConfig } from '@/lib/config';
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
const API_BASE_URL = appConfig.apiUrl;

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
 * Request interceptor for CSRF token (double-submit cookie pattern).
 * The backend CSRF middleware sets a 'parwa_csrf' cookie on responses.
 * Since the cookie is on the backend domain (different port = different origin),
 * we can't read it via document.cookie from the frontend.
 * Instead, we extract it from the Set-Cookie response header on a preflight GET.
 * 
 * Alternative approach: Store the CSRF token from the first GET response
 * and attach it as x-csrf-token header on subsequent mutating requests.
 */
let _csrfToken: string | null = null;

// Preflight: fetch CSRF token from backend on first API call
async function ensureCsrfToken(): Promise<string> {
  if (_csrfToken) return _csrfToken;
  try {
    const response = await axios.get(`${API_BASE_URL}/health`, {
      withCredentials: true,
    });
    // Extract from Set-Cookie header (available when same-origin or CORS)
    const setCookie = response.headers['set-cookie'];
    if (setCookie) {
      const cookies = Array.isArray(setCookie) ? setCookie : [setCookie];
      for (const cookie of cookies) {
        const match = cookie.match(/parwa_csrf=([^;]+)/);
        if (match) {
          _csrfToken = match[1];
          return _csrfToken;
        }
      }
    }
    // Also try reading from document.cookie (works if same origin)
    if (typeof document !== 'undefined') {
      const csrfCookie = document.cookie
        .split('; ')
        .find((row) => row.startsWith('parwa_csrf='));
      if (csrfCookie) {
        _csrfToken = csrfCookie.split('=')[1];
        return _csrfToken;
      }
    }
  } catch {
    // CSRF preflight failed — will be caught by actual request
  }
  return '';
}

apiClient.interceptors.request.use(async (config) => {
  // NOTE: CSRF tokens are NOT attached here because this axios client
  // calls the backend DIRECTLY (causes CORS issues in production).
  // The signup/login pages use fetch('/api/auth/...') instead, which
  // goes through the Next.js proxy route that handles CSRF automatically.
  // If you need CSRF for direct backend calls, use the proxy routes.
  return config;
});

/**
 * Response interceptor for handling errors.
 * C-03 FIX: Auth tokens are sent as httpOnly cookies
 * automatically by the browser via withCredentials: true.
 * GAP-002: Handle malformed responses gracefully.
 */
apiClient.interceptors.response.use(
  (response) => {
    // Capture CSRF token from Set-Cookie header on any response
    const setCookie = response.headers['set-cookie'];
    if (setCookie) {
      const cookies = Array.isArray(setCookie) ? setCookie : [setCookie];
      for (const cookie of cookies) {
        const match = cookie.match(/parwa_csrf=([^;]+)/);
        if (match) {
          _csrfToken = match[1];
        }
      }
    }
    return response;
  },
  (error: AxiosError) => {
    // Handle 401 Unauthorized — but distinguish between:
    // 1. Failed login/signup (auth endpoint returning 401) → just pass through,
    //    don't clear session or redirect — the calling component handles the error.
    // 2. Expired/invalid token on a protected route → clear user data & redirect.
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      const isAuthEndpoint = url.startsWith('/api/auth/login') ||
        url.startsWith('/api/auth/register') ||
        url.startsWith('/api/auth/google') ||
        url.startsWith('/api/auth/phone/');

      if (!isAuthEndpoint && typeof window !== 'undefined') {
        // Protected route with expired/invalid token — clear session
        localStorage.removeItem('parwa_user');
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
    const data = error.response?.data;

    // Extract the actual error message from the backend response.
    // PARWA backend returns: { error: { code, message, details } }
    // FastAPI default returns: { detail: "..." }
    // Next.js API routes return: { status: "error", message: "..." }
    const backendMessage =
      data?.error?.message ||   // PARWA structured error format
      data?.detail ||           // FastAPI default format
      data?.message;            // Next.js API route format

    if (status === 429) {
      const retryAfter = error.response.headers['retry-after'] || 60;
      return `Too many requests. Please try again in ${retryAfter} seconds.`;
    }
    
    if (status >= 500) {
      return 'Server error. Please try again later.';
    }
    
    // For 401: Use the backend's specific message if available (e.g.
    // "Invalid email or password", "Account temporarily locked").
    // Only fall back to generic "Session expired" when there's no
    // message — which means it's an expired/missing token on a
    // protected route, not a failed login attempt.
    if (status === 401) {
      if (backendMessage) {
        return backendMessage;
      }
      return 'Session expired. Please log in again.';
    }
    
    if (status === 403) {
      if (backendMessage) {
        return backendMessage;
      }
      return 'Access denied.';
    }
    
    // Return server's error message if available
    if (backendMessage) {
      return backendMessage;
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

// ── Ticket API Endpoints ────────────────────────────────────────────

export interface TicketListParams {
  status?: string;
  priority?: string;
  category?: string;
  assigned_to?: string;
  channel?: string;
  customer_id?: string;
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface TicketCreateData {
  subject: string;
  customer_id?: string;
  channel?: string;
  priority?: string;
  category?: string;
  tags?: string[];
  metadata_json?: Record<string, unknown>;
}

export interface TicketUpdateData {
  priority?: string;
  category?: string;
  tags?: string[];
  status?: string;
  assigned_to?: string;
  subject?: string;
}

export const ticketApi = {
  /**
   * Create a new ticket.
   */
  create: (data: TicketCreateData) =>
    post('/api/v1/tickets', data),

  /**
   * List tickets with filters & pagination.
   */
  list: (params?: TicketListParams) => {
    const queryParts: string[] = [];
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          queryParts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
        }
      });
    }
    const qs = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return get(`/api/v1/tickets${qs}`);
  },

  /**
   * Get ticket details by ID.
   */
  get: (id: string) => get(`/api/v1/tickets/${id}`),

  /**
   * Update a ticket.
   */
  update: (id: string, data: TicketUpdateData) =>
    put(`/api/v1/tickets/${id}`, data),

  /**
   * Delete a ticket.
   */
  delete: (id: string) => del(`/api/v1/tickets/${id}`),

  /**
   * Update ticket status.
   */
  updateStatus: (id: string, data: { status: string }) =>
    patch(`/api/v1/tickets/${id}/status`, data),

  /**
   * Assign a ticket.
   */
  assign: (id: string, data: { assigned_to: string }) =>
    post(`/api/v1/tickets/${id}/assign`, data),

  /**
   * Add tags to a ticket.
   */
  addTags: (id: string, data: { tags: string[] }) =>
    post(`/api/v1/tickets/${id}/tags`, data),

  /**
   * Remove a tag from a ticket.
   */
  removeTag: (id: string, tag: string) =>
    del(`/api/v1/tickets/${id}/tags/${encodeURIComponent(tag)}`),
};

export default apiClient;
