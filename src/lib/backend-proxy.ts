/**
 * PARWA — Backend Proxy Utility
 *
 * Handles server-side proxying from Vercel to the Render backend.
 * Takes care of:
 *   - CSRF token generation (double-submit pattern for backend middleware)
 *   - Origin header injection (CSRF Layer 1)
 *   - Request body transformation (frontend → backend field mapping)
 *   - Response body transformation (backend → frontend format)
 *   - Auth cookie setting (parwa_at, parwa_rt, parwa_user)
 *   - Error normalization
 *
 * IMPORTANT: Uses Node.js https.request() instead of fetch() because
 * Node.js fetch() strips "forbidden headers" (Cookie, Origin) per the
 * Fetch spec, which breaks CSRF proxy auth and origin validation.
 * https.request() sends ALL headers without stripping.
 */

import { NextRequest, NextResponse } from 'next/server';
import https from 'https';
import http from 'http';
import { setAuthCookies, clearAuthCookies } from './auth-cookies';

// Backend URL — prefer SERVER_API_URL (server-only), fall back to BACKEND_URL, then NEXT_PUBLIC_API_URL
const BACKEND_URL =
  process.env.SERVER_API_URL ||
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://parwa-backend.onrender.com';

// Trusted origin for CSRF validation
const PROXY_ORIGIN =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXTAUTH_URL ||
  'https://parwafrontend.vercel.app';

// Proxy auth secret — must match backend PROXY_AUTH_SECRET
const PROXY_AUTH_SECRET = process.env.PROXY_AUTH_SECRET || 'parwa_proxy_auth_2026';

// ── CSRF Token Generation ──────────────────────────────────────
// The backend CSRF middleware uses a double-submit cookie pattern:
// It checks that parwa_csrf cookie value matches X-CSRF-Token header value.
// We generate a random token and include it in both places.

function generateCSRFToken(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
}

// ── Request Body Transformation ─────────────────────────────────

/**
 * Transform frontend register body to backend RegisterRequest format.
 * Frontend sends: { email, password, fullName, companyName, industry }
 * Backend expects: { email, password, confirm_password, full_name, company_name, industry }
 */
export function transformRegisterBody(body: Record<string, unknown>): Record<string, unknown> {
  return {
    email: body.email,
    password: body.password,
    confirm_password: body.confirm_password || body.password, // Required by backend
    full_name: body.fullName || body.full_name || null,
    company_name: body.companyName || body.company_name || null,
    industry: body.industry || null,
  };
}

/**
 * Transform frontend login body to backend LoginRequest format.
 * Both use { email, password } — no transformation needed.
 */
export function transformLoginBody(body: Record<string, unknown>): Record<string, unknown> {
  return body;
}

/**
 * Transform frontend Google auth body to backend GoogleAuthRequest format.
 * Both use { id_token } — no transformation needed.
 */
export function transformGoogleBody(body: Record<string, unknown>): Record<string, unknown> {
  return body;
}

// ── Response Body Transformation ────────────────────────────────

/**
 * Transform backend AuthResponse to frontend format.
 *
 * Backend returns:
 *   { user: { id, email, full_name, ... }, tokens: { access_token, refresh_token, ... }, is_new_user }
 *
 * Frontend expects:
 *   { status: "success", user: { id, email, fullName, isVerified }, message, is_new_user }
 */
export function transformAuthResponse(data: Record<string, unknown>): Record<string, unknown> {
  const user = (data.user || {}) as Record<string, unknown>;
  const tokens = (data.tokens || {}) as Record<string, unknown>;

  return {
    status: 'success',
    user: {
      id: user.id,
      email: user.email,
      fullName: user.full_name || user.fullName || null,
      isVerified: user.is_verified ?? user.isVerified ?? false,
      industry: user.industry || null,
      companyName: user.company_name || user.companyName || null,
    },
    is_new_user: data.is_new_user ?? false,
    message: data.message || 'Success',
    // Internal: tokens for cookie setting (not exposed to client)
    _tokens: {
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
    },
  };
}

/**
 * Transform backend UserResponse (for /me) to frontend format.
 */
export function transformMeResponse(data: Record<string, unknown>): Record<string, unknown> {
  return {
    id: data.id,
    email: data.email,
    full_name: data.full_name,
    fullName: data.full_name,
    phone: data.phone,
    avatar_url: data.avatar_url,
    role: data.role,
    is_active: data.is_active,
    isVerified: data.is_verified,
    is_verified: data.is_verified,
    company_id: data.company_id,
    company_name: data.company_name,
    created_at: data.created_at,
  };
}

