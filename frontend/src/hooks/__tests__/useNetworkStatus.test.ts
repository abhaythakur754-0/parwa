/**
 * PARWA Day 7 Unit Tests — useNetworkStatus Hook
 *
 * Tests online/offline detection, event handling,
 * wasOffline tracking, offline count, and reset.
 */

import { renderHook, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

describe('useNetworkStatus', () => {
  beforeEach(() => {
    // Reset navigator.onLine to true before each test
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
      configurable: true,
    });
  });

  it('returns isOnline=true by default when navigator.onLine is true', () => {
    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.isOnline).toBe(true);
    expect(result.current.isOffline).toBe(false);
  });

  it('returns isOnline=false when navigator.onLine is false', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true });
    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.isOnline).toBe(false);
    expect(result.current.isOffline).toBe(true);
  });

  it('updates when offline event fires', () => {
    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.isOnline).toBe(true);

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.isOnline).toBe(false);
    expect(result.current.isOffline).toBe(true);
    expect(result.current.wasOffline).toBe(true);
    expect(result.current.lastChange).toBe('offline');
    expect(result.current.offlineCount).toBe(1);
    expect(result.current.lastChangedAt).not.toBeNull();
  });

  it('updates when online event fires after offline', () => {
    const { result } = renderHook(() => useNetworkStatus());

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.isOnline).toBe(false);

    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    expect(result.current.isOnline).toBe(true);
    expect(result.current.lastChange).toBe('online');
  });

  it('tracks wasOffline correctly', () => {
    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.wasOffline).toBe(false);

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.wasOffline).toBe(true);

    // wasOffline persists even after coming back online
    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    expect(result.current.wasOffline).toBe(true);
  });

  it('resets wasOffline with resetWasOffline()', () => {
    const { result } = renderHook(() => useNetworkStatus());

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.wasOffline).toBe(true);

    act(() => {
      result.current.resetWasOffline();
    });

    expect(result.current.wasOffline).toBe(false);
  });

  it('counts multiple offline events', () => {
    const { result } = renderHook(() => useNetworkStatus());

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });
    act(() => {
      window.dispatchEvent(new Event('online'));
    });
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current.offlineCount).toBe(2);
  });

  it('sets lastChangedAt to an ISO timestamp', () => {
    const { result } = renderHook(() => useNetworkStatus());
    expect(result.current.lastChangedAt).toBeNull();

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    const timestamp = result.current.lastChangedAt;
    expect(timestamp).not.toBeNull();
    expect(new Date(timestamp!).toISOString()).toBe(timestamp);
  });

  it('cleans up event listeners on unmount', () => {
    const { unmount } = renderHook(() => useNetworkStatus());

    unmount();

    // After unmount, firing events should not throw
    expect(() => {
      window.dispatchEvent(new Event('offline'));
    }).not.toThrow();
  });
});
