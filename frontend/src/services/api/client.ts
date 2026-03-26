/**
 * PARWA API Client
 *
 * Base API client for making HTTP requests to the PARWA backend.
 * Handles authentication token injection, error handling, and request/response interceptors.
 */

/**
 * API Error class for structured error handling.
 */
export class APIError extends Error {
  public status: number;
  public statusText: string;
  public data: unknown;

  constructor(status: number, statusText: string, message: string, data?: unknown) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.statusText = statusText;
    this.data = data;
  }
}

/**
 * Request configuration options.
 */
export interface RequestConfig {
  /** Request headers */
  headers?: Record<string, string>;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Include auth token in request */
  includeAuth?: boolean;
  /** Custom signal for aborting request */
  signal?: AbortSignal;
}

/**
 * API Response type.
 */
export interface APIResponse<T = unknown> {
  /** Response data */
  data: T;
  /** HTTP status code */
  status: number;
  /** Response headers */
  headers: Headers;
}

/**
 * Token manager for handling auth tokens.
 */
class TokenManager {
  private token: string | null = null;
  private readonly TOKEN_KEY = "parwa_auth_token";

  /**
   * Get the current auth token.
   */
  getToken(): string | null {
    if (typeof window === "undefined") {
      return this.token;
    }
    return this.token ?? sessionStorage.getItem(this.TOKEN_KEY);
  }

  /**
   * Set the auth token.
   */
  setToken(token: string | null): void {
    this.token = token;
    if (typeof window !== "undefined") {
      if (token) {
        sessionStorage.setItem(this.TOKEN_KEY, token);
      } else {
        sessionStorage.removeItem(this.TOKEN_KEY);
      }
    }
  }

  /**
   * Clear the auth token.
   */
  clearToken(): void {
    this.setToken(null);
  }
}

/**
 * API Client class.
 */
export class APIClient {
  private baseURL: string;
  private tokenManager: TokenManager;
  private defaultTimeout: number;

  constructor(baseURL?: string) {
    this.baseURL = baseURL ?? process.env.NEXT_PUBLIC_API_URL ?? "/api";
    this.tokenManager = new TokenManager();
    this.defaultTimeout = 30000; // 30 seconds
  }

  /**
   * Set the auth token.
   */
  setAuthToken(token: string | null): void {
    this.tokenManager.setToken(token);
  }

  /**
   * Get the current auth token.
   */
  getAuthToken(): string | null {
    return this.tokenManager.getToken();
  }

  /**
   * Clear the auth token.
   */
  clearAuthToken(): void {
    this.tokenManager.clearToken();
  }

  /**
   * Build full URL from path.
   */
  private buildURL(path: string, params?: Record<string, string>): string {
    const url = new URL(path, this.baseURL);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }

    return url.toString();
  }

  /**
   * Build headers for request.
   */
  private buildHeaders(config?: RequestConfig): HeadersInit {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...config?.headers,
    };

    // Add auth token if available and not explicitly excluded
    if (config?.includeAuth !== false) {
      const token = this.tokenManager.getToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  /**
   * Handle API response.
   */
  private async handleResponse<T>(
    response: globalThis.Response
  ): Promise<APIResponse<T>> {
    let data: unknown;

    // Try to parse JSON response
    try {
      const contentType = response.headers.get("content-type");
      if (contentType?.includes("application/json")) {
        data = await response.json();
      } else {
        data = await response.text();
      }
    } catch {
      data = null;
    }

    // Handle error responses
    if (!response.ok) {
      const message =
        typeof data === "object" && data !== null && "message" in data
          ? String((data as { message?: string }).message)
          : response.statusText;

      throw new APIError(response.status, response.statusText, message, data);
    }

    return {
      data: data as T,
      status: response.status,
      headers: response.headers,
    };
  }

  /**
   * Make a request with timeout.
   */
  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeout: number,
    signal?: AbortSignal
  ): Promise<globalThis.Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    // Combine external signal with timeout signal
    const combinedSignal = signal
      ? AbortSignal.any?.([signal, controller.signal]) ?? controller.signal
      : controller.signal;

    try {
      const response = await fetch(url, {
        ...options,
        signal: combinedSignal,
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Make a GET request.
   */
  async get<T = unknown>(
    path: string,
    params?: Record<string, string>,
    config?: RequestConfig
  ): Promise<APIResponse<T>> {
    const url = this.buildURL(path, params);
    const headers = this.buildHeaders(config);

    const response = await this.fetchWithTimeout(
      url,
      {
        method: "GET",
        headers,
      },
      config?.timeout ?? this.defaultTimeout,
      config?.signal
    );

    return this.handleResponse<T>(response);
  }

  /**
   * Make a POST request.
   */
  async post<T = unknown>(
    path: string,
    body?: unknown,
    config?: RequestConfig
  ): Promise<APIResponse<T>> {
    const url = this.buildURL(path);
    const headers = this.buildHeaders(config);

    const response = await this.fetchWithTimeout(
      url,
      {
        method: "POST",
        headers,
        body: body ? JSON.stringify(body) : undefined,
      },
      config?.timeout ?? this.defaultTimeout,
      config?.signal
    );

    return this.handleResponse<T>(response);
  }

  /**
   * Make a PUT request.
   */
  async put<T = unknown>(
    path: string,
    body?: unknown,
    config?: RequestConfig
  ): Promise<APIResponse<T>> {
    const url = this.buildURL(path);
    const headers = this.buildHeaders(config);

    const response = await this.fetchWithTimeout(
      url,
      {
        method: "PUT",
        headers,
        body: body ? JSON.stringify(body) : undefined,
      },
      config?.timeout ?? this.defaultTimeout,
      config?.signal
    );

    return this.handleResponse<T>(response);
  }

  /**
   * Make a PATCH request.
   */
  async patch<T = unknown>(
    path: string,
    body?: unknown,
    config?: RequestConfig
  ): Promise<APIResponse<T>> {
    const url = this.buildURL(path);
    const headers = this.buildHeaders(config);

    const response = await this.fetchWithTimeout(
      url,
      {
        method: "PATCH",
        headers,
        body: body ? JSON.stringify(body) : undefined,
      },
      config?.timeout ?? this.defaultTimeout,
      config?.signal
    );

    return this.handleResponse<T>(response);
  }

  /**
   * Make a DELETE request.
   */
  async delete<T = unknown>(
    path: string,
    config?: RequestConfig
  ): Promise<APIResponse<T>> {
    const url = this.buildURL(path);
    const headers = this.buildHeaders(config);

    const response = await this.fetchWithTimeout(
      url,
      {
        method: "DELETE",
        headers,
      },
      config?.timeout ?? this.defaultTimeout,
      config?.signal
    );

    return this.handleResponse<T>(response);
  }
}

// Create default API client instance
export const apiClient = new APIClient();

// Export factory function for custom clients
export function createAPIClient(baseURL: string): APIClient {
  return new APIClient(baseURL);
}

export default apiClient;
