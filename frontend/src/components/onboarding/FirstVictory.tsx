'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { PartyPopper, ArrowRight, Sparkles, AlertCircle } from 'lucide-react';

interface FirstVictoryProps {
  aiName?: string;
  aiGreeting?: string | null;
  /** D8-1: Called after successfully marking first victory on server. */
  onVictoryComplete?: () => void;
}

const MAX_MARK_RETRIES = 3;
const MARK_RETRY_DELAY_MS = 2000;

export function FirstVictory({ aiName = 'Jarvis', aiGreeting, onVictoryComplete }: FirstVictoryProps) {
  const router = useRouter();
  const [showConfetti, setShowConfetti] = useState(false);
  const [markError, setMarkError] = useState<string | null>(null);

  const markVictory = useCallback(async (attempt = 1): Promise<void> => {
    try {
      const res = await fetch('/api/onboarding/first-victory', { method: 'POST' });

      if (!res.ok) {
        // D8-2: If server returns error, retry up to MAX_MARK_RETRIES times
        if (attempt < MAX_MARK_RETRIES) {
          setTimeout(() => markVictory(attempt + 1), MARK_RETRY_DELAY_MS);
          return;
        }
        setMarkError('Unable to mark celebration as seen. You may see this screen again on your next visit.');
        return;
      }

      // Successfully marked — notify parent to update state
      onVictoryComplete?.();
      setMarkError(null);
    } catch {
      // D8-2: Network error — retry
      if (attempt < MAX_MARK_RETRIES) {
        setTimeout(() => markVictory(attempt + 1), MARK_RETRY_DELAY_MS);
        return;
      }
      setMarkError('Connection lost. Your progress will be saved when you click "Go to Dashboard".');
    }
  }, [onVictoryComplete]);

  useEffect(() => {
    // Trigger confetti animation on mount
    const timer = setTimeout(() => setShowConfetti(true), 300);
    return () => clearTimeout(timer);
  }, []);

  // Mark first victory as seen with retry
  useEffect(() => {
    markVictory();
  }, [markVictory]);

  const goToDashboard = () => {
    router.push('/dashboard');
  };

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center space-y-8 px-4">
      {/* Confetti Effect */}
      {showConfetti && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {Array.from({ length: 30 }).map((_, i) => {
            const colors = [
              'bg-yellow-400', 'bg-blue-400', 'bg-green-400',
              'bg-pink-400', 'bg-purple-400', 'bg-orange-400',
            ];
            const size = Math.random() * 8 + 4;
            const left = Math.random() * 100;
            const delay = Math.random() * 2;
            const duration = Math.random() * 3 + 2;
            return (
              <div
                key={i}
                className={`absolute ${colors[i % colors.length]} rounded-full opacity-80`}
                style={{
                  width: size,
                  height: size,
                  left: `${left}%`,
                  top: '-10px',
                  animation: `confetti-fall ${duration}s ease-in ${delay}s forwards`,
                }}
              />
            );
          })}
        </div>
      )}

      <style jsx global>{`
        @keyframes confetti-fall {
          0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
          }
        }
      `}</style>

      <div className="relative">
        <div className="h-24 w-24 mx-auto rounded-full bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center animate-bounce">
          <PartyPopper className="h-12 w-12 text-white" />
        </div>
      </div>

      <div className="space-y-3 max-w-lg">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
          Welcome to PARWA!
        </h1>
        <p className="text-xl text-muted-foreground">
          Your AI assistant <span className="font-semibold text-foreground">{aiName}</span> is ready!
        </p>
        {aiGreeting && (
          <p className="text-lg italic text-muted-foreground">
            &ldquo;{aiGreeting}&rdquo;
          </p>
        )}
        <p className="text-muted-foreground">
          You&apos;ve completed the onboarding process. Your AI-powered customer support
          platform is now live and ready to assist your customers 24/7.
        </p>
      </div>

      {/* D8-2: Show error if marking failed after retries */}
      {markError && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground max-w-md">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>{markError}</p>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <Button size="lg" onClick={goToDashboard} className="gap-2">
          Go to Dashboard
          <ArrowRight className="h-4 w-4" />
        </Button>
        {/* D8-6: Link to /jarvis instead of /onboarding?mode=chat.
           After onboarding completes, the /onboarding page's auth guard
           redirects to /dashboard, so the old link was broken. */}
        <Button size="lg" variant="outline" onClick={() => router.push('/jarvis')} className="gap-2">
          <Sparkles className="h-4 w-4" />
          Chat with {aiName}
        </Button>
      </div>
    </div>
  );
}
