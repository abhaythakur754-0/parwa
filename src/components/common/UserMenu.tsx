/**
 * PARWA UserMenu Component
 *
 * Reusable profile dropdown that shows user info and account actions.
 * Used in ChatHeader, NavigationBar, and Profile page.
 *
 * Features:
 *   - User avatar + greeting ("Hi, {name}!")
 *   - Account info: email, plan, trial status
 *   - Usage stats: messages remaining, member since
 *   - Quick links: Profile, Models, Home
 *   - Account actions: Logout, Delete Account
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import {
  LogOut,
  ChevronDown,
  Mail,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';

interface UserMenuProps {
  /** Whether to show compact version (for ChatHeader) */
  compact?: boolean;
  /** Custom className for the trigger button */
  className?: string;
}

export function UserMenu({ compact = false, className = '' }: UserMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Get user from localStorage (works with Next.js API route login)
  const [userData, setUserData] = useState<{
    id?: string;
    email?: string;
    full_name?: string | null;
    is_verified?: boolean;
    company_name?: string | null;
    created_at?: string | null;
    onboarding_completed?: boolean;
  } | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_user');
      if (stored) {
        setUserData(JSON.parse(stored));
      }
    } catch {
      // ignore
    }
  }, [isOpen]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // Close on escape
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, []);

  const handleLogout = async () => {
    try {
      await fetch(`/api/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      }).catch(() => {});
    } catch {
      // ignore backend errors
    } finally {
      // Clear ALL client-side auth state immediately
      localStorage.removeItem('parwa_user');
      localStorage.removeItem('parwa_at');
      localStorage.removeItem('parwa_rt');
      sessionStorage.clear();
      toast.success('Logged out successfully!');
      // Force a full page reload to / so the server re-evaluates auth state.
      // router.push('/') alone doesn't clear server cookies from the browser —
      // a hard reload ensures the cleared cookies take effect immediately.
      window.location.href = '/';
    }
  };

  const firstName = userData?.full_name?.split(' ')[0] || 'there';
  const initials = (userData?.full_name || userData?.email || 'U').slice(0, 2).toUpperCase();

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* ── Trigger Button ── */}
      <button
        onClick={handleToggle}
        className={`flex items-center gap-2 transition-all duration-300 rounded-xl hover:bg-white/5 ${className}`}
        aria-expanded={isOpen}
        aria-haspopup="true"
      >
        {/* Avatar */}
        <div className="relative">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-xs font-bold shadow-lg shadow-orange-500/20">
            {initials}
          </div>
          <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-orange-400 border-2 border-[#1A1A1A]" />
        </div>

        {!compact && (
          <>
            <span className="text-sm text-orange-200/80 font-medium max-w-[100px] truncate">
              Hi, {firstName}!
            </span>
            <ChevronDown className={`w-3.5 h-3.5 text-orange-200/40 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`} />
          </>
        )}
      </button>

      {/* ── Dropdown ── */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-64 rounded-2xl border border-orange-500/20 bg-[#1A1A1A]/95 backdrop-blur-xl shadow-2xl shadow-black/40 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {/* ── User Header ── */}
          <div className="px-5 py-4 border-b border-white/5" style={{ background: 'linear-gradient(135deg, rgba(255,127,17,0.08) 0%, transparent 100%)' }}>
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-orange-500/20">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">
                  {userData?.full_name || 'User'}
                </p>
                <p className="text-[11px] text-orange-200/40 truncate flex items-center gap-1">
                  <Mail className="w-3 h-3" />
                  {userData?.email || 'No email'}
                </p>
              </div>
              <button onClick={() => setIsOpen(false)} className="p-1 rounded-lg hover:bg-white/5 transition-colors">
                <X className="w-4 h-4 text-white/30" />
              </button>
            </div>
          </div>

          {/* ── Logout (only option) ── */}
          <div className="py-2">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-5 py-3 text-sm text-orange-200/80 hover:text-orange-300 hover:bg-orange-500/10 transition-all duration-200"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      )}    </div>
  );
}
