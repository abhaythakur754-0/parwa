/**
 * PARWA Auth Types
 * 
 * Types for authentication including user, tokens, and auth responses.
 * Based on backend/app/schemas/auth.py
 */

// ── User Types ───────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  company_id: string;
  company_name?: string | null;
  onboarding_completed?: boolean;
  created_at: string | null;
}

// ── Token Types ──────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ── Auth Response Types ──────────────────────────────────────────────────

export interface AuthResponse {
  user: User;
  tokens: TokenResponse;
  is_new_user: boolean;
}

// ── Request Types ────────────────────────────────────────────────────────

export interface RegisterRequest {
  email: string;
  password: string;
  confirm_password: string;
  full_name: string;
  company_name: string;
  industry: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface GoogleAuthRequest {
  id_token: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

// ── Email Check Response ────────────────────────────────────────────────

export interface EmailCheckResponse {
  email: string;
  available: boolean;
}

// ── Message Response ────────────────────────────────────────────────────

export interface MessageResponse {
  message: string;
}

// ── Password Strength Types ─────────────────────────────────────────────

export type PasswordStrength = 'weak' | 'fair' | 'strong' | 'very strong';

export interface PasswordStrengthResult {
  strength: PasswordStrength;
  score: number;
  feedback: string[];
}

// ── Auth State Types ────────────────────────────────────────────────────

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitialized: boolean;
}

// ── Auth Context Types ──────────────────────────────────────────────────

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<AuthResponse>;
  register: (data: RegisterRequest) => Promise<AuthResponse>;
  loginWithGoogle: (idToken: string) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  checkEmailAvailability: (email: string) => Promise<boolean>;
  /** Re-read localStorage and update context state (for login via API routes) */
  hydrate: () => void;
}
