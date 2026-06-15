'use client';

/**
 * ClientToaster — renders the toast notification container.
 *
 * Previously used react-hot-toast's Toaster component, which caused
 * TDZ errors in the Next.js production build. Now uses our self-contained
 * toast system from @/lib/dynamic-toast which renders toasts directly.
 *
 * This component is kept as a no-op placeholder for layout compatibility.
 * All toast rendering is handled internally by dynamic-toast.ts using
 * ReactDOM.createRoot() and a fixed overlay container.
 */
export function ClientToaster() {
  // Our dynamic-toast.ts renders its own container via createRoot(),
  // so this component doesn't need to render anything.
  return null;
}
