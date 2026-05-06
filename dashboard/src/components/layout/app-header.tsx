'use client';

import { useAppStore } from '@/lib/store';
import { ThemeToggle } from './theme-toggle';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Bell, Menu, LogOut, User, Settings } from 'lucide-react';
import { mockMonitoringAlerts } from '@/lib/mock-data';

const pageTitles: Record<string, string> = {
  dashboard: 'Dashboard',
  variants: 'Variant Management',
  monitoring: 'AI Monitoring',
  tickets: 'Tickets',
  channels: 'Channels',
  billing: 'Billing',
  knowledge: 'Knowledge Base',
  jarvis: 'Jarvis Chat',
  settings: 'Settings',
};

export function AppHeader() {
  const { currentPage, user, toggleSidebar, logout, setCurrentPage } = useAppStore();
  const unacknowledgedAlerts = mockMonitoringAlerts.filter(a => !a.acknowledged).length;

  return (
    <header className="flex items-center h-16 px-4 md:px-6 border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-30">
      <Button variant="ghost" size="icon" className="md:hidden mr-2" onClick={toggleSidebar}>
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex-1 min-w-0">
        <h1 className="text-lg font-semibold truncate">{pageTitles[currentPage] || 'Dashboard'}</h1>
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle />

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative h-9 w-9" onClick={() => setCurrentPage('monitoring')}>
          <Bell className="h-4 w-4" />
          {unacknowledgedAlerts > 0 && (
            <Badge className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-[10px] bg-red-500 text-white border-0">
              {unacknowledgedAlerts}
            </Badge>
          )}
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 px-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-emerald-600 text-white text-xs">
                  {user?.name?.split(' ').map(n => n[0]).join('') || 'U'}
                </AvatarFallback>
              </Avatar>
              <span className="hidden md:inline text-sm font-medium truncate max-w-[120px]">
                {user?.name || 'User'}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => setCurrentPage('settings')}>
              <User className="mr-2 h-4 w-4" /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setCurrentPage('settings')}>
              <Settings className="mr-2 h-4 w-4" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} className="text-destructive">
              <LogOut className="mr-2 h-4 w-4" /> Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
