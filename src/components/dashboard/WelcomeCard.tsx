/**
 * PARWA WelcomeCard (Phase 11 — Week 6 Day 7)
 *
 * Welcome message card with variant summary.
 * Shows user name, company, hired agent count, and industry.
 */

'use client';

import { Sparkles, Users, TrendingUp } from 'lucide-react';

interface WelcomeCardProps {
  userName?: string | null;
  companyName?: string | null;
  variantCount?: number;
  industry?: string | null;
}

export function WelcomeCard({
  userName,
  companyName,
  variantCount = 0,
  industry,
}: WelcomeCardProps) {
  const firstName = userName?.split(' ')[0] || 'there';
  const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1);

  return (
    <div className="glass rounded-2xl p-6 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute -top-20 -right-20 w-60 h-60 bg-orange-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative">
        {/* Greeting */}
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-orange-600/10 border border-orange-500/20 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">
              Welcome back, {displayName}!
            </h2>
            <p className="text-xs text-white/40 mt-0.5">
              {companyName || 'Your company'} &middot; {industry || 'All Industries'}
            </p>
          </div>
        </div>

        {/* Message */}
        <p className="text-sm text-white/60 leading-relaxed mb-5">
          Your Jarvis AI agents are live and ready to handle customer support.
          Here&apos;s an overview of your setup.
        </p>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <StatItem
            icon={<Users className="w-4 h-4 text-orange-400" />}
            label="Active Agents"
            value={`${variantCount}`}
          />
          <StatItem
            icon={<TrendingUp className="w-4 h-4 text-purple-400" />}
            label="Resolution Rate"
            value="0%"
          />
          <StatItem
            icon={<Sparkles className="w-4 h-4 text-amber-400" />}
            label="Status"
            value="Active"
          />
        </div>
      </div>
    </div>
  );
}

function StatItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06]">
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0">
        <p className="text-[10px] text-white/30 uppercase tracking-wider">{label}</p>
        <p className="text-sm font-semibold text-white">{value}</p>
      </div>
    </div>
  );
}