/**
 * Extract error message from backend error response.
 * Handles multiple formats:
 *   - { error: { code, message } } — PARWA structured errors
 *   - { detail: "string" } — FastAPI errors
 *   - { detail: [{ msg }] } — Pydantic validation errors
 */
function extractErrorMessage(data: Record<string, unknown>): string {
  // PARWA structured error
  if (data.error && typeof data.error === 'object') {
    const err = data.error as Record<string, unknown>;
    if (err.message) return String(err.message);
  }
  // FastAPI detail (string)
  if (typeof data.detail === 'string') return data.detail;
  // FastAPI detail (array of validation errors)
  if (Array.isArray(data.detail)) {
    const messages = data.detail
      .map((d: Record<string, unknown>) => {
        const msg = d.msg || String(d);
        const field = Array.isArray(d.loc) ? d.loc.join('.') : '';
        return field ? `${field}: ${msg}` : String(msg);
      })
      .join('; ');
    return messages || 'Validation error';
  }
  // Fallback
  if (data.message) return String(data.message);
  return 'An unexpected error occurred.';
}

// ── Cookie Extraction from Request ──────────────────────────────

function getCookieFromRequest(request: NextRequest, name: string): string | null {
  const cookieHeader = request.headers.get('cookie');
  if (!cookieHeader) return null;

  for (const part of cookieHeader.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(`${name}=`)) {
      return trimmed.slice(name.length + 1);
    }
  }
  return null;
}

// ── Low-level HTTP request using Node.js https/http ─────────────
// Uses native Node.js http/https modules instead of fetch() because
// fetch() strips "forbidden headers" (Cookie, Origin) per the Fetch spec.
// This breaks our CSRF proxy auth and origin validation.

interface RawHttpResponse {
  status: number;
  headers: Record<string, string>;
  body: string;
}

function rawHttpRequest(
  url: string,
  method: string,
  headers: Record<string, string>,
  body?: string,
  timeoutMs: number = 60000,
): Promise<RawHttpResponse> {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const isHttps = parsedUrl.protocol === 'https:';
    const lib = isHttps ? https : http;

    const options: https.RequestOptions = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || (isHttps ? 443 : 80),
      path: parsedUrl.pathname + parsedUrl.search,
      method,
      headers,
      timeout: timeoutMs,
    };

    const req = lib.request(options, (res) => {
      let data = '';
      res.on('data', (chunk: Buffer | string) => {
        data += chunk.toString();
      });
      res.on('end', () => {
        const respHeaders: Record<string, string> = {};
        for (let i = 0; i < (res.rawHeaders?.length || 0); i += 2) {
          const key = res.rawHeaders[i];
          const val = res.rawHeaders[i + 1];
          if (key && val) {
            respHeaders[key.toLowerCase()] = val;
          }
        }
        resolve({
          status: res.statusCode || 500,
          headers: respHeaders,
          body: data,
        });
      });
    });

    req.on('error', (err: Error) => {
      reject(err);
    });

    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`Request timeout after ${timeoutMs}ms`));
    });

    if (body) {
      req.write(body);
    }
    req.end();
  });
}

// ── Main Proxy Function ────────────────────────────────────────

export interface ProxyAuthOptions {
  /** Backend path, e.g. "/api/auth/register" */
  backendPath: string;
  /** HTTP method */
  method: string;
  /** Request body (will be transformed) */
  body?: Record<string, unknown>;
  /** Body transformer function */
  transformBody?: (body: Record<string, unknown>) => Record<string, unknown>;
  /** Response transformer function */
  transformResponse?: (data: Record<string, unknown>) => Record<string, unknown>;
  /** Whether to set auth cookies on success */
  setCookies?: boolean;
  /** Whether to clear auth cookies (for logout) */
  clearCookies?: boolean;
  /** Whether to forward the Bearer token from the request */
  forwardAuth?: boolean;
  /** Whether this is a refresh token request (send refresh token in body) */
  isRefresh?: boolean;
}

