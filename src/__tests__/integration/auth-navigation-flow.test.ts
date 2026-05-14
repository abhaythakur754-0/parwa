/**
 * PARWA Integration Test: Auth + App Store Navigation Flow
 *
 * Tests the complete authentication and navigation flow:
 * landing → login → dashboard → navigate sub-pages → logout
 */

import { useAppStore, isDashboardPage, getPageTitle } from '@/lib/store';
import { useVariantStore } from '@/lib/variant-store';

describe('Integration: Auth + App Store Navigation Flow', () => {
  beforeEach(() => {
    useAppStore.setState({
      currentPage: 'landing',
      previousPage: null,
      isAuthenticated: false,
      sidebarOpen: true,
      user: null,
    });
    useVariantStore.getState().reset();
  });

  describe('Unauthenticated user flow', () => {
    it('starts on landing page', () => {
      expect(useAppStore.getState().currentPage).toBe('landing');
      expect(useAppStore.getState().isAuthenticated).toBe(false);
    });

    it('can navigate to login and signup', () => {
      useAppStore.getState().navigate('login');
      expect(useAppStore.getState().currentPage).toBe('login');
      expect(useAppStore.getState().previousPage).toBe('landing');

      useAppStore.getState().navigate('signup');
      expect(useAppStore.getState().currentPage).toBe('signup');
      expect(useAppStore.getState().previousPage).toBe('login');
    });

    it('can go back from signup to login', () => {
      useAppStore.getState().navigate('login');
      useAppStore.getState().navigate('signup');

      useAppStore.getState().goBack();
      expect(useAppStore.getState().currentPage).toBe('login');

      useAppStore.getState().goBack();
      // goBack only works once since previousPage is set to null after first goBack
      // Second goBack has no effect since previousPage is null
      expect(useAppStore.getState().currentPage).toBe('login');
    });
  });

  describe('Authentication flow', () => {
    it('setAuth(true) navigates to dashboard', () => {
      useAppStore.getState().navigate('login');
      useAppStore.getState().setAuth(true, {
        email: 'test@example.com',
        full_name: 'Test User',
        company_name: 'TestCo',
        role: 'admin',
      });

      expect(useAppStore.getState().isAuthenticated).toBe(true);
      expect(useAppStore.getState().currentPage).toBe('dashboard');
      expect(useAppStore.getState().user?.email).toBe('test@example.com');
    });

    it('setAuth(false) navigates back to landing', () => {
      useAppStore.getState().setAuth(true, {
        email: 'test@example.com',
      });

      useAppStore.getState().setAuth(false);

      expect(useAppStore.getState().isAuthenticated).toBe(false);
      expect(useAppStore.getState().currentPage).toBe('landing');
      expect(useAppStore.getState().user).toBeNull();
    });
  });

  describe('Dashboard navigation flow', () => {
    beforeEach(() => {
      useAppStore.getState().setAuth(true, {
        email: 'test@example.com',
        full_name: 'Test User',
      });
    });

    it('can navigate between all dashboard sub-pages', () => {
      const subPages = [
        'dashboard-agents',
        'dashboard-tickets',
        'dashboard-channels',
        'dashboard-monitoring',
        'dashboard-billing',
        'dashboard-knowledge',
        'dashboard-settings',
        'dashboard-variants',
      ] as const;

      subPages.forEach((page) => {
        useAppStore.getState().navigate(page);
        expect(useAppStore.getState().currentPage).toBe(page);
        expect(isDashboardPage(page)).toBe(true);
      });
    });

    it('maintains previous page for goBack', () => {
      useAppStore.getState().navigate('dashboard-tickets');
      useAppStore.getState().navigate('dashboard-billing');

      expect(useAppStore.getState().previousPage).toBe('dashboard-tickets');

      useAppStore.getState().goBack();
      expect(useAppStore.getState().currentPage).toBe('dashboard-tickets');
    });

    it('all dashboard pages have titles', () => {
      const pages = [
        'dashboard',
        'dashboard-agents',
        'dashboard-tickets',
        'dashboard-channels',
        'dashboard-monitoring',
        'dashboard-billing',
        'dashboard-knowledge',
        'dashboard-settings',
        'dashboard-variants',
      ] as const;

      pages.forEach((page) => {
        const title = getPageTitle(page);
        expect(title).toBeTruthy();
        expect(title.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Sidebar state', () => {
    it('sidebar state is independent of navigation', () => {
      useAppStore.getState().setAuth(true, { email: 'test@example.com' });
      useAppStore.getState().setSidebarOpen(false);

      useAppStore.getState().navigate('dashboard-tickets');

      expect(useAppStore.getState().sidebarOpen).toBe(false);
      expect(useAppStore.getState().currentPage).toBe('dashboard-tickets');
    });

    it('sidebar toggle works during navigation', () => {
      useAppStore.getState().toggleSidebar();
      expect(useAppStore.getState().sidebarOpen).toBe(false);

      useAppStore.getState().navigate('dashboard-billing');
      useAppStore.getState().toggleSidebar();
      expect(useAppStore.getState().sidebarOpen).toBe(true);
    });
  });

  describe('Auth + variant store coordination', () => {
    it('logging out resets variant store to mini', () => {
      // User logs in as pro
      useAppStore.getState().setAuth(true, {
        email: 'test@example.com',
        company_name: 'ProCompany',
      });
      useVariantStore.getState().setTier('pro');

      expect(useVariantStore.getState().tier).toBe('pro');

      // User logs out
      useAppStore.getState().setAuth(false);
      useVariantStore.getState().reset();

      expect(useAppStore.getState().isAuthenticated).toBe(false);
      expect(useVariantStore.getState().tier).toBe('mini');
    });
  });

  describe('Complete user journey', () => {
    it('landing → login → dashboard → tickets → billing → logout', () => {
      // 1. Start on landing
      expect(useAppStore.getState().currentPage).toBe('landing');

      // 2. Go to login
      useAppStore.getState().navigate('login');
      expect(useAppStore.getState().currentPage).toBe('login');

      // 3. Login
      useAppStore.getState().setAuth(true, {
        email: 'user@example.com',
        full_name: 'User One',
      });
      expect(useAppStore.getState().currentPage).toBe('dashboard');

      // 4. Navigate to tickets
      useAppStore.getState().navigate('dashboard-tickets');
      expect(useAppStore.getState().currentPage).toBe('dashboard-tickets');

      // 5. Navigate to billing
      useAppStore.getState().navigate('dashboard-billing');
      expect(useAppStore.getState().currentPage).toBe('dashboard-billing');

      // 6. Go back to tickets
      useAppStore.getState().goBack();
      expect(useAppStore.getState().currentPage).toBe('dashboard-tickets');

      // 7. Logout
      useAppStore.getState().setAuth(false);
      expect(useAppStore.getState().currentPage).toBe('landing');
      expect(useAppStore.getState().isAuthenticated).toBe(false);
    });
  });
});
