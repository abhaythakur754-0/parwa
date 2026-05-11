'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Trophy, ArrowRight, Sparkles } from 'lucide-react';
import { onboardingApi, getErrorMessage } from '@/lib/api';
import toast from 'react-hot-toast';

interface FirstVictoryCelebrationProps {
  aiName: string;
  onComplete?: () => void;
}

/**
 * FirstVictoryCelebration Component
 *
 * A full-screen celebration overlay that appears after the user
 * successfully activates their AI assistant. It features CSS-based
 * confetti particles, a congratulatory heading, the AI assistant
 * name with a glowing text effect, and an animated counter message.
 * The component calls onboardingApi.completeVictory on mount to
 * record the milestone. A "Go to Dashboard" button navigates the
 * user away from the onboarding flow.
 */
export function FirstVictoryCelebration({ aiName, onComplete }: FirstVictoryCelebrationProps) {
  const router = useRouter();
  const [count, setCount] = useState(0);
  const [isRedirecting, setIsRedirecting] = useState(false);

  /**
   * Mark the first victory as complete on the backend when
   * this component mounts. This records the milestone so the
   * onboarding state reflects that the celebration was shown.
   */
  useEffect(() => {
    onboardingApi.completeVictory().catch((error) => {
      console.error('Failed to complete victory:', getErrorMessage(error));
    });
  }, []);

  /**
   * Animate the counter from 0 to a target number over time.
   * This creates a visual effect of "counting up" to emphasize
   * the excitement of going live.
   */
  useEffect(() => {
    const target = 1;
    const duration = 1500;
    const steps = 30;
    const increment = target / steps;
    const interval = duration / steps;

    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(current * 100) / 100);
      }
    }, interval);

    return () => clearInterval(timer);
  }, []);

  /**
   * Navigate to the dashboard when the user clicks the button.
   * Sets a redirecting state to show a loading indicator.
   */
  const handleGoToDashboard = () => {
    setIsRedirecting(true);
    onComplete?.();
    router.push('/dashboard');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1A1A1A] premium-gradient">
      {/* CSS confetti particles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {Array.from({ length: 80 }).map((_, i) => (
          <div
            key={i}
            className="absolute rounded-sm animate-confetti"
            style={{
              left: `${Math.random() * 100}%`,
              top: '-3%',
              width: `${4 + Math.random() * 8}px`,
              height: `${4 + Math.random() * 8}px`,
              backgroundColor: [
                '#FF7F11',
                '#FF9F5A',
                '#FFD700',
                '#FF4500',
                '#FFA500',
                '#FFFFFF',
                '#FF6347',
                '#FFB347',
              ][Math.floor(Math.random() * 8)],
              animationDelay: `${Math.random() * 2}s`,
              animationDuration: `${2.5 + Math.random() * 3}s`,
              transform: `rotate(${Math.random() * 360}deg)`,
            }}
          />
        ))}
      </div>

      {/* Celebration content */}
      <div className="relative z-10 text-center px-6 max-w-lg">
        {/* Trophy icon */}
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-orange-500/10 border border-orange-500/20 mb-8 animate-float">
          <Trophy className="w-10 h-10 text-orange-400" />
        </div>

        {/* Congratulations heading */}
        <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
          Congratulations!
        </h1>

        {/* AI name with glow effect */}
        <div className="mb-6">
          <p className="text-2xl sm:text-3xl font-bold text-gradient mb-2">
            {aiName} is now live!
          </p>
          <div className="flex items-center justify-center gap-2">
            <Sparkles className="w-4 h-4 text-orange-400" />
            <p className="text-sm text-orange-200/50">
              Your AI assistant is ready to help your customers
            </p>
          </div>
        </div>

        {/* Animated counter */}
        <div className="mb-10">
          <div className="inline-flex items-baseline gap-1 px-6 py-3 rounded-xl bg-orange-500/5 border border-orange-500/10">
            <span className="text-4xl font-bold text-orange-400 counter-bounce">
              {count}
            </span>
            <span className="text-sm text-orange-200/50 ml-2">
              ticket ready to be handled
            </span>
          </div>
          <p className="text-xs text-orange-200/30 mt-3">
            Your first ticket is just moments away
          </p>
        </div>

        {/* Go to Dashboard button */}
        <button
          type="button"
          onClick={handleGoToDashboard}
          disabled={isRedirecting}
          className="btn-primary btn-lg glow-lg"
        >
          {isRedirecting ? (
            'Redirecting...'
          ) : (
            <>
              Go to Dashboard
              <ArrowRight className="w-5 h-5 ml-2" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

export default FirstVictoryCelebration;
