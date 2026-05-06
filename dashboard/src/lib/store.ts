// ============================================================
// Parwa Variant Engine Dashboard - Zustand Store
// ============================================================

import { create } from 'zustand';
import type { PageId, User, VariantType, TicketStatus, ChannelType } from './types';

interface AppState {
  // Navigation
  currentPage: PageId;
  setCurrentPage: (page: PageId) => void;

  // Auth
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string, company: string) => Promise<void>;
  logout: () => void;
  loginWithGoogle: () => Promise<void>;

  // Sidebar
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  // Ticket Filters
  ticketFilters: {
    status: TicketStatus | 'all';
    variant: VariantType | 'all';
    channel: ChannelType | 'all';
    priority: string | 'all';
    search: string;
  };
  setTicketFilter: (key: string, value: string) => void;
  resetTicketFilters: () => void;

  // Selected Ticket
  selectedTicketId: string | null;
  setSelectedTicketId: (id: string | null) => void;

  // Chat State
  chatSessionId: string | null;
  chatVariant: VariantType;
  setChatVariant: (v: VariantType) => void;
  startNewChat: () => void;

  // Settings Tab
  settingsTab: string;
  setSettingsTab: (tab: string) => void;

  // Variant Tab
  variantTab: string;
  setVariantTab: (tab: string) => void;

  // Monitoring Tab
  monitoringTab: string;
  setMonitoringTab: (tab: string) => void;

  // Channel Tab
  channelTab: string;
  setChannelTab: (tab: string) => void;

  // Billing Tab
  billingTab: string;
  setBillingTab: (tab: string) => void;
}

const defaultTicketFilters = {
  status: 'all' as const,
  variant: 'all' as const,
  channel: 'all' as const,
  priority: 'all' as const,
  search: '',
};

export const useAppStore = create<AppState>((set, get) => ({
  // Navigation
  currentPage: 'auth',
  setCurrentPage: (page) => set({ currentPage: page }),

  // Auth
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: async (email: string, _password: string) => {
    set({ isLoading: true });
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 800));
    const mockUser: User = {
      id: 'usr_001',
      email,
      name: 'Sarah Chen',
      role: 'admin',
      companyId: 'comp_001',
      companyName: 'Parwa Corp',
      mfaEnabled: true,
      createdAt: '2024-01-15T10:00:00Z',
    };
    set({ user: mockUser, isAuthenticated: true, isLoading: false, currentPage: 'dashboard' });
  },
  signup: async (name: string, email: string, _password: string, company: string) => {
    set({ isLoading: true });
    await new Promise(resolve => setTimeout(resolve, 800));
    const mockUser: User = {
      id: 'usr_002',
      email,
      name,
      role: 'admin',
      companyId: 'comp_002',
      companyName: company,
      mfaEnabled: false,
      createdAt: new Date().toISOString(),
    };
    set({ user: mockUser, isAuthenticated: true, isLoading: false, currentPage: 'dashboard' });
  },
  logout: () => set({ user: null, isAuthenticated: false, currentPage: 'auth' }),
  loginWithGoogle: async () => {
    set({ isLoading: true });
    await new Promise(resolve => setTimeout(resolve, 1000));
    const mockUser: User = {
      id: 'usr_003',
      email: 'sarah.chen@gmail.com',
      name: 'Sarah Chen',
      role: 'admin',
      companyId: 'comp_001',
      companyName: 'Parwa Corp',
      mfaEnabled: true,
      createdAt: '2024-01-15T10:00:00Z',
    };
    set({ user: mockUser, isAuthenticated: true, isLoading: false, currentPage: 'dashboard' });
  },

  // Sidebar
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  // Ticket Filters
  ticketFilters: { ...defaultTicketFilters },
  setTicketFilter: (key, value) =>
    set((s) => ({ ticketFilters: { ...s.ticketFilters, [key]: value } })),
  resetTicketFilters: () => set({ ticketFilters: { ...defaultTicketFilters } }),

  // Selected Ticket
  selectedTicketId: null,
  setSelectedTicketId: (id) => set({ selectedTicketId: id }),

  // Chat State
  chatSessionId: null,
  chatVariant: 'parwa',
  setChatVariant: (v) => set({ chatVariant: v }),
  startNewChat: () => set({ chatSessionId: `cs_${Date.now()}`, }),

  // Settings Tab
  settingsTab: 'profile',
  setSettingsTab: (tab) => set({ settingsTab: tab }),

  // Variant Tab
  variantTab: 'instances',
  setVariantTab: (tab) => set({ variantTab: tab }),

  // Monitoring Tab
  monitoringTab: 'router',
  setMonitoringTab: (tab) => set({ monitoringTab: tab }),

  // Channel Tab
  channelTab: 'chat',
  setChannelTab: (tab) => set({ channelTab: tab }),

  // Billing Tab
  billingTab: 'subscription',
  setBillingTab: (tab) => set({ billingTab: tab }),
}));
