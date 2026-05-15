/**
 * PARWA useKeyboardShortcut Hook
 *
 * Registers global keyboard shortcuts with proper modifier key handling.
 * Supports Ctrl/Cmd + key combos, single keys, and custom predicates.
 * Automatically cleans up listeners on unmount.
 *
 * Usage:
 *   useKeyboardShortcut({ key: 'k', meta: true }, () => openCommandPalette());
 *   useKeyboardShortcut({ key: 'Escape' }, () => closeModal());
 */

'use client';

import { useEffect, useRef, useCallback } from 'react';

export interface KeyboardShortcutDef {
  /** The key to listen for (e.g. 'k', 'Escape', 'ArrowDown') */
  key: string;
  /** Whether Ctrl is required (default: false) */
  ctrl?: boolean;
  /** Whether Meta/Command is required (default: false) */
  meta?: boolean;
  /** Whether Shift is required (default: false) */
  shift?: boolean;
  /** Whether Alt is required (default: false) */
  alt?: boolean;
  /** Whether the shortcut is currently active (default: true) */
  enabled?: boolean;
  /** Whether to prevent default browser behavior (default: true) */
  preventDefault?: boolean;
}

export function useKeyboardShortcut(
  shortcut: KeyboardShortcutDef,
  handler: (e: KeyboardEvent) => void
) {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  const {
    key,
    ctrl = false,
    meta = false,
    shift = false,
    alt = false,
    enabled = true,
    preventDefault = true,
  } = shortcut;

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled) return;

      // Don't trigger when typing in input/textarea (unless it's Escape)
      const target = e.target as HTMLElement;
      const isInputField =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable;

      if (isInputField && key !== 'Escape') return;

      // Check key match (case-insensitive)
      if (e.key.toLowerCase() !== key.toLowerCase() && e.key !== key) return;

      // Check modifier keys
      if (ctrl && !e.ctrlKey && !e.metaKey) return;
      if (meta && !e.metaKey && !e.ctrlKey) return; // Cross-platform: meta or ctrl
      if (shift && !e.shiftKey) return;
      if (alt && !e.altKey) return;

      // If no modifiers required, make sure none are held (except for keys like Escape)
      if (!ctrl && !meta && !shift && !alt && key !== 'Escape') {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      }

      if (preventDefault) {
        e.preventDefault();
      }

      handlerRef.current(e);
    },
    [key, ctrl, meta, shift, alt, enabled, preventDefault]
  );

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown, enabled]);
}

/**
 * Register multiple keyboard shortcuts at once.
 */
export function useKeyboardShortcuts(
  shortcuts: Array<{ shortcut: KeyboardShortcutDef; handler: (e: KeyboardEvent) => void }>
) {
  for (const { shortcut, handler } of shortcuts) {
    useKeyboardShortcut(shortcut, handler);
  }
}
