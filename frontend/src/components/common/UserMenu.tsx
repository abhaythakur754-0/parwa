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
 *
 * D6-7 Fix: Replaced raw fetch() calls with useAuth() + authApi.
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import {
  User,
  LogOut,
  Trash2,
  ChevronDown,
  Mail,
  Building2,
  Calendar,
  MessageSquare,
  Shield,
  Zap,
  Crown,
  Home,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '@/contexts/AuthContext';
import { authApi, getErrorMessage } from '@/lib/api';

interface UserMenuProps {
  /** Whether to show compact version (for ChatHeader) */
  compact?: boolean;
  /** Custom className for the trigger button */
  className?: string;
}

export function UserMenu({ compact = false, className = '' }: UserMenuProps) {
  const { user, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setShowDeleteConfirm(false);
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
        setShowDeleteConfirm(false);
      }
    };
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
      toast.success('Logged out successfully!');
    } catch {
      // AuthContext.logout already handles cleanup on error
    }
  };

  const handleDeleteAccount = async () => {
    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true);
      return;
    }
    setIsDeleting(true);
    try {
      await authApi.deleteAccount();
      toast.success('Account deleted successfully');
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setIsDeleting(false);
      setIsOpen(false);
    }
  };

  const firstName = user?.full_name?.split(' ')[0] || 'there';
  const initials = (user?.full_name || user?.email || 'U').slice(0, 2).toUpperCase();
  const memberSince = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
    : 'N/A';

  const handleToggle = () => {
    setIsOpen(!isOpen);
    setShowDeleteConfirm(false);
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
        <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl border border-orange-500/20 bg-[#1A1A1A]/95 backdrop-blur-xl shadow-2xl shadow-black/40 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
          {/* ── User Header ── */}
          <div className="px-5 py-4 border-b border-white/5" style={{ background: 'linear-gradient(135deg, rgba(255,127,17,0.08) 0%, transparent 100%)' }}>
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-sm font-bold shadow-lg shadow-orange-500/20">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">
                  {user?.full_name || 'User'}
                </p>
                <p className="text-[11px] text-orange-200/40 truncate flex items-center gap-1">
                  <Mail className="w-3 h-3" />
                  {user?.email || 'No email'}
                </p>
              </div>
              <button onClick={() => setIsOpen(false)} className="p-1 rounded-lg hover:bg-white/5 transition-colors">
                <X className="w-4 h-4 text-white/30" />
              </button>
            </div>
          </div>

          {/* ── Quick Stats ── */}
          <div className="px-5 py-3 border-b border-white/5">
            <div className="grid grid-cols-2 gap-2">
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
                <Zap className="w-3.5 h-3.5 text-orange-400" />
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">Plan</p>
                  <p className="text-xs font-semibold text-orange-300">
                    {user?.onboarding_completed ? 'Active' : 'Setup'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
                <MessageSquare className="w-3.5 h-3.5 text-orange-400" />
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">Role</p>
                  <p className="text-xs font-semibold text-orange-300 capitalize">
                    {user?.role || 'Admin'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
                <Shield className="w-3.5 h-3.5 text-orange-400" />
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">Status</p>
                  <p className="text-xs font-semibold text-orange-300">
                    {user?.is_verified ? 'Verified' : 'Unverified'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/5">
                <Calendar className="w-3.5 h-3.5 text-orange-400" />
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">Since</p>
                  <p className="text-xs font-semibold text-orange-300">{memberSince}</p>
                </div>
              </div>
            </div>
          </div>

          {/* ── Company (if available) ── */}
          {user?.company_name && (
            <div className="px-5 py-2.5 border-b border-white/5">
              <div className="flex items-center gap-2 text-white/50">
                <Building2 className="w-3.5 h-3.5 text-orange-400/60" />
                <span className="text-xs">{user.company_name}</span>
              </div>
            </div>
          )}

          {/* ── Navigation Links ── */}
          <div className="py-2">
            <Link
              href="/profile"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-5 py-2.5 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <User className="w-4 h-4 text-orange-400/60" />
              <span>My Profile</span>
            </Link>
            <Link
              href="/models"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-5 py-2.5 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <Crown className="w-4 h-4 text-orange-400/60" />
              <span>Upgrade Plan</span>
            </Link>
            <Link
              href="/"
              onClick={() => setIsOpen(false)}
              className="flex items-center gap-3 px-5 py-2.5 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <Home className="w-4 h-4 text-orange-400/60" />
              <span>Home</span>
            </Link>
          </div>

          {/* ── Danger Zone ── */}
          <div className="border-t border-white/5 py-2">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-5 py-2.5 text-sm text-orange-200/60 hover:text-orange-300 hover:bg-orange-500/10 transition-all duration-200"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>

            <button
              onClick={handleDeleteAccount}
              disabled={isDeleting}
              className="flex items-center gap-3 w-full px-5 py-2.5 text-sm text-rose-400/60 hover:text-rose-400 hover:bg-rose-500/10 transition-all duration-200 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              <span>{isDeleting ? 'Deleting...' : 'Delete Account'}</span>
            </button>

            {showDeleteConfirm && (
              <div className="px-5 py-2 mt-1">
                <p className="text-[11px] text-rose-400/70 mb-2">
                  Are you sure? This will permanently delete your account and all data. Click again to confirm.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
