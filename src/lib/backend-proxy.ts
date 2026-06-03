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
 */

import { NextRequest, NextResponse } from 'next/server';
import { setAuthCookies, clearAuthCookies } from './auth-cookies';

// Backend URL — prefer SERVER_API_URL (server-only), fall back to NEXT_PUBLIC_API_URL
const BACKEND_URL =
  process.env.SERVER_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://parwa-backend.onrender.com';

// Trusted origin for CSRF validation
const PROXY_ORIGIN =
  process.env.NEXT_PUBLIC_SITE_URL ||
  process.env.NEXTAUTH_URL ||
  'https://parwafrontend.vercel.app';

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

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    // Set Origin for CSRF Layer 1 validation
    Origin: PROXY_ORIGIN,
    // CSRF double-submit: cookie + header must match
    'X-CSRF-Token': csrfToken,
    Cookie: `parwa_csrf=${csrfToken}`,
  };

  // Forward Bearer token if requested
  if (options.forwardAuth) {
    const accessToken = getCookieFromRequest(request, 'parwa_at');
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
      // When Bearer is present, CSRF Layer 2 is skipped
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
    const response = await fetch(url, {
      method: options.method,
      headers,
      body: requestBody ? JSON.stringify(requestBody) : undefined,
      signal: AbortSignal.timeout(60000), // 60s timeout for Render wake-up
    });

    const data = await response.json();

    // Handle error responses
    if (!response.ok) {
      const errorMessage = extractErrorMessage(data);
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

    // Check for timeout (Render sleeping)
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      return NextResponse.json(
        {
          status: 'error',
          message:
            'Server is waking up. Please try again in a few seconds.',
        },
        { status: 503 }
      );
    }

    console.error('[ProxyAuth] Error:', message);
    return NextResponse.json(
      { status: 'error', message: 'An internal error occurred.' },
      { status: 500 }
    );
  }
}
