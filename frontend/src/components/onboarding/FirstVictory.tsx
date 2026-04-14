'use client';

import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { PartyPopper, ArrowRight, Sparkles } from 'lucide-react';

interface FirstVictoryProps {
  aiName?: string;
  aiGreeting?: string | null;
}

export function FirstVictory({ aiName = 'Jarvis', aiGreeting }: FirstVictoryProps) {
  const router = useRouter();
  const [showConfetti, setShowConfetti] = useState(false);
  const [marked, setMarked] = useState(false);

  useEffect(() => {
    // Trigger confetti animation on mount
    const timer = setTimeout(() => setShowConfetti(true), 300);
    return () => clearTimeout(timer);
  }, []);

  // Mark first victory as seen
  useEffect(() => {
    if (marked) return;
    fetch('/api/onboarding/first-victory', { method: 'POST' }).catch(() => {});
    setMarked(true);
  }, [marked]);

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

      <div className="flex flex-col sm:flex-row gap-3">
        <Button size="lg" onClick={goToDashboard} className="gap-2">
          Go to Dashboard
          <ArrowRight className="h-4 w-4" />
        </Button>
        <Button size="lg" variant="outline" onClick={() => router.push('/onboarding?mode=chat')} className="gap-2">
          <Sparkles className="h-4 w-4" />
          Chat with {aiName}
        </Button>
      </div>
    </div>
  );
}
