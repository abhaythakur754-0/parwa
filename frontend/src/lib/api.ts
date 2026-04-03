/**
 * PARWA API Client
 * 
 * Centralized API client for making requests to the backend.
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';

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
      ? localStorage.getItem('auth_token') 
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
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle 401 Unauthorized
    if (error.response?.status === 401) {
      // Clear auth token and redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
    }
    
    // Handle 403 Forbidden
    if (error.response?.status === 403) {
      console.error('Access denied');
    }
    
    return Promise.reject(error);
  }
);

/**
 * Generic GET request.
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.get<T>(url, config);
  return response.data;
}

/**
 * Generic POST request.
 */
export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.post<T>(url, data, config);
  return response.data;
}

/**
 * Generic PATCH request.
 */
export async function patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.patch<T>(url, data, config);
  return response.data;
}

/**
 * Generic DELETE request.
 */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.delete<T>(url, config);
  return response.data;
}

// ── Onboarding API Endpoints ───────────────────────────────────────────

export const onboardingApi = {
  /**
   * Get current onboarding state.
   */
  getState: () => get('/api/onboarding/state'),
  
  /**
   * Start onboarding wizard.
   */
  start: () => post('/api/onboarding/start'),
  
  /**
   * Complete a step.
   */
  completeStep: (step: number) => post(`/api/onboarding/step/${step}`),
  
  /**
   * Submit legal consents.
   */
  submitLegal: (consents: { terms: boolean; privacy: boolean; ai_data: boolean }) => 
    post('/api/onboarding/legal', consents),
  
  /**
   * Activate AI assistant.
   */
  activateAI: (config?: { ai_name?: string; ai_tone?: string; ai_response_style?: string }) => 
    post('/api/onboarding/activate', config),
  
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
  get: () => get('/api/user/details'),
  
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
  }) => post('/api/user/details', data),
  
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
  }>) => patch('/api/user/details', data),
  
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
    
    const response = await apiClient.post('/api/knowledge/upload', formData, {
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
  list: () => get('/api/knowledge'),
  
  /**
   * Get document status.
   */
  getStatus: (id: string) => get(`/api/knowledge/${id}/status`),
  
  /**
   * Delete document.
   */
  delete: (id: string) => del(`/api/knowledge/${id}`),
};

export default apiClient;
