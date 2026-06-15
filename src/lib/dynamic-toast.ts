/**
 * Lightweight Toast Notification System
 *
 * Drop-in replacement for react-hot-toast that doesn't use any external
 * ESM module. This completely avoids the TDZ ("Cannot access 'X' before
 * initialization") errors that react-hot-toast causes in the Next.js
 * production build with Turbopack.
 *
 * Usage: Same API as react-hot-toast
 *   import { toast } from '@/lib/dynamic-toast';
 *   toast.success('Done!');
 *   toast.error('Failed');
 *   toast('Loading...', { icon: '🔄' });
 *   toast.dismiss();
 */

import React from 'react';
import { createRoot } from 'react-dom/client';

// ── Types ──────────────────────────────────────────────────────────────

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'error' | 'loading' | 'info' | 'custom';
  icon?: React.ReactNode;
  duration?: number;
  createdAt: number;
}

type ToastFn = ((message: string, options?: ToastOptions) => string) & {
  success: (message: string, options?: ToastOptions) => string;
  error: (message: string, options?: ToastOptions) => string;
  loading: (message: string, options?: ToastOptions) => string;
  custom: (message: string, options?: ToastOptions) => string;
  dismiss: (id?: string) => void;
  remove: (id?: string) => void;
  promise: <T>(promise: Promise<T>, options: { loading: string; success: string | ((data: T) => string); error: string | ((err: unknown) => string) }) => Promise<T>;
};

interface ToastOptions {
  id?: string;
  icon?: React.ReactNode;
  duration?: number;
}

// ── State ──────────────────────────────────────────────────────────────

let toasts: ToastItem[] = [];
let listeners: Set<() => void> = new Set();
let containerRoot: ReturnType<typeof createRoot> | null = null;
let idCounter = 0;

function generateId(): string {
  return `toast-${Date.now()}-${++idCounter}`;
}

function notifyChange() {
  listeners.forEach(l => l());
  renderToasts();
}

// ── Toast Container (renders toasts as a fixed overlay) ────────────────

function ToastContainer() {
  return React.createElement('div', {
    style: {
      position: 'fixed',
      top: '16px',
      right: '16px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      pointerEvents: 'none',
    } as React.CSSProperties,
  },
    toasts.map(t =>
      React.createElement('div', {
        key: t.id,
        style: {
          background: '#2A1A0A',
          color: '#FFF4E6',
          border: '1px solid rgba(255,127,17,0.25)',
          borderRadius: '12px',
          padding: '12px 16px',
          boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 40px rgba(255,127,17,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '14px',
          minWidth: '250px',
          maxWidth: '400px',
          pointerEvents: 'auto',
          animation: 'slideIn 0.2s ease-out',
        } as React.CSSProperties,
      },
        t.type === 'success' && React.createElement('span', { style: { color: '#FF9F5A' } }, '✓'),
        t.type === 'error' && React.createElement('span', { style: { color: '#FB7185' } }, '✕'),
        t.type === 'loading' && React.createElement('span', { style: { color: '#FF9F5A', animation: 'spin 1s linear infinite', display: 'inline-block' } }, '⟳'),
        React.createElement('span', null, t.message),
      )
    )
  );
}

function ensureContainer() {
  if (typeof document === 'undefined') return;
  if (containerRoot) return;

  let container = document.getElementById('__toast_container__');
  if (!container) {
    container = document.createElement('div');
    container.id = '__toast_container__';
    document.body.appendChild(container);

    // Add animation keyframes
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
      @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    `;
    document.head.appendChild(style);
  }

  containerRoot = createRoot(container);
}

function renderToasts() {
  if (typeof window === 'undefined') return;
  ensureContainer();
  if (containerRoot) {
    containerRoot.render(React.createElement(ToastContainer));
  }
}

// ── Auto-dismiss ──────────────────────────────────────────────────────

function scheduleDismiss(id: string, duration: number) {
  if (duration === Infinity) return;
  setTimeout(() => {
    dismissToast(id);
  }, duration);
}

// ── Core functions ─────────────────────────────────────────────────────

function addToast(message: string, type: ToastItem['type'], options?: ToastOptions): string {
  const id = options?.id || generateId();
  const duration = options?.duration ?? (type === 'loading' ? Infinity : 4000);

  // Remove existing toast with same id
  toasts = toasts.filter(t => t.id !== id);

  toasts.push({
    id,
    message,
    type,
    icon: options?.icon,
    duration,
    createdAt: Date.now(),
  });

  notifyChange();
  scheduleDismiss(id, duration);
  return id;
}

function dismissToast(id?: string) {
  if (id) {
    toasts = toasts.filter(t => t.id !== id);
  } else {
    toasts = [];
  }
  notifyChange();
}

// ── Exported toast object ──────────────────────────────────────────────

export const toast: ToastFn = Object.assign(
  (message: string, options?: ToastOptions) => addToast(message, 'info', options),
  {
    success: (message: string, options?: ToastOptions) => addToast(message, 'success', options),
    error: (message: string, options?: ToastOptions) => addToast(message, 'error', options),
    loading: (message: string, options?: ToastOptions) => addToast(message, 'loading', options),
    custom: (message: string, options?: ToastOptions) => addToast(message, 'custom', options),
    dismiss: (id?: string) => dismissToast(id),
    remove: (id?: string) => dismissToast(id),
    promise: async <T,>(promise: Promise<T>, opts: { loading: string; success: string | ((data: T) => string); error: string | ((err: unknown) => string) }): Promise<T> => {
      const id = addToast(opts.loading, 'loading');
      try {
        const result = await promise;
        dismissToast(id);
        const msg = typeof opts.success === 'function' ? opts.success(result) : opts.success;
        addToast(msg, 'success');
        return result;
      } catch (err) {
        dismissToast(id);
        const msg = typeof opts.error === 'function' ? opts.error(err) : opts.error;
        addToast(msg, 'error');
        throw err;
      }
    },
  }
) as ToastFn;

/**
 * Pre-load toast (no-op, kept for API compatibility)
 */
export function preloadToast(): void {
  // No-op - our implementation doesn't need preloading
}
