'use client';

import { useAppStore } from '@/lib/store';
import type { PageId } from '@/lib/types';
import {
  LayoutDashboard, Cpu, Activity, TicketCheck, Radio,
  CreditCard, BookOpen, MessageCircle, Settings, LogOut,
  ChevronLeft, ChevronRight, Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

const navItems: { id: PageId; label: string; icon: React.ElementType; section?: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'variants', label: 'Variants', icon: Cpu },
  { id: 'monitoring', label: 'AI Monitoring', icon: Activity },
  { id: 'tickets', label: 'Tickets', icon: TicketCheck },
  { id: 'channels', label: 'Channels', icon: Radio },
  { id: 'billing', label: 'Billing', icon: CreditCard },
  { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
  { id: 'jarvis', label: 'Jarvis Chat', icon: MessageCircle },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export function AppSidebar() {
  const { currentPage, setCurrentPage, sidebarOpen, toggleSidebar, logout } = useAppStore();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'flex flex-col border-r border-border bg-card transition-all duration-300 ease-in-out h-full',
          sidebarOpen ? 'w-64' : 'w-16'
        )}
      >
        {/* Logo */}
        <div className="flex items-center h-16 px-4 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white flex-shrink-0">
              <Zap className="h-4 w-4" />
            </div>
            {sidebarOpen && (
              <span className="font-bold text-lg truncate">Parwa</span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-2">
          <nav className="flex flex-col gap-1 px-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPage === item.id;
              const btn = (
                <button
                  key={item.id}
                  onClick={() => setCurrentPage(item.id)}
                  className={cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors w-full',
                    'hover:bg-accent hover:text-accent-foreground',
                    isActive
                      ? 'bg-emerald-600/10 text-emerald-600 dark:text-emerald-400 dark:bg-emerald-400/10'
                      : 'text-muted-foreground',
                    !sidebarOpen && 'justify-center px-2'
                  )}
                >
                  <Icon className={cn('h-4 w-4 flex-shrink-0', isActive && 'text-emerald-600 dark:text-emerald-400')} />
                  {sidebarOpen && <span className="truncate">{item.label}</span>}
                </button>
              );

              if (!sidebarOpen) {
                return (
                  <Tooltip key={item.id}>
                    <TooltipTrigger asChild>{btn}</TooltipTrigger>
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  </Tooltip>
                );
              }
              return btn;
            })}
          </nav>
        </ScrollArea>

        {/* Bottom Section */}
        <div className="border-t border-border p-2">
          {sidebarOpen && (
            <div className="mb-2 px-3 py-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30">
              <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400">Growth Plan</p>
              <p className="text-xs text-muted-foreground mt-0.5">6 active variants</p>
            </div>
          )}
          <div className="flex flex-col gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size={sidebarOpen ? 'default' : 'icon'}
                  onClick={logout}
                  className={cn(
                    'text-muted-foreground hover:text-destructive',
                    !sidebarOpen && 'justify-center w-full'
                  )}
                >
                  <LogOut className="h-4 w-4 flex-shrink-0" />
                  {sidebarOpen && <span className="ml-2">Logout</span>}
                </Button>
              </TooltipTrigger>
              {!sidebarOpen && <TooltipContent side="right">Logout</TooltipContent>}
            </Tooltip>
            <Separator className="my-1" />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={toggleSidebar}
                  className="w-full text-muted-foreground"
                >
                  {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </Button>
              </TooltipTrigger>
              {!sidebarOpen && <TooltipContent side="right">Expand</TooltipContent>}
            </Tooltip>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}
