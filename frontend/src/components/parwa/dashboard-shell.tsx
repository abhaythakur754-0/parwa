'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Separator } from '@/components/ui/separator';
import {
  Home, Zap, CreditCard, Link2, BookOpen, Bell, Settings,
  Menu, ChevronRight, Sparkles, LogOut, User,
  Ticket, Phone, Activity,
} from 'lucide-react';
import { type VariantType, getNotifications } from '@/lib/api';
import { useAuth } from '@/components/providers/auth-provider';
import DashboardHome from './dashboard-home';
import VariantSelection from './variant-selection';
import VariantControl from './variant-control';
import TicketsPage from './tickets-page';
import CallsPage from './calls-page';
import PaymentBilling from './payment-billing';
import Integrations from './integrations';
import Notifications from './notifications';
import KnowledgeBase from './knowledge-base';
import SettingsPage from './settings';
import OnboardingFlow from './onboarding-flow';

type TabId = 'home' | 'tickets' | 'variants' | 'calls' | 'billing' | 'integrations' | 'knowledge' | 'notifications' | 'settings';

interface NavItem {
  id: TabId;
  label: string;
  icon: React.ElementType;
}

const navItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'tickets', label: 'Tickets', icon: Ticket },
  { id: 'variants', label: 'Variants', icon: Activity },
  { id: 'calls', label: 'Calls', icon: Phone },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'integrations', label: 'Integrations', icon: Link2 },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'settings', label: 'Settings', icon: Settings },
];

