/**
 * PARWA ShadowModeStep (Day 7 — Onboarding Stage 0 Enforcer)
 *
 * Onboarding step component that explains Shadow Mode to new users.
 * Shows progress toward graduation and sample actions they'll approve.
 *
 * Features:
 *   - Animated explanation of Shadow Mode
 *   - "You're in the driver's seat" metaphor
 *   - Progress bar: X actions until graduation
 *   - Sample actions preview
 *   - Real-time shadow_actions_remaining via API
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { shadowApi, type SystemMode } from '@/lib/shadow-api';
import { useSocket } from '@/contexts/SocketContext';
import {
  Shield,
  Eye,
  CheckCircle,
  ChevronRight,
  Clock,
  MessageSquare,
  Mail,
  CreditCard,
  Loader2,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────

interface ShadowModeStepProps {
  /** Called when the user completes this step */
  onComplete: () => void;
  /** Whether this step can be skipped */
  canSkip?: boolean;
  /** Called when user graduates from shadow mode */
  onGraduate?: () => void;
  /** Additional CSS classes */
  className?: string;
}

interface SampleAction {
  type: string;
  description: string;
  icon: React.ReactNode;
  riskLevel: 'low' | 'medium' | 'high';
}

// ── Sample Actions Preview ──────────────────────────────────────────────────

const SAMPLE_ACTIONS: SampleAction[] = [
  {
    type: 'Email Reply',
    description: 'AI drafts a response to a customer inquiry',
    icon: <Mail className="w-4 h-4" />,
    riskLevel: 'low',
  },
  {
    type: 'SMS Notification',
    description: 'AI sends an order status update',
    icon: <MessageSquare className="w-4 h-4" />,
    riskLevel: 'low',
  },
  {
    type: 'Refund Request',
    description: 'AI processes a refund under $50',
    icon: <CreditCard className="w-4 h-4" />,
    riskLevel: 'medium',
  },
];

// ── Component ───────────────────────────────────────────────────────────

