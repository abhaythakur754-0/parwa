/**
 * Dynamic Toast Wrapper
 *
 * Avoids static `import toast from 'react-hot-toast'` which causes TDZ errors
 * ("Cannot access 'X' before initialization") in the Next.js production build.
 *
 * react-hot-toast is an ESM module that, when bundled into a shared webpack chunk
 * alongside other onboarding dependencies, triggers TDZ errors during module
 * evaluation. By dynamically importing it, we defer evaluation until first use.
 *
 * Usage: Same API as react-hot-toast
 *   import { toast } from '@/lib/dynamic-toast';
 *   toast.success('Done!');
 *   toast.error('Failed');
 *   toast('Loading...', { icon: '🔄' });
 *   toast.dismiss();
 *
 * IMPORTANT: The first call to toast will be async (returns a Promise).
 * If you need the toast ID, use: const id = await toast.success('Done!');
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyFn = (...args: any[]) => any;
type ToastType = AnyFn & {
  success: AnyFn;
  error: AnyFn;
  loading: AnyFn;
  custom: AnyFn;
  promise: AnyFn;
  dismiss: AnyFn;
  remove: AnyFn;
};

let _toast: ToastType | null = null;
let _loadPromise: Promise<ToastType> | null = null;

async function loadToast(): Promise<ToastType> {
  if (_toast) return _toast;
  if (_loadPromise) return _loadPromise;

  _loadPromise = import('react-hot-toast').then((mod) => {
    _toast = mod.default as ToastType;
    _loadPromise = null;
    return _toast;
  });

  return _loadPromise;
}

/**
 * Create a method that queues the call and replays once toast is loaded.
 */
function createMethod(method: string | null): AnyFn {
  return (...args: unknown[]) => {
    return loadToast().then((t) => {
      const fn = method ? t[method as keyof ToastType] : t;
      if (typeof fn === 'function') {
        return fn(...args);
      }
      return t(args[0], args[1]);
    });
  };
}

/**
 * Drop-in replacement for `toast` from react-hot-toast.
 * Dynamically loads the module on first call.
 */
export const toast: ToastType = Object.assign(
  createMethod(null), // toast('msg')
  {
    success: createMethod('success'),
    error: createMethod('error'),
    loading: createMethod('loading'),
    custom: createMethod('custom'),
    promise: createMethod('promise'),
    dismiss: createMethod('dismiss'),
    remove: createMethod('remove'),
  }
) as ToastType;

/**
 * Pre-load the toast module so it's ready when needed.
 * Call this early (e.g., in a useEffect) to avoid delay on first toast.
 */
export function preloadToast(): void {
  loadToast().catch(() => {
    // Silently fail — toast will retry on next use
  });
}
