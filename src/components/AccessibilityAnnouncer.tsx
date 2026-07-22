/**
 * PARWA AccessibilityAnnouncer
 *
 * Provides a centralized way to announce messages to screen readers
 * using ARIA live regions. Creates both polite and assertive regions
 * so that dynamic UI changes (toasts, status updates, form validation)
 * are accessible to assistive technology.
 *
 * Usage:
 *   import { announce } from '@/components/AccessibilityAnnouncer';
 *   announce('Form submitted successfully', 'polite');
 *   announce('Error: Required field missing', 'assertive');
 *
 * Place <AccessibilityAnnouncer /> once in the root layout.
 */

'use client';

import React, { useCallback } from 'react';

// ── Module-level announcement queue ────────────────────────────────

type Politeness = 'polite' | 'assertive';

let politeRegion: HTMLElement | null = null;
let assertiveRegion: HTMLElement | null = null;
let politeTimeout: ReturnType<typeof setTimeout> | null = null;
let assertiveTimeout: ReturnType<typeof setTimeout> | null = null;

/**
 * Announce a message to screen readers via ARIA live regions.
 * Polite messages wait for the reader to be idle.
 * Assertive messages interrupt immediately (use sparingly).
 */
export function announce(message: string, politeness: Politeness = 'polite') {
  const region = politeness === 'assertive' ? assertiveRegion : politeRegion;
  const timeoutRef = politeness === 'assertive' ? 'assertiveTimeout' : 'politeTimeout';

  if (!region) {
    // Region not mounted yet — queue for later
    if (typeof window !== 'undefined') {
      console.warn('[AccessibilityAnnouncer] Live region not mounted. Message:', message);
    }
    return;
  }

  // Clear any pending timeout
  if (timeoutRef === 'politeTimeout' && politeTimeout) {
    clearTimeout(politeTimeout);
    politeTimeout = null;
  }
  if (timeoutRef === 'assertiveTimeout' && assertiveTimeout) {
    clearTimeout(assertiveTimeout);
    assertiveTimeout = null;
  }

  // Clear and re-set to ensure the same message can be announced twice
  region.textContent = '';

  // Small delay to ensure the screen reader detects the change
  const timer = setTimeout(() => {
    region.textContent = message;
  }, 100);

  if (timeoutRef === 'politeTimeout') {
    politeTimeout = timer;
  } else {
    assertiveTimeout = timer;
  }
}

// ── React Component ────────────────────────────────────────────────

export function AccessibilityAnnouncer() {
  const politeRef = useCallback((node: HTMLDivElement | null) => {
    politeRegion = node;
  }, []);

  const assertiveRef = useCallback((node: HTMLDivElement | null) => {
    assertiveRegion = node;
  }, []);

  return (
    <>
      {/* Polite live region — announces when reader is idle */}
      <div
        ref={politeRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        data-testid="aria-live-polite"
        className="sr-only"
      />
      {/* Assertive live region — interrupts immediately */}
      <div
        ref={assertiveRef}
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        data-testid="aria-live-assertive"
        className="sr-only"
      />
    </>
  );
}

export default AccessibilityAnnouncer;
