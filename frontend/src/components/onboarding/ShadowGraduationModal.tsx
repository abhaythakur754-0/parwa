/**
 * PARWA ShadowGraduationModal (Day 7 — Onboarding Stage 0 Enforcer)
 *
 * Celebration modal shown when a user graduates from Shadow Mode
 * to Supervised or Graduated mode after completing their initial actions.
 *
 * Features:
 *   - Confetti animation (CSS-based)
 *   - "You've graduated!" message
 *   - Explanation of what changed
 *   - Option to stay in Shadow mode longer
 *   - Continue button
 */

'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { shadowApi, type SystemMode } from '@/lib/shadow-api';
import {
  PartyPopper,
  Shield,
  Eye,
  CheckCircle,
  ArrowRight,
  Loader2,
  Sparkles,
  X,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────

interface ShadowGraduationModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Called when modal is closed */
  onClose: () => void;
  /** Called when user confirms graduation */
  onContinue?: () => void;
  /** The new mode after graduation */
  newMode?: SystemMode;
  /** Additional CSS classes */
  className?: string;
}

interface ConfettiPiece {
  id: number;
  x: number;
  delay: number;
  color: string;
  size: number;
  duration: number;
}

// ── Confetti Colors ─────────────────────────────────────────────────────

const CONFETTI_COLORS = [
  '#FF7F11', // PARWA orange
  '#10B981', // Emerald
  '#3B82F6', // Blue
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#EC4899', // Pink
];

// ── Component ───────────────────────────────────────────────────────────

export function ShadowGraduationModal({
  isOpen,
  onClose,
  onContinue,
  newMode = 'supervised',
  className,
}: ShadowGraduationModalProps) {
  const [loading, setLoading] = useState(false);
  const [stayInShadow, setStayInShadow] = useState(false);
  const [confetti, setConfetti] = useState<ConfettiPiece[]>([]);

  // Generate confetti pieces
  useEffect(() => {
    if (isOpen) {
      const pieces: ConfettiPiece[] = [];
      for (let i = 0; i < 50; i++) {
        pieces.push({
          id: i,
          x: Math.random() * 100,
          delay: Math.random() * 0.5,
          color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
          size: Math.random() * 8 + 6,
          duration: 2 + Math.random() * 1,
        });
      }
      setConfetti(pieces);
    }
  }, [isOpen]);

  // Handle continue
  const handleContinue = async () => {
    setLoading(true);
    try {
      if (stayInShadow) {
        await shadowApi.setMode('shadow', 'ui');
      }
      onContinue?.();
      onClose();
    } catch (err) {
      console.error('[ShadowGraduationModal] Failed to update mode:', err);
    } finally {
      setLoading(false);
    }
  };

  // Get mode info
  const getModeInfo = () => {
    switch (newMode) {
      case 'supervised':
        return {
          label: 'Supervised Mode',
          description: 'High-risk actions will need your approval, while safe actions execute automatically.',
          icon: <Shield className="w-6 h-6" />,
          color: 'text-blue-400',
          bgColor: 'bg-blue-500/15',
        };
      case 'graduated':
        return {
          label: 'Graduated Mode',
          description: 'Most actions will execute automatically. You can undo within 30 minutes.',
          icon: <CheckCircle className="w-6 h-6" />,
          color: 'text-emerald-400',
          bgColor: 'bg-emerald-500/15',
        };
      default:
        return {
          label: 'Shadow Mode',
          description: 'All actions require your approval.',
          icon: <Eye className="w-6 h-6" />,
          color: 'text-orange-400',
          bgColor: 'bg-orange-500/15',
        };
    }
  };

  const modeInfo = getModeInfo();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Confetti */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {confetti.map((piece) => (
          <div
            key={piece.id}
            className="absolute animate-confetti-fall"
            style={{
              left: `${piece.x}%`,
              width: piece.size,
              height: piece.size,
              backgroundColor: piece.color,
              borderRadius: Math.random() > 0.5 ? '50%' : '2px',
              animationDelay: `${piece.delay}s`,
              animationDuration: `${piece.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Modal */}
      <div
        className={cn(
          'relative w-full max-w-md bg-[#111111] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden',
          'animate-in fade-in zoom-in-95 slide-in-from-bottom-4 duration-300',
          className
        )}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors z-10"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Content */}
        <div className="p-6 pt-8 text-center">
          {/* Celebration Icon */}
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-[#FF7F11]/15 mb-4 animate-bounce">
            <PartyPopper className="w-10 h-10 text-[#FF7F11]" />
          </div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-white mb-2">
            Congratulations! 🎉
          </h2>
          <p className="text-zinc-400 mb-6">
            You've completed your Shadow Mode training and earned more autonomy for your AI assistant.
          </p>

          {/* New Mode Card */}
          <div className={cn(
            'rounded-xl border p-4 mb-6',
            modeInfo.bgColor,
            'border-white/[0.06]'
          )}>
            <div className="flex items-center justify-center gap-3 mb-3">
              <div className={cn('p-2 rounded-lg', modeInfo.bgColor)}>
                <span className={modeInfo.color}>{modeInfo.icon}</span>
              </div>
              <span className={cn('text-lg font-semibold', modeInfo.color)}>
                {modeInfo.label}
              </span>
            </div>
            <p className="text-sm text-zinc-300">
              {modeInfo.description}
            </p>
          </div>

          {/* What Changed */}
          <div className="bg-background rounded-lg border p-4 mb-6 text-left">
            <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#FF7F11]" />
              What changed?
            </h3>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                <span>Low-risk actions now execute automatically</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                <span>High-risk actions still need your approval</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                <span>You can undo actions within 30 minutes</span>
              </li>
            </ul>
          </div>

          {/* Stay in Shadow Option */}
          <label className="flex items-center justify-center gap-2 mb-6 cursor-pointer">
            <input
              type="checkbox"
              checked={stayInShadow}
              onChange={(e) => setStayInShadow(e.target.checked)}
              className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-[#FF7F11] focus:ring-[#FF7F11]"
            />
            <span className="text-sm text-zinc-400">
              Stay in Shadow Mode (keep reviewing all actions)
            </span>
          </label>

          {/* Actions */}
          <div className="flex flex-col gap-3">
            <Button
              onClick={handleContinue}
              disabled={loading}
              size="lg"
              className="w-full"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : null}
              {stayInShadow ? 'Stay in Shadow Mode' : 'Continue to Supervised Mode'}
              {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
            </Button>
            <p className="text-xs text-zinc-600">
              You can change this anytime in Settings → Shadow Mode
            </p>
          </div>
        </div>
      </div>

      {/* Confetti Animation Styles */}
      <style jsx global>{`
        @keyframes confetti-fall {
          0% {
            transform: translateY(-100vh) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
          }
        }
        .animate-confetti-fall {
          animation: confetti-fall linear forwards;
        }
      `}</style>
    </div>
  );
}

export default ShadowGraduationModal;
