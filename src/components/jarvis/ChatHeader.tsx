/**
 * PARWA ChatHeader Component
 *
 * Header bar for the Jarvis chat interface.
 * Auth-aware: shows user greeting + profile dropdown when logged in,
 * or "Log in" / "Sign up" links when not logged in.
 * Includes a home link for easy navigation back to the main site.
 */

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Bot, Zap, ArrowLeft } from 'lucide-react';
import { UserMenu } from '@/components/common/UserMenu';

interface ChatHeaderProps {
  /** Active Jarvis session (null before init completes) */
  session?: {
    detected_stage?: string;
    remaining_today?: number;
    pack_type?: string;
  } | null;
  /** Whether the session is currently loading */
  isLoading?: boolean;
}

/** Stage display labels mapped from backend enum values */
const STAGE_LABELS: Record<string, string> = {
  welcome: 'Getting Started',
  discovery: 'Understanding Needs',
  demo: 'Demo',
  pricing: 'Pricing',
  bill_review: 'Bill Review',
  verification: 'Verification',
  payment: 'Payment',
  handoff: 'Handoff',
};

export function ChatHeader({ session, isLoading }: ChatHeaderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Initialize and listen for storage changes (login/logout) after mount
  useEffect(() => {
    const checkAuth = () => {
      try {
        setIsAuthenticated(!!localStorage.getItem('parwa_user'));
      } catch {
        setIsAuthenticated(false);
      }
    };
    
    checkAuth();
    window.addEventListener('storage', checkAuth);
    return () => window.removeEventListener('storage', checkAuth);
  }, []);

  const stageLabel = session?.detected_stage
    ? STAGE_LABELS[session.detected_stage] || session.detected_stage
    : null;

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#1A1A1A] backdrop-blur-md shrink-0" role="banner">
      {/* Left — Back link + Avatar + Title */}
      <div className="flex items-center gap-3">
        {/* Back to Home link */}
        <Link
          href="/"
          className="flex items-center gap-1.5 text-orange-300/60 hover:text-orange-300 transition-all duration-200 group"
          title="Back to Home"
        >
          <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-1" />
          <span className="text-xs font-medium hidden sm:inline">Back</span>
        </Link>

        <div className="w-px h-6 bg-white/10" />

        {/* Bot Avatar */}
        <div className="relative">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          {/* Online indicator dot */}
          <div
            className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-[#1A1A1A] ${
              isLoading
                ? 'bg-amber-400 animate-pulse'
                : 'bg-orange-400 animate-pulse'
            }`}
          />
        </div>

        <div className="flex flex-col">
          <h1 className="text-sm font-semibold text-white tracking-tight">
            Jarvis — Your AI Assistant
          </h1>
          <p className="text-[11px] text-orange-400/60 flex items-center gap-1">
            <Zap className="w-3 h-3" />
            {isLoading ? 'Connecting...' : 'Online • Ready to help'}
          </p>
        </div>
      </div>

      {/* Right — Auth section + Stage badge + remaining count */}
      <div className="flex items-center gap-2">
        {isAuthenticated ? (
          <UserMenu compact={true} />
        ) : (
          <>
            <Link
              href="/login"
              className="text-[11px] text-orange-400/70 hover:text-orange-400 transition-colors"
            >
              Log in
            </Link>
            <Link
              href="/signup"
              className="text-[11px] text-orange-400/70 hover:text-orange-400 border border-orange-400/20 rounded-full px-2.5 py-0.5 hover:border-orange-400/40 transition-all"
            >
              Sign up
            </Link>
          </>
        )}

        {stageLabel && (
          <span className="hidden sm:inline-flex border border-orange-500/20 text-orange-300/80 text-[11px] font-normal px-2 py-0.5 bg-orange-500/5 rounded-full">
            {stageLabel}
          </span>
        )}

        {!isLoading && session && (
          <span
            className={`text-[11px] font-normal px-2 py-0.5 rounded-full border ${
              session.pack_type === 'demo'
                ? 'border-amber-500/30 text-amber-300 bg-amber-500/5'
                : session.remaining_today !== undefined && session.remaining_today <= 5
                  ? 'border-red-500/30 text-red-300 bg-red-500/5'
                  : 'border-orange-500/30 text-orange-300 bg-orange-500/5'
            }`}
          >
            {session.remaining_today ?? '...'} msg left
          </span>
        )}
      </div>
    </header>
  );
}
