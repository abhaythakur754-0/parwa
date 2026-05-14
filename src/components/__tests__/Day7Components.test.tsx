/**
 * PARWA Day 7 Unit Tests — UI Components
 *
 * Tests OfflineBanner, SkipLink, AccessibilityAnnouncer,
 * DashboardSkeleton, and toast accessibility improvements.
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { OfflineBanner } from '@/components/OfflineBanner';
import { SkipLink } from '@/components/SkipLink';
import { AccessibilityAnnouncer, announce } from '@/components/AccessibilityAnnouncer';
import { DashboardSkeleton, KPICardSkeleton, ChartSkeleton, TableSkeleton } from '@/components/DashboardSkeleton';
import { RealtimeToast } from '@/components/notifications/RealtimeToast';
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

// ── OfflineBanner Tests ────────────────────────────────────────────

describe('OfflineBanner', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
  });

  it('renders nothing when online', () => {
    render(React.createElement(OfflineBanner));
    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
  });

  it('renders offline banner when browser goes offline', () => {
    render(React.createElement(OfflineBanner));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(screen.getByTestId('offline-banner')).toBeInTheDocument();
    expect(screen.getByText(/You are offline/)).toBeInTheDocument();
  });

  it('has role="alert" for accessibility', () => {
    render(React.createElement(OfflineBanner));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    const banner = screen.getByTestId('offline-banner');
    expect(banner).toHaveAttribute('role', 'alert');
    expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  it('can be dismissed with the dismiss button', () => {
    render(React.createElement(OfflineBanner));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(screen.getByTestId('offline-banner')).toBeInTheDocument();

    const dismissBtn = screen.getByLabelText('Dismiss offline banner');
    fireEvent.click(dismissBtn);

    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
  });

  it('can be dismissed with Escape key', () => {
    render(React.createElement(OfflineBanner));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    const banner = screen.getByTestId('offline-banner');
    fireEvent.keyDown(banner.querySelector('button')!, { key: 'Escape' });

    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
  });

  it('shows "Back online" when reconnecting after being offline', () => {
    jest.useFakeTimers();
    render(React.createElement(OfflineBanner));

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    expect(screen.getByText(/Back online/)).toBeInTheDocument();

    // Auto-hides after 3 seconds
    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
    jest.useRealTimers();
  });
});

// ── SkipLink Tests ────────────────────────────────────────────────

describe('SkipLink', () => {
  it('renders a skip link', () => {
    render(React.createElement(SkipLink));
    expect(screen.getByTestId('skip-link')).toBeInTheDocument();
  });

  it('has correct default href', () => {
    render(React.createElement(SkipLink));
    expect(screen.getByTestId('skip-link')).toHaveAttribute('href', '#main-content');
  });

  it('has correct default label text', () => {
    render(React.createElement(SkipLink));
    expect(screen.getByText('Skip to main content')).toBeInTheDocument();
  });

  it('accepts custom targetId', () => {
    render(React.createElement(SkipLink, { targetId: 'custom-target' }));
    expect(screen.getByTestId('skip-link')).toHaveAttribute('href', '#custom-target');
  });

  it('accepts custom label', () => {
    render(React.createElement(SkipLink, { label: 'Jump to content' }));
    expect(screen.getByText('Jump to content')).toBeInTheDocument();
  });

  it('is visually hidden by default (sr-only)', () => {
    render(React.createElement(SkipLink));
    const link = screen.getByTestId('skip-link');
    expect(link.className).toContain('sr-only');
  });

  it('becomes visible on focus (focus:not-sr-only)', () => {
    render(React.createElement(SkipLink));
    const link = screen.getByTestId('skip-link');
    expect(link.className).toContain('focus:not-sr-only');
  });

  it('scrolls to target element on click', () => {
    // jsdom doesn't implement scrollIntoView, so we need to add it
    const scrollIntoViewMock = jest.fn();
    render(
      React.createElement('div', null,
        React.createElement(SkipLink, { targetId: 'main' }),
        React.createElement('main', { id: 'main', tabIndex: -1, 'data-testid': 'main-content' }, 'Main')
      )
    );

    const link = screen.getByTestId('skip-link');
    const main = screen.getByTestId('main-content');
    main.scrollIntoView = scrollIntoViewMock;

    fireEvent.click(link);

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' });
  });
});

// ── AccessibilityAnnouncer Tests ──────────────────────────────────

describe('AccessibilityAnnouncer', () => {
  it('renders polite and assertive live regions', () => {
    render(React.createElement(AccessibilityAnnouncer));

    expect(screen.getByTestId('aria-live-polite')).toBeInTheDocument();
    expect(screen.getByTestId('aria-live-assertive')).toBeInTheDocument();
  });

  it('polite region has correct ARIA attributes', () => {
    render(React.createElement(AccessibilityAnnouncer));

    const polite = screen.getByTestId('aria-live-polite');
    expect(polite).toHaveAttribute('role', 'status');
    expect(polite).toHaveAttribute('aria-live', 'polite');
    expect(polite).toHaveAttribute('aria-atomic', 'true');
  });

  it('assertive region has correct ARIA attributes', () => {
    render(React.createElement(AccessibilityAnnouncer));

    const assertive = screen.getByTestId('aria-live-assertive');
    expect(assertive).toHaveAttribute('role', 'alert');
    expect(assertive).toHaveAttribute('aria-live', 'assertive');
    expect(assertive).toHaveAttribute('aria-atomic', 'true');
  });

  it('announce() writes to polite region', () => {
    jest.useFakeTimers();
    render(React.createElement(AccessibilityAnnouncer));

    act(() => {
      announce('Test message', 'polite');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-polite').textContent).toBe('Test message');
    jest.useRealTimers();
  });

  it('announce() writes to assertive region', () => {
    jest.useFakeTimers();
    render(React.createElement(AccessibilityAnnouncer));

    act(() => {
      announce('Error message', 'assertive');
    });

    act(() => {
      jest.advanceTimersByTime(200);
    });

    expect(screen.getByTestId('aria-live-assertive').textContent).toBe('Error message');
    jest.useRealTimers();
  });

  it('both regions are visually hidden (sr-only)', () => {
    render(React.createElement(AccessibilityAnnouncer));

    expect(screen.getByTestId('aria-live-polite').className).toContain('sr-only');
    expect(screen.getByTestId('aria-live-assertive').className).toContain('sr-only');
  });
});

// ── DashboardSkeleton Tests ───────────────────────────────────────

describe('DashboardSkeleton', () => {
  it('renders KPICardSkeleton with accessibility attributes', () => {
    render(React.createElement(KPICardSkeleton));
    const skeleton = screen.getByTestId('kpi-skeleton');
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute('aria-busy', 'true');
    expect(skeleton).toHaveAttribute('role', 'status');
    expect(skeleton).toHaveAttribute('aria-label', 'Loading KPI data');
  });

  it('renders ChartSkeleton with accessibility attributes', () => {
    render(React.createElement(ChartSkeleton));
    const skeleton = screen.getByTestId('chart-skeleton');
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute('aria-busy', 'true');
    expect(skeleton).toHaveAttribute('role', 'status');
  });

  it('renders TableSkeleton with accessibility attributes', () => {
    render(React.createElement(TableSkeleton, { rows: 3 }));
    const skeleton = screen.getByTestId('table-skeleton');
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute('aria-busy', 'true');
    expect(skeleton).toHaveAttribute('role', 'status');
  });

  it('renders full DashboardSkeleton', () => {
    render(React.createElement(DashboardSkeleton));
    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();
    // Should contain 4 KPI skeletons
    const kpis = screen.getAllByTestId('kpi-skeleton');
    expect(kpis.length).toBe(4);
    // Should contain charts
    const charts = screen.getAllByTestId('chart-skeleton');
    expect(charts.length).toBe(2);
    // Should contain table
    expect(screen.getByTestId('table-skeleton')).toBeInTheDocument();
  });

  it('DashboardSkeleton has screen reader announcement', () => {
    render(React.createElement(DashboardSkeleton));
    expect(screen.getByText('Dashboard content is loading, please wait.')).toBeInTheDocument();
  });
});

// ── RealtimeToast Accessibility Tests ─────────────────────────────

describe('RealtimeToast Accessibility', () => {
  beforeEach(() => {
    useNotificationStore.getState().clearAll();
  });

  it('toast container has role="region" and aria-label', () => {
    useNotificationStore.getState().addToast({
      type: 'info',
      category: 'system',
      title: 'Test',
      message: 'Message',
      priority: 'high',
    });

    const { container } = render(React.createElement(RealtimeToast));
    const region = container.querySelector('[role="region"]');
    expect(region).toBeInTheDocument();
    expect(region).toHaveAttribute('aria-label', 'Notifications');
    expect(region).toHaveAttribute('aria-live', 'polite');
  });

  it('info toast has role="status"', () => {
    useNotificationStore.getState().addToast({
      type: 'info',
      category: 'system',
      title: 'Info Test',
      message: 'Info message',
      priority: 'high',
    });

    const { container } = render(React.createElement(RealtimeToast));
    const toast = container.querySelector('[role="status"]');
    expect(toast).toBeInTheDocument();
  });

  it('error toast has role="alert" and aria-live="assertive"', () => {
    useNotificationStore.getState().addToast({
      type: 'error',
      category: 'system',
      title: 'Error Test',
      message: 'Error message',
      priority: 'high',
    });

    const { container } = render(React.createElement(RealtimeToast));
    const alert = container.querySelector('[role="alert"]');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveAttribute('aria-live', 'assertive');
  });

  it('dismiss button has descriptive aria-label', () => {
    useNotificationStore.getState().addToast({
      type: 'success',
      category: 'system',
      title: 'Saved',
      message: 'Data saved',
      priority: 'high',
    });

    render(React.createElement(RealtimeToast));
    const btn = screen.getByLabelText('Dismiss notification: Saved');
    expect(btn).toBeInTheDocument();
  });

  it('toast icon has aria-hidden="true"', () => {
    useNotificationStore.getState().addToast({
      type: 'warning',
      category: 'system',
      title: 'Warning',
      message: 'Be careful',
      priority: 'high',
    });

    const { container } = render(React.createElement(RealtimeToast));
    const iconSpan = container.querySelector('[aria-hidden="true"]');
    expect(iconSpan).toBeInTheDocument();
  });
});
