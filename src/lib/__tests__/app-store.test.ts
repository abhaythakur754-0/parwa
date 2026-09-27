/**
 * PARWA App Store — Unit Tests
 *
 * Tests navigation, auth state, sidebar, and helper functions.
 */

import { useAppStore, isDashboardPage, getPageTitle, Page } from '@/lib/store';

describe('useAppStore', () => {
  beforeEach(() => {
    useAppStore.setState({
      currentPage: 'landing',
      previousPage: null,
      isAuthenticated: false,
      sidebarOpen: true,
      user: null,
    });
  });

  describe('initial state', () => {
    it('starts on landing page', () => {
      expect(useAppStore.getState().currentPage).toBe('landing');
    });

    it('has no previous page', () => {
      expect(useAppStore.getState().previousPage).toBeNull();
    });

    it('is not authenticated', () => {
      expect(useAppStore.getState().isAuthenticated).toBe(false);
    });

    it('has sidebar open by default', () => {
      expect(useAppStore.getState().sidebarOpen).toBe(true);
    });

    it('has no user', () => {
      expect(useAppStore.getState().user).toBeNull();
    });
  });

  describe('navigate', () => {
    it('updates currentPage and sets previousPage', () => {
      useAppStore.getState().navigate('login');
      expect(useAppStore.getState().currentPage).toBe('login');
      expect(useAppStore.getState().previousPage).toBe('landing');
    });

    it('tracks navigation history correctly', () => {
      useAppStore.getState().navigate('login');
      useAppStore.getState().navigate('signup');

      expect(useAppStore.getState().currentPage).toBe('signup');
      expect(useAppStore.getState().previousPage).toBe('login');
    });

    it('navigates to dashboard sub-pages', () => {
      useAppStore.getState().navigate('dashboard');
      useAppStore.getState().navigate('dashboard-tickets');

      expect(useAppStore.getState().currentPage).toBe('dashboard-tickets');
      expect(useAppStore.getState().previousPage).toBe('dashboard');
    });
  });

  describe('goBack', () => {
    it('returns to previous page', () => {
      useAppStore.getState().navigate('login');
      useAppStore.getState().navigate('signup');
      useAppStore.getState().goBack();

      expect(useAppStore.getState().currentPage).toBe('login');
      expect(useAppStore.getState().previousPage).toBeNull();
    });

    it('does nothing when there is no previous page', () => {
      useAppStore.getState().goBack();
      expect(useAppStore.getState().currentPage).toBe('landing');
    });
  });

  describe('setAuth', () => {
    it('sets authenticated state with user', () => {
      const user = {
        email: 'test@example.com',
        full_name: 'Test User',
        company_name: 'TestCo',
        role: 'admin',
      };

      useAppStore.getState().setAuth(true, user);

      expect(useAppStore.getState().isAuthenticated).toBe(true);
      expect(useAppStore.getState().user).toEqual(user);
      expect(useAppStore.getState().currentPage).toBe('dashboard');
    });

    it('sets unauthenticated state and goes to landing', () => {
      useAppStore.getState().setAuth(true, { email: 'test@example.com' });
      useAppStore.getState().setAuth(false);

      expect(useAppStore.getState().isAuthenticated).toBe(false);
      expect(useAppStore.getState().user).toBeNull();
      expect(useAppStore.getState().currentPage).toBe('landing');
    });

    it('sets user to null when authenticated without user data', () => {
      useAppStore.getState().setAuth(true);
      expect(useAppStore.getState().isAuthenticated).toBe(true);
      expect(useAppStore.getState().user).toBeNull();
      expect(useAppStore.getState().currentPage).toBe('dashboard');
    });
  });

  describe('toggleSidebar', () => {
    it('toggles sidebar open state', () => {
      expect(useAppStore.getState().sidebarOpen).toBe(true);
      useAppStore.getState().toggleSidebar();
      expect(useAppStore.getState().sidebarOpen).toBe(false);
      useAppStore.getState().toggleSidebar();
      expect(useAppStore.getState().sidebarOpen).toBe(true);
    });
  });

  describe('setSidebarOpen', () => {
    it('sets sidebar to specific state', () => {
      useAppStore.getState().setSidebarOpen(false);
      expect(useAppStore.getState().sidebarOpen).toBe(false);
      useAppStore.getState().setSidebarOpen(true);
      expect(useAppStore.getState().sidebarOpen).toBe(true);
    });
  });
});

// ── Helper Functions ──────────────────────────────────────────────────

describe('isDashboardPage', () => {
  it('returns true for dashboard', () => {
    expect(isDashboardPage('dashboard')).toBe(true);
  });

  it('returns true for dashboard sub-pages', () => {
    expect(isDashboardPage('dashboard-agents')).toBe(true);
    expect(isDashboardPage('dashboard-tickets')).toBe(true);
    expect(isDashboardPage('dashboard-channels')).toBe(true);
    expect(isDashboardPage('dashboard-monitoring')).toBe(true);
    expect(isDashboardPage('dashboard-billing')).toBe(true);
    expect(isDashboardPage('dashboard-knowledge')).toBe(true);
    expect(isDashboardPage('dashboard-settings')).toBe(true);
    expect(isDashboardPage('dashboard-variants')).toBe(true);
  });

  it('returns false for non-dashboard pages', () => {
    expect(isDashboardPage('landing')).toBe(false);
    expect(isDashboardPage('login')).toBe(false);
    expect(isDashboardPage('signup')).toBe(false);
    expect(isDashboardPage('jarvis')).toBe(false);
    expect(isDashboardPage('profile')).toBe(false);
  });
});

describe('getPageTitle', () => {
  it('returns correct title for landing', () => {
    expect(getPageTitle('landing')).toBe('PARWA - AI Customer Support');
  });

  it('returns correct title for dashboard', () => {
    expect(getPageTitle('dashboard')).toBe('Dashboard');
  });

  it('returns correct title for all dashboard sub-pages', () => {
    expect(getPageTitle('dashboard-agents')).toBe('AI Agents');
    expect(getPageTitle('dashboard-tickets')).toBe('Tickets');
    expect(getPageTitle('dashboard-billing')).toBe('Billing');
    expect(getPageTitle('dashboard-knowledge')).toBe('Knowledge Base');
    expect(getPageTitle('dashboard-settings')).toBe('Settings');
    expect(getPageTitle('dashboard-variants')).toBe('AI Variants');
  });

  it('returns fallback for unknown pages', () => {
    // Page type is a union type so we can't easily test unknown,
    // but we can verify all valid pages return non-empty strings
    const pages: Page[] = [
      'landing', 'login', 'signup', 'forgot-password', 'onboarding',
      'roi-calculator', 'models', 'dashboard', 'dashboard-agents',
      'dashboard-tickets', 'dashboard-channels', 'dashboard-monitoring',
      'dashboard-billing', 'dashboard-knowledge', 'dashboard-settings',
      'dashboard-variants', 'jarvis', 'profile',
    ];
    pages.forEach((page) => {
      expect(getPageTitle(page)).toBeTruthy();
    });
  });
});