// Sidebar content extracted as a separate component to avoid render-time creation
function SidebarContent({
  activeTab,
  activeVariants,
  unreadCount,
  userName,
  companyName,
  onNavigate,
  onLogout,
}: {
  activeTab: TabId;
  activeVariants: VariantType[];
  unreadCount: number;
  userName?: string;
  companyName?: string;
  onNavigate: (tab: TabId) => void;
  onLogout: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] flex items-center justify-center shadow-lg">
          <Sparkles className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="font-bold text-lg text-white leading-tight">PARWA</h1>
          <p className="text-xs text-white/50">AI Support Platform</p>
        </div>
      </div>

      <Separator className="bg-white/10" />

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-[#D4AF37] text-[#1A1A1A] shadow-md'
                  : 'text-white/70 hover:bg-white/10 hover:text-white'
              }`}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-left">{item.label}</span>
              {item.id === 'notifications' && unreadCount > 0 && (
                <Badge className="bg-red-500 text-white text-xs px-1.5 py-0 min-w-[20px] flex items-center justify-center">
                  {unreadCount}
                </Badge>
              )}
              {item.id === 'variants' && activeVariants.length > 0 && (
                <Badge className="bg-[#D4AF37]/20 text-[#D4AF37] text-xs px-1.5 py-0">
                  {activeVariants.length}
                </Badge>
              )}
              {isActive && <ChevronRight className="h-4 w-4 text-[#D4AF37]" />}
            </button>
          );
        })}
      </nav>

      <Separator className="bg-white/10" />

      {/* Active Variant Badge */}
      <div className="p-3">
        {activeVariants.length > 0 ? (
          <div className="p-3 rounded-lg bg-white/5 border border-white/10">
            <p className="text-xs text-white/50 mb-1">Active Plan</p>
            <p className="text-sm font-medium text-[#D4AF37]">
              {activeVariants.includes('high') ? 'PARWA High' :
               activeVariants.includes('parwa') ? 'PARWA Standard' :
               'PARWA Mini'}
            </p>
          </div>
        ) : (
          <Button
            onClick={() => onNavigate('variants')}
            className="w-full bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] text-sm"
            size="sm"
          >
            <Zap className="h-3.5 w-3.5 mr-1.5" />
            Choose a Plan
          </Button>
        )}
      </div>

      <Separator className="bg-white/10" />

      {/* User Info + Logout */}
      <div className="p-3">
        <div className="p-3 rounded-lg bg-white/5 border border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-[#D4AF37] flex items-center justify-center text-[#1A1A1A] text-xs font-bold shrink-0">
              {userName ? userName.charAt(0).toUpperCase() : 'U'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-white truncate">{userName || 'User'}</p>
              <p className="text-xs text-white/50 truncate">{companyName || 'Company'}</p>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}

export default function DashboardShell() {
  const { user, isAuthenticated, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>('home');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeVariants, setActiveVariants] = useState<VariantType[]>([]);
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const initializedRef = useRef(false);

  // Sync user subscription_variant into activeVariants
  useEffect(() => {
    if (user?.subscription_variant) {
      setActiveVariants(prev => {
        if (!prev.includes(user.subscription_variant as VariantType)) {
          return [...prev, user.subscription_variant as VariantType];
        }
        return prev;
      });
    }
  }, [user?.subscription_variant]);

  // Check if we should show onboarding — use lazy init pattern
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const hasVisited = localStorage.getItem('parwa-visited');
    const savedVariants = localStorage.getItem('parwa-variants');

    queueMicrotask(() => {
      if (savedVariants) {
        try {
          setActiveVariants(JSON.parse(savedVariants));
        } catch { /* ignore parse errors */ }
      }
      if (!hasVisited) {
        setOnboardingOpen(true);
      }
    });
  }, []);

  // Load unread notification count
  useEffect(() => {
    let cancelled = false;
    async function loadUnread() {
      const notifs = await getNotifications().catch(() => []);
      if (!cancelled) {
        setUnreadCount(notifs.filter(n => !n.read).length);
      }
    }
    loadUnread();
    return () => { cancelled = true; };
  }, [activeTab]);

  // Save variants to localStorage
  useEffect(() => {
    localStorage.setItem('parwa-variants', JSON.stringify(activeVariants));
  }, [activeVariants]);

  const handleNavigate = useCallback((tab: string) => {
    setActiveTab(tab as TabId);
    setSidebarOpen(false);
  }, []);

  const handleVariantChange = useCallback((variants: VariantType[]) => {
    setActiveVariants(variants);
  }, []);

  const handleOnboardingComplete = useCallback(() => {
    localStorage.setItem('parwa-visited', 'true');
    setOnboardingOpen(false);
  }, []);

  const handleOnboardingVariant = useCallback((variant: VariantType) => {
    setActiveVariants(prev => {
      if (prev.includes(variant)) return prev;
      return [...prev, variant];
    });
  }, []);

  const userName = user?.name;
  const companyName = user?.company_name;

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <DashboardHome activeVariants={activeVariants} onNavigate={handleNavigate} />;
      case 'tickets':
        return <TicketsPage activeVariants={activeVariants} />;
      case 'variants':
        return <VariantSelection activeVariants={activeVariants} onVariantChange={handleVariantChange} />;
      case 'calls':
        return <CallsPage />;
      case 'billing':
        return <PaymentBilling activeVariants={activeVariants} />;
      case 'integrations':
        return <Integrations activeVariants={activeVariants} />;
      case 'knowledge':
        return <KnowledgeBase />;
      case 'notifications':
        return <Notifications />;
      case 'settings':
        return <SettingsPage />;
      default:
        return <DashboardHome activeVariants={activeVariants} onNavigate={handleNavigate} />;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 bg-[#0A3D2E] text-white flex-col shrink-0">
        <SidebarContent
          activeTab={activeTab}
          activeVariants={activeVariants}
          unreadCount={unreadCount}
          userName={userName}
          companyName={companyName}
          onNavigate={handleNavigate}
          onLogout={logout}
        />
      </aside>

      {/* Mobile Sidebar */}
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="p-0 w-64 bg-[#0A3D2E] text-white border-white/10">
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
          </SheetHeader>
          <SidebarContent
            activeTab={activeTab}
            activeVariants={activeVariants}
            unreadCount={unreadCount}
            userName={userName}
            companyName={companyName}
            onNavigate={handleNavigate}
            onLogout={logout}
          />
        </SheetContent>
      </Sheet>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-3">
            {/* Mobile menu button */}
            <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
            </Sheet>
            <div className="flex items-center gap-2">
              <div className="md:hidden w-7 h-7 rounded-md bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] flex items-center justify-center">
                <Sparkles className="h-4 w-4 text-white" />
              </div>
              <h2 className="font-semibold text-sm sm:text-base">
                {navItems.find(i => i.id === activeTab)?.label || 'Dashboard'}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {activeVariants.length === 0 && (
              <Button
                onClick={() => handleNavigate('variants')}
                size="sm"
                className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] text-xs hidden sm:flex"
              >
                <Zap className="h-3.5 w-3.5 mr-1" />
                Get Started
              </Button>
            )}
            <button
              onClick={() => handleNavigate('notifications')}
              className="relative p-2 rounded-lg hover:bg-muted transition-colors"
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-bold">
                  {unreadCount}
                </span>
              )}
            </button>
            {/* User avatar in header */}
            <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-border">
              <div className="w-7 h-7 rounded-full bg-[#0A3D2E] flex items-center justify-center text-white text-xs font-bold">
                {userName ? userName.charAt(0).toUpperCase() : 'U'}
              </div>
              <span className="text-xs text-muted-foreground max-w-[100px] truncate">{userName || 'User'}</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="p-4 sm:p-6 lg:p-8"
            >
              {renderContent()}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Onboarding Flow */}
      <OnboardingFlow
        open={onboardingOpen}
        onComplete={handleOnboardingComplete}
        onVariantSelected={handleOnboardingVariant}
      />
    </div>
  );
}
