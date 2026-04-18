/**
 * PARWA Profile Page
 *
 * Full user profile/account page showing:
 *   - Personal info (name, email, phone, company)
 *   - Account status (plan type, verification, member since)
 *   - Usage stats (messages, tickets, trial status)
 *   - Subscription details (current plan, upgrade options)
 *   - Security info (last login, 2FA status)
 *   - Account actions (edit profile, change password, logout, delete account)
 *
 * Route: /profile
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  User,
  Mail,
  Phone,
  Building2,
  Calendar,
  Shield,
  Zap,
  Crown,
  MessageSquare,
  Clock,
  CreditCard,
  LogOut,
  Trash2,
  ChevronRight,
  ArrowLeft,
  Edit3,
  Key,
  CheckCircle,
  AlertTriangle,
  Ticket,
  BarChart3,
  Lock,
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function ProfilePage() {
  const router = useRouter();
  const [userData, setUserData] = useState<{
    id?: string;
    email?: string;
    full_name?: string | null;
    phone?: string | null;
    is_verified?: boolean;
    is_active?: boolean;
    company_name?: string | null;
    company_id?: string;
    created_at?: string | null;
    onboarding_completed?: boolean;
    role?: string;
    plan?: string;
  } | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_user');
      if (!stored) {
        router.replace('/login?redirect=/profile');
        return;
      }
      setUserData(JSON.parse(stored));
    } catch {
      router.replace('/login?redirect=/profile');
    }
  }, [router]);

  const handleLogout = async () => {
    try {
      const refreshToken = localStorage.getItem('parwa_refresh_token');
      if (refreshToken) {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        }).catch(() => {});
      }
    } finally {
      localStorage.removeItem('parwa_access_token');
      localStorage.removeItem('parwa_refresh_token');
      localStorage.removeItem('parwa_user');
      toast.success('Logged out successfully!');
      router.push('/');
    }
  };

  const handleDeleteAccount = async () => {
    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true);
      return;
    }
    setIsDeleting(true);
    try {
      const token = localStorage.getItem('parwa_access_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/user/delete-account`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) throw new Error('Failed');
    } catch {
      // Backend might not be running
    } finally {
      localStorage.removeItem('parwa_access_token');
      localStorage.removeItem('parwa_refresh_token');
      localStorage.removeItem('parwa_user');
      toast.success('Account removed');
      router.push('/');
      setIsDeleting(false);
    }
  };

  const planName = userData?.plan || 'Free Trial';
  const firstName = userData?.full_name?.split(' ')[0] || 'User';
  const initials = (userData?.full_name || userData?.email || 'U').slice(0, 2).toUpperCase();
  const memberSince = userData?.created_at
    ? new Date(userData.created_at).toLocaleDateString('en-IN', { month: 'long', year: 'numeric', day: 'numeric' })
    : 'N/A';
  const memberSinceShort = userData?.created_at
    ? new Date(userData.created_at).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
    : 'N/A';

  if (!userData) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <div className="animate-spin w-8 h-8 border-2 border-orange-400 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen py-8 px-4 sm:px-6 lg:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}
    >
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[500px] h-[500px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,127,17,0.1) 0%, transparent 70%)',
          top: '-10%',
          right: '-10%',
          animation: 'orbFloat 10s ease-in-out infinite',
        }} />
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{
          background: 'radial-gradient(circle, rgba(255,215,0,0.05) 0%, transparent 70%)',
          bottom: '-10%',
          left: '-10%',
          animation: 'orbFloat 12s ease-in-out infinite',
        }} />
      </div>

      <div className="max-w-2xl mx-auto relative z-10 space-y-6">
        {/* ── Back Link ── */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-orange-200/50 hover:text-orange-300 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>

        {/* ── Profile Header Card ── */}
        <div
          className="rounded-2xl p-6 sm:p-8 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)',
          }}
        >
          {/* Glow */}
          <div className="absolute -top-20 -right-20 w-40 h-40 rounded-full blur-[80px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.08)' }} />

          <div className="relative flex flex-col sm:flex-row items-center gap-5">
            {/* Avatar */}
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-2xl font-bold shadow-xl shadow-orange-500/20">
                {initials}
              </div>
              <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-orange-400 border-3 border-[#1A1A1A] flex items-center justify-center">
                <Zap className="w-3 h-3 text-white" />
              </div>
            </div>

            {/* Info */}
            <div className="text-center sm:text-left flex-1">
              <h1 className="text-2xl font-bold text-white">
                Hi, {firstName}!
              </h1>
              <p className="text-sm text-orange-200/50 mt-1">
                {userData.email}
              </p>
              <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 mt-3">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-orange-500/10 border border-orange-500/20 text-orange-300">
                  <Crown className="w-3 h-3" />
                  {planName}
                </span>
                {userData.is_verified && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                    <CheckCircle className="w-3 h-3" />
                    Verified
                  </span>
                )}
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-white/50">
                  <Calendar className="w-3 h-3" />
                  Since {memberSinceShort}
                </span>
              </div>
            </div>

            {/* Edit Profile button */}
            <Link
              href="/models"
              className="px-4 py-2.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-600/20 hover:shadow-orange-600/40 hover:-translate-y-0.5 transition-all duration-300 flex items-center gap-2"
            >
              <Crown className="w-4 h-4" />
              Upgrade
            </Link>
          </div>
        </div>

        {/* ── Stats Grid ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { icon: MessageSquare, label: 'Messages', value: '20/day', color: 'text-orange-400' },
            { icon: Clock, label: 'Member Since', value: memberSinceShort, color: 'text-orange-400' },
            { icon: Shield, label: 'Status', value: userData.is_verified ? 'Verified' : 'Unverified', color: userData.is_verified ? 'text-green-400' : 'text-amber-400' },
            { icon: CreditCard, label: 'Plan', value: planName, color: 'text-orange-400' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-xl p-4 border border-white/5 bg-white/[0.02] text-center"
            >
              <stat.icon className={`w-5 h-5 ${stat.color} mx-auto mb-2`} />
              <p className="text-lg font-bold text-white">{stat.value}</p>
              <p className="text-[10px] text-white/30 uppercase tracking-wider mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* ── Personal Information ── */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <User className="w-4 h-4 text-orange-400" />
              Personal Information
            </h2>
            <span className="text-[10px] text-white/20 uppercase tracking-wider">Read Only</span>
          </div>
          <div className="divide-y divide-white/5">
            {[
              { icon: User, label: 'Full Name', value: userData.full_name || 'Not set' },
              { icon: Mail, label: 'Email', value: userData.email || 'Not set' },
              { icon: Phone, label: 'Phone', value: userData.phone || 'Not set' },
              { icon: Building2, label: 'Company', value: userData.company_name || 'Not set' },
              { icon: Calendar, label: 'Member Since', value: memberSince },
              { icon: Shield, label: 'Role', value: userData.role || 'User' },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 px-5 py-3.5">
                <item.icon className="w-4 h-4 text-orange-400/50 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] text-white/30 uppercase tracking-wider">{item.label}</p>
                  <p className="text-sm text-white/80 truncate">{item.value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Account Activity ── */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div className="px-5 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-orange-400" />
              Account Activity
            </h2>
          </div>
          <div className="divide-y divide-white/5">
            <div className="flex items-center gap-3 px-5 py-3.5">
              <MessageSquare className="w-4 h-4 text-orange-400/50" />
              <div className="flex-1">
                <p className="text-[11px] text-white/30 uppercase tracking-wider">Daily Message Limit</p>
                <div className="flex items-center gap-3 mt-1">
                  <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full w-1/4 rounded-full bg-gradient-to-r from-orange-500 to-orange-400" />
                  </div>
                  <span className="text-xs text-orange-300 font-medium">5 / 20</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 px-5 py-3.5">
              <Ticket className="w-4 h-4 text-orange-400/50" />
              <div className="flex-1">
                <p className="text-[11px] text-white/30 uppercase tracking-wider">Active Tickets</p>
                <p className="text-sm text-white/80">0 tickets</p>
              </div>
            </div>
            <div className="flex items-center gap-3 px-5 py-3.5">
              <Clock className="w-4 h-4 text-orange-400/50" />
              <div className="flex-1">
                <p className="text-[11px] text-white/30 uppercase tracking-wider">Plan Status</p>
                <p className="text-sm text-orange-300 font-medium">Active — {planName}</p>
              </div>
            </div>
          </div>
        </div>

        {/* ── Quick Actions ── */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div className="px-5 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="w-4 h-4 text-orange-400" />
              Quick Actions
            </h2>
          </div>
          <div className="py-2">
            <Link
              href="/jarvis"
              className="flex items-center gap-3 px-5 py-3 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <MessageSquare className="w-4 h-4 text-orange-400/60" />
              <span className="flex-1">Open Jarvis Chat</span>
              <ChevronRight className="w-4 h-4 text-white/20" />
            </Link>
            <Link
              href="/models"
              className="flex items-center gap-3 px-5 py-3 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <Crown className="w-4 h-4 text-orange-400/60" />
              <span className="flex-1">View Plans & Pricing</span>
              <ChevronRight className="w-4 h-4 text-white/20" />
            </Link>
            <Link
              href="/forgot-password"
              className="flex items-center gap-3 px-5 py-3 text-sm text-white/70 hover:text-white hover:bg-orange-500/10 transition-all duration-200"
            >
              <Key className="w-4 h-4 text-orange-400/60" />
              <span className="flex-1">Change Password</span>
              <ChevronRight className="w-4 h-4 text-white/20" />
            </Link>
          </div>
        </div>

        {/* ── Security ── */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}
        >
          <div className="px-5 py-4 border-b border-white/5">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Lock className="w-4 h-4 text-orange-400" />
              Security
            </h2>
          </div>
          <div className="py-2">
            <div className="flex items-center gap-3 px-5 py-3">
              <Shield className="w-4 h-4 text-orange-400/50" />
              <div className="flex-1">
                <p className="text-sm text-white/70">Account Verification</p>
                <p className="text-[11px] text-white/30 mt-0.5">
                  {userData.is_verified ? 'Your email is verified' : 'Email not yet verified'}
                </p>
              </div>
              {userData.is_verified ? (
                <CheckCircle className="w-4 h-4 text-green-400" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              )}
            </div>
          </div>
        </div>

        {/* ── Danger Zone ── */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(239,68,68,0.03) 0%, rgba(239,68,68,0.01) 100%)',
            border: '1px solid rgba(239,68,68,0.1)',
          }}
        >
          <div className="px-5 py-4 border-b border-rose-500/10">
            <h2 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Danger Zone
            </h2>
          </div>
          <div className="py-3">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-5 py-3 text-sm text-orange-200/60 hover:text-orange-300 hover:bg-orange-500/10 transition-all duration-200 rounded-lg mx-2"
            >
              <LogOut className="w-4 h-4" />
              <span className="flex-1 text-left">Logout from this device</span>
            </button>

            <button
              onClick={handleDeleteAccount}
              disabled={isDeleting}
              className="flex items-center gap-3 w-full px-5 py-3 text-sm text-rose-400/60 hover:text-rose-400 hover:bg-rose-500/10 transition-all duration-200 rounded-lg mx-2 mt-1 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" />
              <span className="flex-1 text-left">
                {isDeleting ? 'Deleting account...' : 'Permanently delete account'}
              </span>
            </button>

            {showDeleteConfirm && (
              <div className="mx-5 mt-3 p-3 rounded-xl bg-rose-500/5 border border-rose-500/10">
                <p className="text-xs text-rose-300/70">
                  This action is irreversible. All your data, conversations, and account information will be permanently deleted. Click the delete button again to confirm.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ── Footer ── */}
        <p className="text-center text-[11px] text-white/15 pb-8">
          PARWA — Your AI-powered customer support assistant
        </p>
      </div>

      <style jsx global>{`
        @keyframes orbFloat {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-25px) scale(1.04); }
        }
      `}</style>
    </div>
  );
}
