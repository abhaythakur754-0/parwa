'use client';

import React, { useEffect, useState } from 'react';
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
    const timer = setTimeout(() => setShowConfetti(true), 300);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (marked) return;
    fetch('/api/onboarding/first-victory', { method: 'POST' }).catch(() => {
      // Mark locally even if API fails
    });
    setMarked(true);
  }, [marked]);

  const goToDashboard = () => {
    // Variant-aware dashboard redirect
    try {
      const ctx = localStorage.getItem('parwa_pricing_context');
      if (ctx) {
        const pricing = JSON.parse(ctx) as Record<string, unknown>;
        const variant = String(pricing.variant || '').toLowerCase();
        if (variant === 'parwa' || variant === 'mini-parwa' || variant === 'mini') {
          router.push('/dashboard?variant=parwa');
          return;
        }
        if (variant === 'parwa-high' || variant === 'high') {
          router.push('/dashboard?variant=high');
          return;
        }
        // Default PARWA variant
        if (variant) {
          router.push('/dashboard?variant=pro');
          return;
        }
      }
    } catch { /* ignore */ }

    // Fallback: check pricing context again for variants info
    try {
      const ctx = localStorage.getItem('parwa_pricing_context');
      if (ctx) {
        const parsed = JSON.parse(ctx) as Record<string, unknown>;
        // Store variants info for the dashboard to read
        localStorage.setItem('parwa_onboarding_variants', JSON.stringify({
          industry: parsed.industry,
          variants: parsed.variants,
          totalMonthly: parsed.totalMonthly,
          completedAt: new Date().toISOString(),
        }));
      }
    } catch { /* ignore */ }

    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center text-center px-4" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #1A1A1A 100%)' }}>
      {/* Confetti Effect */}
      {showConfetti && (
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {Array.from({ length: 40 }).map((_, i) => {
            const colors = [
              'bg-orange-400', 'bg-amber-400', 'bg-emerald-400',
              'bg-yellow-400', 'bg-purple-400', 'bg-blue-400',
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

      <style jsx>{`
        @keyframes confetti-fall {
          0% { transform: translateY(0) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
      `}</style>

      <div className="relative z-10 space-y-8">
        <div className="h-24 w-24 mx-auto rounded-2xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center animate-bounce shadow-2xl shadow-orange-500/30">
          <PartyPopper className="h-12 w-12 text-white" />
        </div>

        <div className="space-y-3 max-w-lg">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-orange-400 to-amber-300 bg-clip-text text-transparent">
            Welcome to PARWA!
          </h1>
          <p className="text-xl text-white">
            Your AI assistant <span className="font-semibold text-orange-400">{aiName}</span> is ready!
          </p>
          {aiGreeting && (
            <p className="text-lg italic text-orange-200/40">
              &ldquo;{aiGreeting}&rdquo;
            </p>
          )}
          <p className="text-orange-200/30">
            You&apos;ve completed the onboarding process. Your AI-powered customer support
            platform is now live and ready to assist your customers 24/7.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            onClick={goToDashboard}
            className="px-8 py-3 bg-gradient-to-r from-orange-500 to-amber-400 hover:from-orange-400 hover:to-amber-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-300 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 flex items-center justify-center gap-2"
          >
            Go to Dashboard
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            onClick={goToDashboard}
            className="px-8 py-3 rounded-xl border border-white/[0.1] text-orange-200/60 hover:bg-white/[0.04] hover:text-orange-400 transition-all flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4" />
            Chat with {aiName}
          </button>
        </div>
      </div>
    </div>
  );
}
