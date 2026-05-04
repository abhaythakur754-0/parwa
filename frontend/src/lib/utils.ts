import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge class names with Tailwind CSS classes.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Security Utilities (GAP-001 Fix) ─────────────────────────────────────

/**
 * XSS Prevention: Sanitize user input by removing dangerous HTML/JS content.
 * 
 * @param input - Raw user input string
 * @returns Sanitized string safe for display
 */
export function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') return '';
  
  let sanitized = input;
  
  // Remove HTML tags
  sanitized = sanitized.replace(/<[^>]*>/g, '');
  
  // Remove javascript: protocol (case-insensitive)
  sanitized = sanitized.replace(/javascript:/gi, '');
  
  // Remove event handlers (onclick, onerror, onload, etc.)
  sanitized = sanitized.replace(/on\w+\s*=/gi, '');
  
  // Remove data: URLs (can contain malicious content)
  sanitized = sanitized.replace(/data:/gi, '');
  
  // Remove vbscript: protocol
  sanitized = sanitized.replace(/vbscript:/gi, '');
  
  // Trim whitespace
  return sanitized.trim();
}

/**
 * Validate and sanitize URL to prevent XSS via URL schemes.
 * 
 * @param url - URL string to validate
 * @returns Sanitized URL or empty string if invalid
 */
export function sanitizeUrl(url: string): string {
  if (!url || typeof url !== 'string') return '';
  
  const trimmed = url.trim().toLowerCase();
  
  // Only allow http:// and https:// protocols
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return url.trim();
  }
  
  // Block dangerous protocols
  const dangerousProtocols = ['javascript:', 'data:', 'vbscript:', 'file:'];
  if (dangerousProtocols.some(p => trimmed.startsWith(p))) {
    return '';
  }
  
  // If no protocol, assume https
  if (trimmed && !trimmed.startsWith('http')) {
    return `https://${url.trim()}`;
  }
  
  return url.trim();
}

/**
 * Validate email format and check for XSS attempts.
 * 
 * @param email - Email string to validate
 * @returns Object with isValid flag and sanitized email
 */
export function validateEmail(email: string): { isValid: boolean; sanitized: string } {
  if (!email || typeof email !== 'string') {
    return { isValid: false, sanitized: '' };
  }
  
  // Check for XSS attempts
  if (email.includes('<') || email.includes('>') || email.includes('javascript:')) {
    return { isValid: false, sanitized: '' };
  }
  
  // Standard email regex
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const sanitized = email.trim().toLowerCase();
  
  return {
    isValid: emailRegex.test(sanitized),
    sanitized,
  };
}

// ── Form State Persistence (GAP-007 Fix) ─────────────────────────────────

const FORM_STORAGE_KEY = 'parwa_onboarding_form';

/**
 * Save form data to localStorage for persistence.
 */
export function saveFormDataToStorage(data: Record<string, unknown>): void {
  if (typeof window === 'undefined') return;
  
  try {
    localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(data));
  } catch (error) {
    console.warn('Failed to save form data to localStorage:', error);
  }
}

/**
 * Load form data from localStorage.
 */
export function loadFormDataFromStorage<T = Record<string, unknown>>(): T | null {
  if (typeof window === 'undefined') return null;
  
  try {
    const stored = localStorage.getItem(FORM_STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored) as T;
    }
  } catch (error) {
    console.warn('Failed to load form data from localStorage:', error);
  }
  
  return null;
}

/**
 * Clear form data from localStorage after successful submission.
 */
export function clearFormDataFromStorage(): void {
  if (typeof window === 'undefined') return;
  
  try {
    localStorage.removeItem(FORM_STORAGE_KEY);
  } catch (error) {
    console.warn('Failed to clear form data from localStorage:', error);
  }
}
