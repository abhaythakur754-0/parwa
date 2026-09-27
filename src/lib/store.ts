import { create } from 'zustand';

export type Page =
  | 'landing'
  | 'login'
  | 'signup'
  | 'forgot-password'
  | 'onboarding'
  | 'roi-calculator'
  | 'models'
  | 'dashboard'
  | 'dashboard-agents'
  | 'dashboard-tickets'
  | 'dashboard-channels'
  | 'dashboard-monitoring'
  | 'dashboard-billing'
  | 'dashboard-knowledge'
  | 'dashboard-settings'
  | 'dashboard-variants'
  | 'jarvis'
  | 'profile';

interface AppState {
  currentPage: Page;
  previousPage: Page | null;
  isAuthenticated: boolean;
  sidebarOpen: boolean;
  user: {
    email?: string;
    full_name?: string;
    company_name?: string;
    role?: string;
  } | null;
  navigate: (page: Page) => void;
  goBack: () => void;
  setAuth: (auth: boolean, user?: AppState['user']) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  currentPage: 'landing',
  previousPage: null,
  isAuthenticated: false,
  sidebarOpen: true,
  user: null,
  navigate: (page: Page) => {
    const { currentPage } = get();
    set({ currentPage: page, previousPage: currentPage });
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  },
  goBack: () => {
    const { previousPage } = get();
    if (previousPage) {
      set({ currentPage: previousPage, previousPage: null });
    }
  },
  setAuth: (auth: boolean, user?: AppState['user']) => {
    set({ isAuthenticated: auth, user: user ?? null });
    if (auth) {
      set({ currentPage: 'dashboard' });
    } else {
      set({ currentPage: 'landing' });
    }
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setSidebarOpen: (open: boolean) => set({ sidebarOpen: open }),
}));

// Expose store on window for debugging/testing (client-only)
if (typeof window !== 'undefined') {
  (window as unknown as Record<string, unknown>).__PARWA_STORE__ = useAppStore;
}

// Helper: check if current page is a dashboard sub-page
export function isDashboardPage(page: Page): boolean {
  return page === 'dashboard' || page.startsWith('dashboard-');
}

// Helper: get the display title for a page
export function getPageTitle(page: Page): string {
  const titles: Record<Page, string> = {
    landing: 'PARWA - AI Customer Support',
    login: 'Sign In',
    signup: 'Create Account',
    'forgot-password': 'Reset Password',
    onboarding: 'Get Started',
    'roi-calculator': 'ROI Calculator',
    models: 'AI Workforce Plans',
    dashboard: 'Dashboard',
    'dashboard-agents': 'AI Agents',
    'dashboard-tickets': 'Tickets',
    'dashboard-channels': 'Channels',
    'dashboard-monitoring': 'Monitoring',
    'dashboard-billing': 'Billing',
    'dashboard-knowledge': 'Knowledge Base',
    'dashboard-settings': 'Settings',
    'dashboard-variants': 'AI Variants',
    jarvis: 'Jarvis AI',
    profile: 'Profile',
  };
  return titles[page] || 'PARWA';
}
