/**
 * PARWA useFocusTrap Hook
 *
 * Traps keyboard focus within a container element.
 * Essential for modals, dialogs, and drawers to comply with WCAG 2.1
 * focus management requirements (2.4.3 Focus Order, 2.1.2 No Keyboard Trap).
 *
 * Usage:
 *   const containerRef = useRef<HTMLDivElement>(null);
 *   useFocusTrap(containerRef, { active: isModalOpen });
 *
 *   return <div ref={containerRef}>...modal content...</div>;
 */

'use client';

import { useEffect, useRef, useCallback } from 'react';

interface FocusTrapOptions {
  /** Whether the focus trap is active (default: true) */
  active?: boolean;
  /** Whether to auto-focus the first focusable element on activation (default: true) */
  autoFocus?: boolean;
  /** Restore focus to the previously focused element on deactivation (default: true) */
  restoreFocus?: boolean;
  /** Called when Escape is pressed (default: no-op) */
  onEscape?: () => void;
}

const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
  'details > summary',
].join(', ');

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const elements = Array.from(container.querySelectorAll(FOCUSABLE_SELECTORS));
  return elements.filter((el) => {
    // Filter out elements that are not visible
    if (el.getAttribute('aria-hidden') === 'true') return false;
    if (el.hasAttribute('disabled')) return false;
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }) as HTMLElement[];
}

export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement | null>,
  options: FocusTrapOptions = {}
) {
  const { active = true, autoFocus = true, restoreFocus = true, onEscape } = options;
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Save the previously focused element when trap activates
  useEffect(() => {
    if (active && typeof document !== 'undefined') {
      previouslyFocusedRef.current = document.activeElement as HTMLElement;
    }

    return () => {
      if (active && restoreFocus && previouslyFocusedRef.current) {
        // Restore focus when trap deactivates
        try {
          previouslyFocusedRef.current.focus();
        } catch {
          // Element may have been removed from the DOM
        }
      }
    };
  }, [active, restoreFocus]);

  // Auto-focus first focusable element when trap activates
  useEffect(() => {
    if (!active || !containerRef.current || !autoFocus) return;

    const timer = setTimeout(() => {
      if (!containerRef.current) return;
      const focusable = getFocusableElements(containerRef.current);
      if (focusable.length > 0) {
        focusable[0].focus();
      }
    }, 50); // Small delay to allow DOM to settle

    return () => clearTimeout(timer);
  }, [active, autoFocus, containerRef]);

  // Handle Tab key cycling and Escape
  useEffect(() => {
    if (!active || !containerRef.current) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onEscape?.();
        return;
      }

      if (e.key !== 'Tab') return;

      const container = containerRef.current;
      if (!container) return;

      const focusable = getFocusableElements(container);
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }

      const firstElement = focusable[0];
      const lastElement = focusable[focusable.length - 1];

      if (e.shiftKey) {
        // Shift+Tab: if on first element, wrap to last
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab: if on last element, wrap to first
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    const container = containerRef.current;
    container.addEventListener('keydown', handleKeyDown);

    return () => {
      container.removeEventListener('keydown', handleKeyDown);
    };
  }, [active, containerRef, onEscape]);
}
