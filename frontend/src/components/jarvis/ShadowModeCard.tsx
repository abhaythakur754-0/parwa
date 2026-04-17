/**
 * PARWA ShadowModeCard (Day 6 — Jarvis Commands & Dual Control)
 *
 * Visual card for Jarvis chat showing current shadow mode status.
 * Allows quick actions: view approvals, change mode, see pending count.
 *
 * Features:
 *   - Current mode badge with color indicator
 *   - Pending approvals count
 *   - Quick action buttons
 *   - Last action summary
 *   - Real-time sync with dashboard settings
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { 
  ShieldCheck, 
  Eye, 
  CheckCircle, 
  Clock, 
  ChevronRight,
  AlertTriangle,
  ArrowRight,
  Settings,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { shadowApi, type SystemMode, type ShadowStats } from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';

// ── Types ──────────────────────────────────────────────────────────────

interface ShadowModeCardProps {
  /** Compact mode for sidebar */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Called when mode changes */
  onModeChange?: (mode: SystemMode) => void;
}

interface ModeConfig {
  icon: React.ReactNode;
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

// ── Mode Configuration ──────────────────────────────────────────────────

const MODE_CONFIG: Record<SystemMode, ModeConfig> = {
  shadow: {
    icon: <Eye className="w-4 h-4" />,
    label: 'Shadow Mode',
    description: 'All actions require your approval',
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/15',
    borderColor: 'border-orange-500/30',
  },
  supervised: {
    icon: <ShieldCheck className="w-4 h-4" />,
    label: 'Supervised',
    description: 'High-risk actions need approval',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/15',
    borderColor: 'border-blue-500/30',
  },
  graduated: {
    icon: <CheckCircle className="w-4 h-4" />,
    label: 'Graduated',
    description: 'Auto-execute with undo available',
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/15',
    borderColor: 'border-emerald-500/30',
  },
};

// ── Component ───────────────────────────────────────────────────────────

export function ShadowModeCard({ 
  compact = false, 
  className,
  onModeChange,
}: ShadowModeCardProps) {
  const router = useRouter();
  const { socket } = useSocket();
  
  // State
  const [mode, setMode] = useState<SystemMode | null>(null);
  const [stats, setStats] = useState<ShadowStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [switchingMode, setSwitchingMode] = useState(false);

  // Fetch data
  const fetchData = useCallback(async () => {
    try {
      const [modeRes, statsRes] = await Promise.all([
        shadowApi.getMode(),
        shadowApi.getStats(),
      ]);
      setMode(modeRes.mode);
      setStats(statsRes);
    } catch (err) {
      console.error('[ShadowModeCard] Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WebSocket real-time updates
  useEffect(() => {
    if (!socket) return;

    const handleModeChange = (data: { mode: SystemMode }) => {
      setMode(data.mode);
      onModeChange?.(data.mode);
    };

    const handleStatsUpdate = () => {
      shadowApi.getStats().then(setStats).catch(() => {});
    };

    socket.on('shadow:mode_changed', handleModeChange);
    socket.on('shadow:action_resolved', handleStatsUpdate);
    socket.on('shadow:action_undone', handleStatsUpdate);
    socket.on('shadow:new', handleStatsUpdate);

    return () => {
      socket.off('shadow:mode_changed', handleModeChange);
      socket.off('shadow:action_resolved', handleStatsUpdate);
      socket.off('shadow:action_undone', handleStatsUpdate);
      socket.off('shadow:new', handleStatsUpdate);
    };
  }, [socket, onModeChange]);

  // Quick mode cycle (shadow → supervised → graduated → shadow)
  const cycleMode = async () => {
    if (!mode || switchingMode) return;
    
    const modeOrder: SystemMode[] = ['shadow', 'supervised', 'graduated'];
    const currentIndex = modeOrder.indexOf(mode);
    const nextMode = modeOrder[(currentIndex + 1) % modeOrder.length];
    
    setSwitchingMode(true);
    try {
      await shadowApi.setMode(nextMode, 'jarvis');
      setMode(nextMode);
      onModeChange?.(nextMode);
    } catch (err) {
      console.error('[ShadowModeCard] Failed to switch mode:', err);
    } finally {
      setSwitchingMode(false);
    }
  };

  // Navigation
  const goToApprovals = () => router.push('/dashboard/approvals');
  const goToSettings = () => router.push('/dashboard/settings/shadow-mode');

  // Get current mode config
  const config = mode ? MODE_CONFIG[mode] : null;
  const pendingCount = stats?.pending_count ?? 0;
  const approvalRate = stats?.approval_rate ? (stats.approval_rate * 100).toFixed(0) : '0';

  // Loading state
  if (loading) {
    return (
      <div className={cn(
        'glass rounded-xl p-3 border border-white/[0.06] max-w-sm w-full',
        className
      )}>
        <div className="flex items-center gap-2">
          <Loader2 className="w-4 h-4 text-white/40 animate-spin" />
          <span className="text-xs text-white/40">Loading shadow mode...</span>
        </div>
      </div>
    );
  }

  // Compact mode (for sidebar widgets)
  if (compact) {
    return (
      <div 
        onClick={goToApprovals}
        className={cn(
          'glass rounded-xl p-3 border cursor-pointer hover:bg-white/[0.02] transition-all',
          config?.borderColor || 'border-white/[0.06]',
          className
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn('p-1.5 rounded-lg', config?.bgColor)}>
              {config?.icon && <span className={config.color}>{config.icon}</span>}
            </div>
            <div>
              <p className={cn('text-xs font-medium', config?.color || 'text-white/70')}>
                {config?.label || 'Unknown'}
              </p>
              <p className="text-[10px] text-white/40">
                {pendingCount > 0 ? `${pendingCount} pending` : 'All clear'}
              </p>
            </div>
          </div>
          {pendingCount > 0 && (
            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-orange-500/20 text-orange-400 text-[10px] font-bold">
              {pendingCount}
            </span>
          )}
        </div>
      </div>
    );
  }

  // Full mode
  return (
    <div className={cn(
      'glass rounded-xl border max-w-sm w-full overflow-hidden',
      config?.borderColor || 'border-white/[0.06]',
      className
    )}>
      {/* Header */}
      <div className={cn('p-3 border-b border-white/[0.06]', config?.bgColor)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn('p-1.5 rounded-lg bg-black/20')}>
              {config?.icon && <span className={config.color}>{config.icon}</span>}
            </div>
            <div>
              <p className={cn('text-sm font-semibold', config?.color)}>
                {config?.label || 'Unknown Mode'}
              </p>
              <p className="text-[10px] text-white/50">
                {config?.description}
              </p>
            </div>
          </div>
          
          {/* Cycle Mode Button */}
          <button
            onClick={cycleMode}
            disabled={switchingMode}
            className={cn(
              'p-1.5 rounded-lg border transition-all',
              'border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.08]',
              switchingMode && 'opacity-50 cursor-not-allowed'
            )}
            title="Cycle mode"
          >
            {switchingMode ? (
              <Loader2 className="w-3.5 h-3.5 text-white/40 animate-spin" />
            ) : (
              <ArrowRight className="w-3.5 h-3.5 text-white/60" />
            )}
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="p-3 grid grid-cols-3 gap-2 border-b border-white/[0.06]">
        <div className="text-center">
          <p className="text-lg font-semibold text-white">
            {pendingCount}
          </p>
          <p className="text-[10px] text-white/40">Pending</p>
        </div>
        <div className="text-center border-x border-white/[0.06]">
          <p className={cn(
            'text-lg font-semibold',
            parseFloat(approvalRate) >= 80 ? 'text-emerald-400' :
            parseFloat(approvalRate) >= 50 ? 'text-yellow-400' : 'text-red-400'
          )}>
            {approvalRate}%
          </p>
          <p className="text-[10px] text-white/40">Approved</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold text-white">
            {stats?.total_actions ?? 0}
          </p>
          <p className="text-[10px] text-white/40">Total</p>
        </div>
      </div>

      {/* Pending Alert */}
      {pendingCount > 0 && (
        <div 
          onClick={goToApprovals}
          className="p-2.5 flex items-center justify-between bg-orange-500/10 border-b border-orange-500/20 cursor-pointer hover:bg-orange-500/15 transition-all"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-xs text-orange-300">
              {pendingCount} action{pendingCount > 1 ? 's' : ''} awaiting review
            </span>
          </div>
          <ChevronRight className="w-3.5 h-3.5 text-orange-400" />
        </div>
      )}

      {/* Quick Actions */}
      <div className="p-2.5 flex gap-2">
        <button
          onClick={goToApprovals}
          className={cn(
            'flex-1 py-2 px-3 rounded-lg text-xs font-medium',
            'bg-white/[0.04] border border-white/[0.08]',
            'hover:bg-white/[0.08] transition-all',
            pendingCount > 0 && 'text-orange-400'
          )}
        >
          {pendingCount > 0 ? `Review (${pendingCount})` : 'View Approvals'}
        </button>
        <button
          onClick={goToSettings}
          className={cn(
            'flex-1 py-2 px-3 rounded-lg text-xs font-medium',
            'bg-white/[0.04] border border-white/[0.08]',
            'hover:bg-white/[0.08] transition-all text-white/70'
          )}
        >
          <Settings className="w-3 h-3 inline mr-1" />
          Settings
        </button>
      </div>

      {/* Mode Cycle Hint */}
      <div className="px-3 pb-2.5">
        <p className="text-[9px] text-white/30 text-center">
          Click the arrow to cycle: Shadow → Supervised → Graduated
        </p>
      </div>
    </div>
  );
}

export default ShadowModeCard;