export function ShadowModeStep({
  onComplete,
  canSkip = true,
  onGraduate,
  className,
}: ShadowModeStepProps) {
  const { socket } = useSocket();
  const [loading, setLoading] = useState(true);
  const [actionsRemaining, setActionsRemaining] = useState(10);
  const [currentMode, setCurrentMode] = useState<SystemMode>('shadow');
  const [showSampleActions, setShowSampleActions] = useState(false);
  const [animatingProgress, setAnimatingProgress] = useState(false);
  // Track whether graduation has been announced (to fire onGraduate only once)
  const [graduationAnnounced, setGraduationAnnounced] = useState(false);

  // Fetch initial shadow mode status
  const fetchStatus = useCallback(async () => {
    try {
      const [modeRes, statsRes] = await Promise.all([
        shadowApi.getMode(),
        shadowApi.getStats(),
      ]);
      setCurrentMode(modeRes.mode);
      // For new users, this would come from a separate endpoint
      // For now, we estimate from stats
      setActionsRemaining(10 - (statsRes?.approved_count || 0));
      // Fix: Math.max guard prevents actionsRemaining going negative
      // if approved_count exceeds the expected total
      setActionsRemaining((v) => Math.max(0, v));
    } catch (err) {
      console.error('[ShadowModeStep] Failed to fetch status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // WebSocket updates
  useEffect(() => {
    if (!socket) return;

    const handleModeChange = (data: { mode: SystemMode }) => {
      setCurrentMode(data.mode);
    };

    const handleActionResolved = () => {
      setActionsRemaining((prev) => Math.max(0, prev - 1));
      setAnimatingProgress(true);
      setTimeout(() => setAnimatingProgress(false), 1000);
    };

    socket.on('shadow:mode_changed', handleModeChange);
    socket.on('shadow:action_resolved', handleActionResolved);

    return () => {
      socket.off('shadow:mode_changed', handleModeChange);
      socket.off('shadow:action_resolved', handleActionResolved);
    };
  }, [socket]);

  // Calculate progress
  const totalActions = 10;
  const progress = ((totalActions - actionsRemaining) / totalActions) * 100;
  const isGraduated = actionsRemaining <= 0 || currentMode !== 'shadow';

  // Fire onGraduate callback when graduation is first detected
  useEffect(() => {
    if (isGraduated && !graduationAnnounced && onGraduate) {
      setGraduationAnnounced(true);
      onGraduate();
    }
  }, [isGraduated, graduationAnnounced, onGraduate]);

  // Get risk level color
  const getRiskColor = (level: 'low' | 'medium' | 'high') => {
    switch (level) {
      case 'low':
        return 'text-emerald-400 bg-emerald-500/10';
      case 'medium':
        return 'text-yellow-400 bg-yellow-500/10';
      case 'high':
        return 'text-red-400 bg-red-500/10';
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-12', className)}>
        <Loader2 className="w-8 h-8 animate-spin text-[#FF7F11] mb-4" />
        <p className="text-muted-foreground">Loading your safety settings...</p>
      </div>
    );
  }

  // Graduated state - show different content
  if (isGraduated) {
    return (
      <div className={cn('text-center animate-in fade-in duration-300', className)}>
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/15 mb-4 animate-pulse">
          <CheckCircle className="w-8 h-8 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          You're in Control
        </h2>
        <p className="text-zinc-400 mb-6 max-w-md mx-auto">
          Your AI assistant is configured with safety measures in place. You can adjust these settings anytime from the dashboard.
        </p>
        <Button onClick={onComplete} size="lg">
          Continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500', className)}>
      {/* Header */}
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-orange-500/15 mb-4 animate-pulse">
          <Eye className="w-8 h-8 text-orange-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          Welcome to Shadow Mode
        </h2>
        <p className="text-zinc-400 max-w-md mx-auto">
          For your first few actions, you'll review everything before it's sent. This helps you understand how your AI assistant works.
        </p>
      </div>

      {/* Progress Card */}
      <div className="bg-card rounded-xl border p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-[#FF7F11]" />
            <span className="text-sm font-medium text-white">
              Shadow Actions Remaining
            </span>
          </div>
          <span className="text-lg font-bold text-[#FF7F11]">
            {actionsRemaining} of {totalActions}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="relative h-3 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className={cn(
              'absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out',
              animatingProgress ? 'bg-gradient-to-r from-emerald-500 to-[#FF7F11]' : 'bg-[#FF7F11]'
            )}
            style={{ width: `${progress}%` }}
          />
        </div>

        <p className="text-xs text-zinc-500 mt-2">
          {actionsRemaining === totalActions
            ? "Approve actions to build trust and graduate to more autonomy"
            : `${totalActions - actionsRemaining} actions approved — keep going!`}
        </p>
      </div>

      {/* How It Works */}
      <div className="space-y-3">
        <button
          onClick={() => setShowSampleActions(!showSampleActions)}
          className="flex items-center justify-between w-full text-left"
        >
          <span className="text-sm font-medium text-white">
            What happens in Shadow Mode?
          </span>
          <ChevronRight
            className={cn(
              'w-4 h-4 text-zinc-400 transition-transform duration-200',
              showSampleActions && 'rotate-90'
            )}
          />
        </button>

        {showSampleActions && (
          <div className="space-y-2 pt-2 animate-in fade-in slide-in-from-top-2 duration-200">
            {SAMPLE_ACTIONS.map((action, idx) => (
              <div
                key={action.type}
                className="flex items-center gap-3 p-3 rounded-lg bg-background border"
                style={{ animationDelay: `${idx * 100}ms` }}
              >
                <div className={cn(
                  'p-2 rounded-lg',
                  getRiskColor(action.riskLevel)
                )}>
                  {action.icon}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-white">
                    {action.type}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {action.description}
                  </p>
                </div>
                <div className="flex items-center gap-1 text-xs text-orange-400">
                  <Clock className="w-3 h-3" />
                  <span>Pending</span>
                </div>
              </div>
            ))}

            <div className="flex items-center gap-2 p-3 rounded-lg bg-[#FF7F11]/10 border border-[#FF7F11]/20">
              <Sparkles className="w-4 h-4 text-[#FF7F11]" />
              <p className="text-xs text-zinc-300">
                You'll review each action before it's executed. Once you approve {totalActions} actions, you'll graduate to more autonomous mode.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Benefits */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[
          { icon: Shield, label: 'Full Control', desc: 'Review every action' },
          { icon: Eye, label: 'Transparency', desc: 'See what AI does' },
          { icon: CheckCircle, label: 'Trust Building', desc: 'Learn the system' },
        ].map((item) => (
          <div
            key={item.label}
            className="flex flex-col items-center text-center p-3 rounded-lg bg-background border"
          >
            <item.icon className="w-5 h-5 text-[#FF7F11] mb-2" />
            <span className="text-sm font-medium text-white">{item.label}</span>
            <span className="text-xs text-zinc-500">{item.desc}</span>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3 justify-center pt-4">
        {canSkip && (
          <Button
            variant="ghost"
            onClick={onComplete}
            className="text-zinc-400"
          >
            Skip for now
          </Button>
        )}
        <Button onClick={onComplete} size="lg">
          Got it, let's continue
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>

      {/* Footer Note */}
      <p className="text-xs text-zinc-600 text-center">
        You can change these settings anytime in{' '}
        <span className="text-zinc-400">Dashboard → Settings → Shadow Mode</span>
      </p>
    </div>
  );
}

export default ShadowModeStep;
