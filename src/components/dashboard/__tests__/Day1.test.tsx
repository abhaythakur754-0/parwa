/**
 * Day 1 Unit Tests — Dashboard Shell & Infrastructure
 *
 * Tests for:
 * 1. SocketProvider — context provides socket state, badge counts, notifications
 * 2. DashboardHeaderBar — renders connection status, notifications, mode selector
 * 3. DashboardSidebar — dynamic badge counts from socket context
 * 4. DashboardLayout — wraps children with SocketProvider and HeaderBar
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockUseAuth = {
  user: {
    id: 'user-1',
    full_name: 'Test User',
    email: 'test@parwa.ai',
    company_name: 'TestCo',
    company_id: 'tenant-1',
  },
  logout: jest.fn(),
};

jest.mock('@/hooks/useAuth', () => ({
  useAuth: () => mockUseAuth,
}));

jest.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockSocket = {
  on: jest.fn(),
  off: jest.fn(),
  emit: jest.fn(),
  disconnect: jest.fn(),
  connected: true,
};

jest.mock('socket.io-client', () => ({
  io: jest.fn(() => mockSocket),
}));

jest.mock('@/lib/api', () => ({
  get: jest.fn(() => Promise.resolve(null)),
  post: jest.fn(() => Promise.resolve(null)),
  patch: jest.fn(() => Promise.resolve(null)),
  del: jest.fn(() => Promise.resolve(null)),
}));

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock localStorage
const store: Record<string, string> = {};
const localStorageMock = {
  getItem: jest.fn((key: string) => store[key] || null),
  setItem: jest.fn((key: string, val: string) => { store[key] = val; }),
  removeItem: jest.fn((key: string) => { delete store[key]; }),
  clear: jest.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
};
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ── Helper: Render with mock socket context ────────────────────────────

function renderWithSocket(
  ui: React.ReactElement,
  overrides: Record<string, any> = {}
) {
  // Use require to get the context after all mocks are set up
  const { SocketContext, SocketProvider } = require('@/lib/socket');
  const ctx = SocketContext;

  const defaultCtx = {
    socket: null,
    isConnected: true,
    badgeCounts: { tickets: 0, approvals: 0, notifications: 0 },
    notifications: [],
    latestTicketEvent: null,
    systemStatus: null,
    markNotificationRead: jest.fn(),
    clearNotifications: jest.fn(),
    ...overrides,
  };

  return render(
    <ctx.Provider value={defaultCtx}>
      {ui}
    </ctx.Provider>
  );
}

// =====================================================================
// Test 1: SocketProvider Context
// =====================================================================

describe('SocketProvider', () => {
  it('provides default socket context values', async () => {
    const { SocketProvider, useSocket } = require('@/lib/socket');

    let contextValue: any = null;

    function TestConsumer() {
      contextValue = useSocket();
      return <div data-testid="consumer">test</div>;
    }

    await act(async () => {
      render(
        <SocketProvider>
          <TestConsumer />
        </SocketProvider>
      );
    });

    expect(contextValue).not.toBeNull();
    expect(contextValue.isConnected).toBe(false);
    expect(contextValue.badgeCounts).toEqual({ tickets: 0, approvals: 0, notifications: 0 });
    expect(contextValue.notifications).toEqual([]);
    expect(contextValue.systemStatus).toBeNull();
    expect(typeof contextValue.markNotificationRead).toBe('function');
    expect(typeof contextValue.clearNotifications).toBe('function');
  });

  it('markNotificationRead function is callable', async () => {
    const { SocketProvider, useSocket } = require('@/lib/socket');

    let contextValue: any = null;

    function TestConsumer() {
      contextValue = useSocket();
      return null;
    }

    await act(async () => {
      render(
        <SocketProvider>
          <TestConsumer />
        </SocketProvider>
      );
    });

    // Should not throw
    expect(() => contextValue.markNotificationRead('notif-1')).not.toThrow();
  });

  it('clearNotifications resets badge counts', async () => {
    const { SocketProvider, useSocket } = require('@/lib/socket');

    let contextValue: any = null;

    function TestConsumer() {
      contextValue = useSocket();
      return null;
    }

    await act(async () => {
      render(
        <SocketProvider>
          <TestConsumer />
        </SocketProvider>
      );
    });

    await act(() => {
      contextValue.clearNotifications();
    });

    expect(contextValue.notifications.length).toBe(0);
    expect(contextValue.badgeCounts.notifications).toBe(0);
  });
});

// =====================================================================
// Test 2: DashboardHeaderBar
// =====================================================================

describe('DashboardHeaderBar', () => {
  it('renders connection status, system status, and user info when connected', async () => {
    const DashboardHeaderBar = require('@/components/dashboard/DashboardHeaderBar').default;

    await act(async () => {
      renderWithSocket(<DashboardHeaderBar />, {
        isConnected: true,
        badgeCounts: { tickets: 3, approvals: 1, notifications: 5 },
        systemStatus: { status: 'healthy' },
      });
    });

    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('Pause')).toBeInTheDocument();
    expect(screen.getByText('Live')).toBeInTheDocument();
    expect(screen.getByText('Simulation')).toBeInTheDocument();
    expect(screen.getByText('Training')).toBeInTheDocument();
  });

  it('shows Offline and Down status when disconnected', async () => {
    const DashboardHeaderBar = require('@/components/dashboard/DashboardHeaderBar').default;

    await act(async () => {
      renderWithSocket(<DashboardHeaderBar />, {
        isConnected: false,
        badgeCounts: { tickets: 0, approvals: 0, notifications: 0 },
        systemStatus: { status: 'down' },
      });
    });

    expect(screen.getByText('Offline')).toBeInTheDocument();
    expect(screen.getByText('Down')).toBeInTheDocument();
  });

  it('shows PAUSED when emergency pause is active', async () => {
    const DashboardHeaderBar = require('@/components/dashboard/DashboardHeaderBar').default;

    await act(async () => {
      renderWithSocket(<DashboardHeaderBar />, {
        isConnected: true,
        systemStatus: { status: 'healthy' },
      });
    });

    // Component initializes unpaused, click to pause
    const pauseBtn = screen.getByTitle('Emergency pause AI');
    await act(async () => {
      fireEvent.click(pauseBtn);
    });

    // The post mock will resolve, state updates
    expect(screen.getByText('PAUSED')).toBeInTheDocument();
  });

  it('hides notification count when zero', async () => {
    const DashboardHeaderBar = require('@/components/dashboard/DashboardHeaderBar').default;

    await act(async () => {
      renderWithSocket(<DashboardHeaderBar />, {
        isConnected: true,
        badgeCounts: { tickets: 0, approvals: 0, notifications: 0 },
        systemStatus: { status: 'healthy' },
      });
    });

    // No numeric badge with just "5" or similar
    expect(screen.queryByText('5')).not.toBeInTheDocument();
  });
});

// =====================================================================
// Test 3: DashboardSidebar — Dynamic Badges
// =====================================================================

describe('DashboardSidebar', () => {
  it('shows dynamic badge counts from socket', async () => {
    const DashboardSidebar = require('@/components/dashboard/DashboardSidebar').default;

    await act(async () => {
      renderWithSocket(
        <DashboardSidebar collapsed={false} onToggle={jest.fn()} />,
        { badgeCounts: { tickets: 7, approvals: 3, notifications: 2 } }
      );
    });

    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('hides badges when counts are zero', async () => {
    const DashboardSidebar = require('@/components/dashboard/DashboardSidebar').default;

    await act(async () => {
      renderWithSocket(
        <DashboardSidebar collapsed={false} onToggle={jest.fn()} />,
        { badgeCounts: { tickets: 0, approvals: 0, notifications: 0 } }
      );
    });

    expect(screen.queryByText('7')).not.toBeInTheDocument();
    expect(screen.queryByText('3')).not.toBeInTheDocument();
  });

  it('shows all navigation items', async () => {
    const DashboardSidebar = require('@/components/dashboard/DashboardSidebar').default;

    await act(async () => {
      renderWithSocket(
        <DashboardSidebar collapsed={false} onToggle={jest.fn()} />
      );
    });

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tickets')).toBeInTheDocument();
    expect(screen.getByText('Channels')).toBeInTheDocument();
    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getByText('Approvals')).toBeInTheDocument();
    expect(screen.getByText('Jarvis AI')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('shows user name and logout button when not collapsed', async () => {
    const DashboardSidebar = require('@/components/dashboard/DashboardSidebar').default;

    await act(async () => {
      renderWithSocket(
        <DashboardSidebar collapsed={false} onToggle={jest.fn()} />
      );
    });

    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByTitle('Logout')).toBeInTheDocument();
  });

  it('collapses and hides labels', async () => {
    const DashboardSidebar = require('@/components/dashboard/DashboardSidebar').default;

    await act(async () => {
      renderWithSocket(
        <DashboardSidebar collapsed={true} onToggle={jest.fn()} />
      );
    });

    // When collapsed, nav labels should not be visible
    expect(screen.queryByText('Tickets')).not.toBeInTheDocument();
  });
});

// =====================================================================
// Test 4: DashboardLayout — SocketProvider + HeaderBar Wiring
// =====================================================================

describe('DashboardLayout', () => {
  it('renders children content', async () => {
    const { DashboardLayout } = require('@/components/dashboard/DashboardLayout');

    await act(async () => {
      render(
        <DashboardLayout>
          <div data-testid="test-content">Dashboard Content</div>
        </DashboardLayout>
      );
    });

    expect(screen.getByTestId('test-content')).toBeInTheDocument();
    expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
  });

  it('renders sidebar with PARWA brand', async () => {
    const { DashboardLayout } = require('@/components/dashboard/DashboardLayout');

    await act(async () => {
      render(
        <DashboardLayout>
          <div>Content</div>
        </DashboardLayout>
      );
    });

    // Sidebar brand
    const parwaElements = screen.getAllByText('PARWA');
    expect(parwaElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders sidebar navigation items', async () => {
    const { DashboardLayout } = require('@/components/dashboard/DashboardLayout');

    await act(async () => {
      render(
        <DashboardLayout>
          <div>Content</div>
        </DashboardLayout>
      );
    });

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tickets')).toBeInTheDocument();
  });
});