export async function proxyAuthRequest(
  request: NextRequest,
  options: ProxyAuthOptions
): Promise<NextResponse> {
  const url = `${BACKEND_URL}${options.backendPath}`;

  // Generate CSRF token for double-submit pattern
  const csrfToken = generateCSRFToken();

  // Build headers — using Node.js https.request() which does NOT strip
  // "forbidden headers" like Cookie and Origin (unlike fetch()).
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Origin': PROXY_ORIGIN,
    'x-proxy-origin': PROXY_ORIGIN,
    'x-csrf-token': csrfToken,
    'x-csrf-cookie': csrfToken,
    'Cookie': `parwa_csrf=${csrfToken}`,
    // Trusted proxy auth — backend skips CSRF checks when this matches
    'x-proxy-auth': PROXY_AUTH_SECRET,
  };

  // Debug: log proxy details
  console.log('[ProxyAuth]', options.method, options.backendPath, 'origin=', PROXY_ORIGIN, 'proxy_auth_len=', PROXY_AUTH_SECRET.length);

  // Forward Bearer token if requested
  if (options.forwardAuth) {
    const accessToken = getCookieFromRequest(request, 'parwa_at');
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  // Build request body
  let requestBody: Record<string, unknown> | undefined;
  if (options.body) {
    requestBody = options.transformBody
      ? options.transformBody(options.body)
      : options.body;
  }

  // For refresh requests, include the refresh token from cookie
  if (options.isRefresh) {
    const refreshToken = getCookieFromRequest(request, 'parwa_rt');
    requestBody = {
      ...(requestBody || {}),
      refresh_token: refreshToken || '',
    };
  }

  // For logout, include the refresh token from cookie
  if (options.clearCookies) {
    const refreshToken = getCookieFromRequest(request, 'parwa_rt');
    requestBody = {
      ...(requestBody || {}),
      refresh_token: refreshToken || '',
    };
    // Also forward Bearer token for logout (backend requires auth)
    const accessToken = getCookieFromRequest(request, 'parwa_at');
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  try {
    // Use raw HTTP request instead of fetch() to preserve ALL headers
    // (fetch() strips Cookie, Origin, and other "forbidden headers")
    const response = await rawHttpRequest(
      url,
      options.method,
      headers,
      requestBody ? JSON.stringify(requestBody) : undefined,
      60000, // 60s timeout for Render wake-up
    );

    // Parse JSON response
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(response.body);
    } catch {
      console.error('[ProxyAuth] Invalid JSON response:', response.body?.slice(0, 200));
      return NextResponse.json(
        { status: 'error', message: 'Invalid response from server.' },
        { status: 502 }
      );
    }

    // Handle error responses
    if (response.status < 200 || response.status >= 300) {
      const errorMessage = extractErrorMessage(data);
      console.error('[ProxyAuth] Backend error:', response.status, errorMessage);
      return NextResponse.json(
        { status: 'error', message: errorMessage },
        { status: response.status }
      );
    }

    // Transform successful response
    const transformed = options.transformResponse
      ? options.transformResponse(data)
      : data;

    // Build NextResponse
    const nextResponse = NextResponse.json(transformed);

    // Set auth cookies if requested
    if (options.setCookies && transformed._tokens) {
      const tokens = transformed._tokens as {
        access_token: string;
        refresh_token: string;
      };
      const userData = (transformed.user || {}) as Record<string, unknown>;

      // Remove internal _tokens field before sending to client
      delete (transformed as Record<string, unknown>)._tokens;
      // Re-create response without _tokens
      const cleanResponse = NextResponse.json(transformed);

      setAuthCookies(
        cleanResponse,
        tokens.access_token,
        tokens.refresh_token,
        userData
      );
      return cleanResponse;
    }

    // Clear auth cookies if requested (logout)
    if (options.clearCookies) {
      clearAuthCookies(nextResponse);
    }

    return nextResponse;
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : 'Unknown error';

    // Check for timeout (Render sleeping or slow response)
    const isTimeout =
      message.includes('timeout') || message.includes('abort') || message.includes('ETIMEDOUT');
    if (isTimeout) {
      console.error('[ProxyAuth] Timeout error:', message);
      return NextResponse.json(
        {
          status: 'error',
          message:
            'Server is waking up, please try again in a moment.',
        },
        { status: 503 }
      );
    }

    // Check for connection errors (backend unreachable)
    const isConnectionError =
      message.includes('ECONNREFUSED') ||
      message.includes('ENOTFOUND') ||
      message.includes('network') ||
      message.includes('socket hang up');
    if (isConnectionError) {
      console.error('[ProxyAuth] Connection error:', message);
      return NextResponse.json(
        {
          status: 'error',
          message:
            'Unable to connect to the server. Please try again.',
        },
        { status: 502 }
      );
    }

    console.error('[ProxyAuth] Unexpected error:', message, error);
    return NextResponse.json(
      { status: 'error', message: 'Something went wrong. Please try again later.' },
      { status: 500 }
    );
  }
}
