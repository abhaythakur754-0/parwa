'use client';

import React, { useEffect, useRef, useCallback } from 'react';
import { trapFocus, focusFirstFocusable } from '@/lib/a11y';

interface FocusTrapProps {
  children: React.ReactNode;
  active?: boolean;
  initialFocus?: boolean;
  restoreFocus?: boolean;
  onEscape?: () => void;
  className?: string;
}

/**
 * FocusTrap component for trapping focus within modals, dialogs, and other overlays.
 * Implements WCAG 2.1 focus management requirements.
 */
export const FocusTrap: React.FC<FocusTrapProps> = ({
  children,
  active = true,
  initialFocus = true,
  restoreFocus = true,
  onEscape,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Store the previously focused element
  useEffect(() => {
    if (active) {
      previousActiveElement.current = document.activeElement as HTMLElement;
    }
  }, [active]);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!active || !containerRef.current) return;

      // Handle Tab key for focus trapping
      trapFocus(containerRef.current, event);

      // Handle Escape key
      if (event.key === 'Escape' && onEscape) {
        event.preventDefault();
        onEscape();
      }
    },
    [active, onEscape]
  );

  // Add/remove event listeners
  useEffect(() => {
    if (active) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [active, handleKeyDown]);

  // Focus first element when trap becomes active
  useEffect(() => {
    if (active && initialFocus && containerRef.current) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => {
        focusFirstFocusable(containerRef.current!);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [active, initialFocus]);

  // Restore focus when trap becomes inactive
  useEffect(() => {
    if (!active && restoreFocus && previousActiveElement.current) {
      previousActiveElement.current.focus();
    }
  }, [active, restoreFocus]);

  if (!active) {
    return <>{children}</>;
  }

  return (
    <div
      ref={containerRef}
      className={className}
      role="presentation"
      aria-modal={active ? 'true' : undefined}
    >
      {children}
    </div>
  );
};

export default FocusTrap;
