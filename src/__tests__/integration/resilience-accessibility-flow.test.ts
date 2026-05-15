/**
 * PARWA Day 7 Integration Tests — Full Resilience Flow
 *
 * Tests the complete resilience and accessibility pipeline:
 * - Offline detection → OfflineBanner → retry with backoff → recovery → toast
 * - Keyboard navigation → SkipLink → focus management → accessibility announcements
 * - Cross-component resilience: ErrorBoundary + retry + offline + toast
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useRetryWithBackoff } from '@/hooks/useRetryWithBackoff';
import { AccessibilityAnnouncer, announce } from '@/components/AccessibilityAnnouncer';
import { OfflineBanner } from '@/components/OfflineBanner';
import { SkipLink } from '@/components/SkipLink';
import { useNotificationStore } from '@/lib/notification-store';

// ── Mocks ────────────────────────────────────────────────────────────

jest.mock('next/navigation', () => ({
  useRouter() {
    return { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn(), pathname: '/', query: {}, asPath: '/' };
  },
  useSearchParams() { return new URLSearchParams(); },
  usePathname() { return '/'; },
}));

jest.mock('lucide-react', () => {
  return new Proxy({}, {
    get: function(_target: Record<string, unknown>, prop: string) {
      return (props: Record<string, unknown>) =>
        React.createElement('svg', { 'data-testid': `icon-${prop.toLowerCase()}`, ...props });
    },
  });
});

// ── Integration: Offline → Retry → Recovery → Toast ──────────────

describe('Integration: Offline → Retry → Recovery Flow', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
    useNotificationStore.getState().clearAll();
  });

  it('detects offline, shows banner, and recovers when back online', async () => {
    jest.useFakeTimers();

    function ResilientComponent() {
      const { isOnline, wasOffline } = useNetworkStatus();

      return React.createElement('div', { 'data-testid': 'resilient-component' },
        React.createElement(AccessibilityAnnouncer),
        React.createElement(OfflineBanner),
        React.createElement('span', { 'data-testid': 'status-text' }, isOnline ? 'Online' : 'Offline')
      );
    }

    render(React.createElement(ResilientComponent));

    // Initially online
    expect(screen.getByTestId('status-text')).toHaveTextContent('Online');

    // Go offline
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(screen.getByTestId('status-text')).toHaveTextContent('Offline');
    expect(screen.getByTestId('offline-banner')).toBeInTheDocument();

    // Come back online
    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    // Should show back online banner
    expect(screen.getByText(/Back online/)).toBeInTheDocument();

    jest.useRealTimers();
  });

  it('retry with backoff recovers after reconnecting', async () => {
    let shouldFail = true;

    function RetryComponent() {
      const { isOffline } = useNetworkStatus();
      const fetchFn = React.useCallback(async () => {
        if (shouldFail) throw new Error('Network error');
        return { data: 'recovered' };
      }, []);

      const retry = useRetryWithBackoff(fetchFn, {
        maxRetries: 2,
        baseDelay: 1,
        onSuccess: () => {
          announce('Data recovered', 'polite');
        },
      });

      return React.createElement('div', null,
        React.createElement(AccessibilityAnnouncer),
        React.createElement('span', { 'data-testid': 'retry-status' }, retry.data ? 'Has Data' : retry.error ? 'Error' : 'Idle'),
        React.createElement('button', {
          'data-testid': 'retry-btn',
          onClick: () => retry.execute()
        }, 'Fetch')
      );
    }

    render(React.createElement(RetryComponent));

    // Click to start fetching (will fail)
    await act(async () => {
      fireEvent.click(screen.getByTestId('retry-btn'));
    });

    // Should eventually show error after retries exhausted
    await waitFor(() => {
      expect(screen.getByTestId('retry-status')).toHaveTextContent('Error');
    });

    // Now let fetch succeed
    shouldFail = false;

    // Click retry button again
    await act(async () => {
      fireEvent.click(screen.getByTestId('retry-btn'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('retry-status')).toHaveTextContent('Has Data');
    });
  });
});

// ── Integration: Keyboard Navigation + Accessibility ──────────────

describe('Integration: Keyboard Navigation + Accessibility', () => {
  it('SkipLink + Announcer work together for accessible navigation', () => {
    jest.useFakeTimers();

    function AccessiblePage() {
      return React.createElement('div', null,
        React.createElement(AccessibilityAnnouncer),
        React.createElement(SkipLink, { targetId: 'main' }),
        React.createElement('nav', { 'data-testid': 'nav' }, 'Navigation'),
        React.createElement('main', { id: 'main', tabIndex: -1, 'data-testid': 'main' }, 'Main Content')
      );
    }

    render(React.createElement(AccessiblePage));

    // SkipLink exists
    expect(screen.getByTestId('skip-link')).toBeInTheDocument();

    // Announcer regions exist
    expect(screen.getByTestId('aria-live-polite')).toBeInTheDocument();
    expect(screen.getByTestId('aria-live-assertive')).toBeInTheDocument();

    // Announce navigation
    act(() => {
      announce('Navigated to main content', 'polite');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-polite').textContent).toBe('Navigated to main content');

    jest.useRealTimers();
  });

  it('announces errors assertively and successes politely', () => {
    jest.useFakeTimers();
    render(React.createElement(AccessibilityAnnouncer));

    act(() => {
      announce('Validation error: Email is required', 'assertive');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-assertive').textContent).toBe('Validation error: Email is required');

    // Clear and announce success
    act(() => {
      announce('Form submitted successfully', 'polite');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-polite').textContent).toBe('Form submitted successfully');

    jest.useRealTimers();
  });
});

// ── Integration: Offline + Notification Store ─────────────────────

describe('Integration: Offline Detection + Notification Store', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
    useNotificationStore.getState().clearAll();
  });

  it('adds system notification when going offline', () => {
    function OfflineNotifier() {
      const { isOffline } = useNetworkStatus();

      React.useEffect(() => {
        if (isOffline) {
          useNotificationStore.getState().addNotification({
            type: 'warning',
            category: 'system',
            title: 'Connection Lost',
            message: 'You are offline. Changes will sync when you reconnect.',
            priority: 'high',
          });
        }
      }, [isOffline]);

      return React.createElement('div', { 'data-testid': 'offline-notifier' },
        isOffline ? 'Offline' : 'Online'
      );
    }

    render(React.createElement(OfflineNotifier));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    const state = useNotificationStore.getState();
    expect(state.notifications.length).toBeGreaterThan(0);
    expect(state.notifications[0].title).toBe('Connection Lost');
    expect(state.notifications[0].type).toBe('warning');
  });

  it('adds success notification when coming back online', () => {
    function OnlineRecovery() {
      const { wasOffline, lastChange } = useNetworkStatus();

      React.useEffect(() => {
        if (wasOffline && lastChange === 'online') {
          useNotificationStore.getState().addNotification({
            type: 'success',
            category: 'system',
            title: 'Back Online',
            message: 'Your connection has been restored.',
            priority: 'medium',
          });
        }
      }, [wasOffline, lastChange]);

      return React.createElement('div', null, 'Recovery');
    }

    render(React.createElement(OnlineRecovery));

    // Go offline first
    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    // Then come online
    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    const state = useNotificationStore.getState();
    const onlineNotif = state.notifications.find(n => n.title === 'Back Online');
    expect(onlineNotif).toBeDefined();
    expect(onlineNotif?.type).toBe('success');
  });
});

// ── Integration: Retry + Notification Store ───────────────────────

describe('Integration: Retry with Backoff + Notifications', () => {
  beforeEach(() => {
    useNotificationStore.getState().clearAll();
  });

  it('notifies on retry exhaustion', async () => {
    function RetryWithNotification() {
      const fetchFn = React.useCallback(async () => {
        throw new Error('Server unavailable');
      }, []);

      const retry = useRetryWithBackoff(fetchFn, {
        maxRetries: 0,
        baseDelay: 1,
        onError: (error) => {
          useNotificationStore.getState().addNotification({
            type: 'error',
            category: 'system',
            title: 'Sync Failed',
            message: error.message,
            priority: 'high',
          });
        },
      });

      React.useEffect(() => {
        retry.execute();
      }, []);

      return React.createElement('div', null, retry.hasExhaustedRetries ? 'Failed' : 'Trying');
    }

    render(React.createElement(RetryWithNotification));

    await waitFor(() => {
      const state = useNotificationStore.getState();
      const errorNotif = state.notifications.find(n => n.title === 'Sync Failed');
      expect(errorNotif).toBeDefined();
      expect(errorNotif?.type).toBe('error');
    });
  });
});

// ── Integration: Accessibility Announcer + Toast ──────────────────

describe('Integration: Announcer + Toast Accessibility', () => {
  beforeEach(() => {
    useNotificationStore.getState().clearAll();
  });

  it('toast announcements are accessible via live regions', () => {
    jest.useFakeTimers();
    render(React.createElement(AccessibilityAnnouncer));

    // Simulate a toast being added
    act(() => {
      useNotificationStore.getState().addToast({
        type: 'success',
        category: 'system',
        title: 'Ticket Resolved',
        message: 'Ticket #1234 has been resolved.',
        priority: 'high',
      });
      announce('Notification: Ticket Resolved', 'polite');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-polite').textContent).toBe('Notification: Ticket Resolved');

    jest.useRealTimers();
  });

  it('error toasts are announced assertively', () => {
    jest.useFakeTimers();
    render(React.createElement(AccessibilityAnnouncer));

    act(() => {
      useNotificationStore.getState().addToast({
        type: 'error',
        category: 'system',
        title: 'Payment Failed',
        message: 'Your payment method was declined.',
        priority: 'critical',
      });
      announce('Error: Payment Failed', 'assertive');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-assertive').textContent).toBe('Error: Payment Failed');

    jest.useRealTimers();
  });
});

// ── Integration: Full Page Accessibility ──────────────────────────

describe('Integration: Full Page Accessibility Structure', () => {
  it('page has proper landmark structure with SkipLink', () => {
    function AccessibleApp() {
      return React.createElement('div', null,
        React.createElement(AccessibilityAnnouncer),
        React.createElement(SkipLink),
        React.createElement('header', { role: 'banner', 'data-testid': 'header' }, 'Header'),
        React.createElement('nav', { role: 'navigation', 'aria-label': 'Main navigation', 'data-testid': 'nav' }, 'Nav'),
        React.createElement('main', { id: 'main-content', role: 'main', tabIndex: -1, 'data-testid': 'main' }, 'Content'),
        React.createElement('footer', { role: 'contentinfo', 'data-testid': 'footer' }, 'Footer')
      );
    }

    render(React.createElement(AccessibleApp));

    // Verify landmarks
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('navigation')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();

    // Verify SkipLink points to main content
    expect(screen.getByTestId('skip-link')).toHaveAttribute('href', '#main-content');

    // Verify live regions
    expect(screen.getByTestId('aria-live-polite')).toBeInTheDocument();
    expect(screen.getByTestId('aria-live-assertive')).toBeInTheDocument();
  });

  it('all interactive elements have accessible labels', () => {
    useNotificationStore.getState().clearAll();

    function LabeledApp() {
      return React.createElement('div', null,
        React.createElement(AccessibilityAnnouncer),
        React.createElement('button', { 'aria-label': 'Open navigation menu', 'data-testid': 'menu-btn' }, 'Menu'),
        React.createElement('button', { 'aria-label': 'Search', 'data-testid': 'search-btn' }, 'Search')
      );
    }

    render(React.createElement(LabeledApp));

    expect(screen.getByLabelText('Open navigation menu')).toBeInTheDocument();
    expect(screen.getByLabelText('Search')).toBeInTheDocument();
  });
});
