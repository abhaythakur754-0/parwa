'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { PartyPopper, ArrowRight, Sparkles, AlertCircle, Trophy, Loader2 } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface FirstVictoryProps {
  aiName?: string;
  aiGreeting?: string | null;
  onVictoryComplete?: () => void;
}

interface WarmupStatus {
  overall_status: string;
  models_ready: number;
  models_total: number;
  message: string;
}

// ── Constants ──────────────────────────────────────────────────────────────

const MAX_MARK_RETRIES = 3;
const MARK_RETRY_DELAY_MS = 2000;

// Enhanced confetti: 12 colors, 4 shape types
const CONFETTI_COLORS = [
  '#F59E0B', // amber
  '#EF4444', // red
  '#10B981', // emerald
  '#EC4899', // pink
  '#8B5CF6', // violet
  '#F97316', // orange
  '#06B6D4', // cyan
  '#F43F5E', // rose
  '#84CC16', // lime
  '#A855F7', // purple
  '#14B8A6', // teal
  '#FBBF24', // yellow
];

type ConfettiShape = 'circle' | 'square' | 'rectangle' | 'streamer';

interface ConfettiParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  rotation: number;
  rotationSpeed: number;
  color: string;
  shape: ConfettiShape;
  width: number;
  height: number;
  opacity: number;
  gravity: number;
  airResistance: number;
  life: number;
  maxLife: number;
}

// ── Progressive Reveal Timing (ms) ─────────────────────────────────────────
const REVEAL_TIMELINE = {
  confetti: 0,
  trophy: 500,
  heading: 1000,
  message: 1500,
  stats: 2000,
  buttons: 2500,
} as const;

// ── Confetti Canvas Hook ───────────────────────────────────────────────────

function useConfetti(canvasRef: React.RefObject<HTMLCanvasElement | null>) {
  const particlesRef = useRef<ConfettiParticle[]>([]);
  const animationRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);
  const mountedRef = useRef(true);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const resizeDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const createParticle = useCallback(
    (centerX: number, centerY: number, burst = false): ConfettiParticle => {
      const shape: ConfettiShape = (['circle', 'square', 'rectangle', 'streamer'] as ConfettiShape[])[
        Math.floor(Math.random() * 4)
      ];
      const speed = burst ? (Math.random() * 12 + 4) : (Math.random() * 3 + 1);
      const angle = Math.random() * Math.PI * 2;

      return {
        x: centerX + (burst ? (Math.random() - 0.5) * 40 : (Math.random() - 0.5) * 300),
        y: burst ? centerY : -10,
        vx: Math.cos(angle) * speed * (burst ? 1 : 0.3),
        vy: burst ? -Math.abs(Math.sin(angle) * speed * 1.5) - 2 : Math.random() * 2 + 0.5,
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 12,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
        shape,
        width: shape === 'streamer' ? Math.random() * 3 + 1 : Math.random() * 8 + 4,
        height: shape === 'rectangle' ? Math.random() * 12 + 6 : shape === 'streamer' ? Math.random() * 16 + 10 : Math.random() * 8 + 4,
        opacity: 1,
        gravity: 0.12 + Math.random() * 0.08,
        airResistance: 0.98 + Math.random() * 0.015,
        life: 0,
        maxLife: 180 + Math.random() * 120, // 3-5 seconds at 60fps
      };
    },
    [],
  );

  const drawParticle = useCallback((ctx: CanvasRenderingContext2D, p: ConfettiParticle) => {
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.rotate((p.rotation * Math.PI) / 180);
    ctx.globalAlpha = p.opacity * Math.max(0, 1 - p.life / p.maxLife);
    ctx.fillStyle = p.color;

    switch (p.shape) {
      case 'circle':
        ctx.beginPath();
        ctx.arc(0, 0, p.width / 2, 0, Math.PI * 2);
        ctx.fill();
        break;
      case 'square':
        ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
        break;
      case 'rectangle':
        ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
        break;
      case 'streamer':
        ctx.fillRect(-p.width / 2, -p.height / 2, p.width, p.height);
        break;
    }

    ctx.restore();
  }, []);

  const animate = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !mountedRef.current) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const elapsed = Date.now() - startTimeRef.current;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Initial burst (first 500ms) — spawn burst particles
    if (elapsed < 500 && particlesRef.current.length < 60) {
      const centerX = canvas.width / 2;
      const centerY = canvas.height * 0.35;
      for (let i = 0; i < 5; i++) {
        particlesRef.current.push(createParticle(centerX, centerY, true));
      }
    }

    // Continuous trickle (after 200ms)
    if (elapsed > 200 && elapsed < 3000 && Math.random() < 0.3) {
      particlesRef.current.push(createParticle(canvas.width / 2, 0, false));
    }

    // Update and draw particles
    const alive: ConfettiParticle[] = [];
    for (const p of particlesRef.current) {
      p.vy += p.gravity;
      p.vx *= p.airResistance;
      p.vy *= p.airResistance;
      p.x += p.vx;
      p.y += p.vy;
      p.rotation += p.rotationSpeed;
      p.life++;

      if (p.life < p.maxLife && p.y < canvas.height + 50) {
        drawParticle(ctx, p);
        alive.push(p);
      }
    }

    particlesRef.current = alive;

    // Continue animation while particles exist or we're still spawning
    if (particlesRef.current.length > 0 || elapsed < 3500) {
      animationRef.current = requestAnimationFrame(animate);
    }
  }, [canvasRef, createParticle, drawParticle]);

  const start = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // D14-P6: Skip confetti for users who prefer reduced motion
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    }

    // D14-P7: ResizeObserver for canvas on rotation/resize
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
    }
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (resizeDebounceRef.current) {
          clearTimeout(resizeDebounceRef.current);
        }
        resizeDebounceRef.current = setTimeout(() => {
          const c = canvasRef.current;
          if (!c) return;
          const { width, height } = entry.contentRect;
          const dpr = window.devicePixelRatio || 1;
          c.width = width * dpr;
          c.height = height * dpr;
          const ctx2 = c.getContext('2d');
          if (ctx2) {
            ctx2.setTransform(dpr, 0, 0, dpr, 0, 0);
          }
        }, 200);
      }
    });
    observer.observe(canvas);
    resizeObserverRef.current = observer;

    particlesRef.current = [];
    startTimeRef.current = Date.now();
    mountedRef.current = true;
    animate();
  }, [canvasRef, animate]);

  const stop = useCallback(() => {
    mountedRef.current = false;
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = 0;
    }
    // D14-P7: Clean up ResizeObserver
    if (resizeObserverRef.current) {
      resizeObserverRef.current.disconnect();
      resizeObserverRef.current = null;
    }
    if (resizeDebounceRef.current) {
      clearTimeout(resizeDebounceRef.current);
      resizeDebounceRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return { start, stop };
}

// ── Sound Effect Placeholder ──────────────────────────────────────────────
//
// Future sound effect integration can be added here. The hook structure
// is ready to be uncommented when audio assets are available:
//
// function useVictorySound() {
//   const audioRef = useRef<HTMLAudioElement | null>(null);
//
//   useEffect(() => {
//     // Preload victory sound
//     audioRef.current = new Audio('/sounds/victory.mp3');
//     audioRef.current.volume = 0.4;
//     return () => {
//       audioRef.current = null;
//     };
//   }, []);
//
//   const play = useCallback(async () => {
//     if (!audioRef.current) return;
//     try {
//       audioRef.current.currentTime = 0;
//       await audioRef.current.play();
//     } catch {
//       // Browser may block autoplay — silently ignore
//     }
//   }, []);
//
//   return { play };
// }
//
// Usage in component:
// const { play: playVictorySound } = useVictorySound();
// Call playVictorySound() when the confetti triggers.

// ── Progressive Reveal Hook ────────────────────────────────────────────────

function useProgressiveReveal() {
  const [visibleSections, setVisibleSections] = useState<Set<string>>(new Set());

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    const schedule = (key: string, delay: number) => {
      timers.push(
        setTimeout(() => {
          setVisibleSections((prev) => new Set([...prev, key]));
        }, delay),
      );
    };

    schedule('confetti', REVEAL_TIMELINE.confetti);
    schedule('trophy', REVEAL_TIMELINE.trophy);
    schedule('heading', REVEAL_TIMELINE.heading);
    schedule('message', REVEAL_TIMELINE.message);
    schedule('stats', REVEAL_TIMELINE.stats);
    schedule('buttons', REVEAL_TIMELINE.buttons);

    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  const isVisible = useCallback(
    (key: string) => visibleSections.has(key),
    [visibleSections],
  );

  // D14-P10: Provide aria-hidden state for progressive reveal sections
  const getAriaHidden = useCallback(
    (key: string) => !visibleSections.has(key),
    [visibleSections],
  );

  return { isVisible, getAriaHidden };
}

// ── Component ──────────────────────────────────────────────────────────────

export function FirstVictory({ aiName = 'Jarvis', aiGreeting, onVictoryComplete }: FirstVictoryProps) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { start: startConfetti, stop: stopConfetti } = useConfetti(canvasRef);
  const { isVisible, getAriaHidden } = useProgressiveReveal();
  const mountedRef = useRef(true);
  // D14-P13: Track retry setTimeout IDs for cleanup on unmount
  const retryTimeoutsRef = useRef<number[]>([]);

  const [markError, setMarkError] = useState<string | null>(null);
  const [warmupStatus, setWarmupStatus] = useState<WarmupStatus | null>(null);
  const [warmupComplete, setWarmupComplete] = useState(false);
  const [autoRedirecting, setAutoRedirecting] = useState(false); // D14-P4

  // ── Mark first victory as seen with retry ─────────────────────────────

  const markVictory = useCallback(
    async (attempt = 1): Promise<void> => {
      if (!mountedRef.current) return;

      // D14-P4: Set sessionStorage flag on first attempt to break infinite loop
      if (attempt === 1) {
        try { sessionStorage.setItem('parwa_victory_attempted', Date.now().toString()); } catch { /* ignore */ }
      }

      try {
        const res = await fetch('/api/onboarding/first-victory', { method: 'POST' });

        if (!res.ok) {
          if (attempt < MAX_MARK_RETRIES && mountedRef.current) {
            const id = window.setTimeout(() => markVictory(attempt + 1), MARK_RETRY_DELAY_MS);
            retryTimeoutsRef.current.push(id);
            return;
          }
          if (mountedRef.current) {
            setMarkError(
              'Unable to mark celebration as seen. You may see this screen again on your next visit.',
            );
          }
          return;
        }

        onVictoryComplete?.();
        if (mountedRef.current) setMarkError(null);
      } catch {
        if (attempt < MAX_MARK_RETRIES && mountedRef.current) {
          const id = window.setTimeout(() => markVictory(attempt + 1), MARK_RETRY_DELAY_MS);
          retryTimeoutsRef.current.push(id);
          return;
        }
        if (mountedRef.current) {
          setMarkError(
            'Connection lost. Your progress will be saved when you click "Go to Dashboard".',
          );
        }
      }
    },
    [onVictoryComplete],
  );

  useEffect(() => {
    // D14-P4: If a previous victory attempt was made (sessionStorage flag exists)
    // but server says not completed, auto-redirect to dashboard after 3 seconds
    // to break the infinite loop on page refresh.
    const checkPreviousAttempt = async () => {
      try {
        const wasAttempted = sessionStorage.getItem('parwa_victory_attempted');
        if (!wasAttempted) return;

        // Check if victory is already completed on the server
        const stateRes = await fetch('/api/onboarding/state');
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          if (stateData.first_victory_completed) {
            // Already marked — trigger completion
            onVictoryComplete?.();
            return;
          }
        }

        // Not completed on server but was attempted — this is the loop scenario.
        // Auto-redirect after 3 seconds.
        if (mountedRef.current) {
          setAutoRedirecting(true);
          onVictoryComplete?.(); // Force-set local state so wizard redirect triggers
          setTimeout(() => {
            if (mountedRef.current) {
              router.push('/dashboard');
            }
          }, 3000);
        }
      } catch {
        // Best effort — proceed with normal mark attempt
        markVictory();
      }
    };

    checkPreviousAttempt();

    return () => {
      mountedRef.current = false;
      // D14-P13: Clear any pending retry timeouts
      retryTimeoutsRef.current.forEach(clearTimeout);
      retryTimeoutsRef.current = [];
    };
  }, [markVictory, onVictoryComplete, router]);

  // ── Start confetti animation ──────────────────────────────────────────

  useEffect(() => {
    const timer = setTimeout(() => {
      startConfetti();
    }, REVEAL_TIMELINE.confetti);

    return () => {
      clearTimeout(timer);
      stopConfetti();
    };
  }, [startConfetti, stopConfetti]);

  // ── Warmup status polling ─────────────────────────────────────────────

  useEffect(() => {
    // D14-P12: Skip polling entirely if models are already warm
    if (!mountedRef.current || warmupComplete) return;

    let cancelled = false;

    const fetchWarmup = async () => {
      try {
        const res = await fetch('/api/onboarding/warmup-status');
        if (res.ok && mountedRef.current && !cancelled) {
          const data: WarmupStatus = await res.json();
          setWarmupStatus(data);
          if (data.overall_status === 'warm') {
            setWarmupComplete(true);
            return; // Stop polling
          }
        }
      } catch {
        /* best effort */
      }

      // Auto-refresh every 5 seconds if not complete
      if (!cancelled && !warmupComplete) {
        setTimeout(fetchWarmup, 5000);
      }
    };

    fetchWarmup();

    return () => {
      cancelled = true;
    };
  }, [warmupComplete]);

  // ── Navigation handlers ───────────────────────────────────────────────

  const goToDashboard = () => {
    // D14-P4: Call onVictoryComplete BEFORE navigating to force-set local state
    // and ensure the wizard redirect kicks in even if the server mark failed.
    onVictoryComplete?.();
    router.push('/dashboard');
  };

  // ── Warmup progress calculation ───────────────────────────────────────

  const warmupProgress =
    warmupStatus && warmupStatus.models_total > 0
      ? Math.round((warmupStatus.models_ready / warmupStatus.models_total) * 100)
      : 0;

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center space-y-8 px-4 relative">
      {/* Confetti Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none w-full h-full"
        aria-hidden="true"
      />

      {/* Trophy / Celebration Icon — Progressive Reveal at 500ms */}
      <div
        className={`relative transition-all duration-500 ${
          isVisible('trophy')
            ? 'opacity-100 scale-100'
            : 'opacity-0 scale-0'
        }`}
        style={{ transitionDelay: '0ms' }}
        aria-hidden={getAriaHidden('trophy')}
      >
        <div className="h-28 w-28 mx-auto rounded-full bg-gradient-to-br from-amber-400 via-yellow-500 to-orange-500 flex items-center justify-center shadow-2xl shadow-amber-500/30">
          <Trophy className="h-14 w-14 text-white drop-shadow-lg" />
        </div>
        {/* Sparkle ring */}
        <div className="absolute -inset-2 rounded-full border-2 border-dashed border-amber-300/50 animate-[spin_10s_linear_infinite]" />
      </div>

      {/* Heading — Progressive Reveal at 1000ms */}
      <div
        className={`space-y-1 max-w-lg transition-all duration-500 ${
          isVisible('heading')
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-4'
        }`}
        aria-hidden={getAriaHidden('heading')}
      >
        <h1 className="text-5xl font-extrabold bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 bg-clip-text text-transparent">
          Congratulations!
        </h1>
        <p className="text-lg text-muted-foreground font-medium">
          Welcome to PARWA 🎉
        </p>
      </div>

      {/* AI Name + Greeting Message — Progressive Reveal at 1500ms */}
      <div
        className={`space-y-3 max-w-lg transition-all duration-500 ${
          isVisible('message')
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-4'
        }`}
        style={{ transitionDelay: '100ms' }}
        aria-hidden={getAriaHidden('message')}
      >
        <p className="text-xl text-muted-foreground">
          {warmupComplete ? (
            <>
              Your AI assistant{' '}
              <span className="font-semibold text-foreground">{aiName}</span> is ready!
            </>
          ) : warmupStatus?.overall_status === 'cooling' ? (
            <>
              Your AI assistant{' '}
              <span className="font-semibold text-foreground">{aiName}</span> is activating{' '}
              <span className="text-amber-600">
                (some models are warming up — responses may be slower initially)
              </span>
            </>
          ) : warmupStatus?.overall_status === 'warming' ? (
            <>
              Your AI assistant{' '}
              <span className="font-semibold text-foreground">{aiName}</span> is warming up{' '}
              <span className="text-amber-600">
                (AI models are being prepared — first responses may take a moment)
              </span>
            </>
          ) : (
            <>
              Your AI assistant{' '}
              <span className="font-semibold text-foreground">{aiName}</span> is ready!
            </>
          )}
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

      {/* Stats — Progressive Reveal at 2000ms */}
      <div
        className={`transition-all duration-500 ${
          isVisible('stats')
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-4'
        }`}
        style={{ transitionDelay: '200ms' }}
        aria-hidden={getAriaHidden('stats')}
      >
        <div className="flex items-center justify-center gap-6">
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold text-foreground">
              <Sparkles className="inline h-5 w-5 mr-1 text-amber-500" />
              Active
            </span>
            <span className="text-xs text-muted-foreground">AI Status</span>
          </div>
          <div className="h-8 w-px bg-border" />
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold text-green-600">24/7</span>
            <span className="text-xs text-muted-foreground">Support</span>
          </div>
          <div className="h-8 w-px bg-border" />
          <div className="flex flex-col items-center">
            <span className="text-2xl font-bold text-foreground">Ready</span>
            <span className="text-xs text-muted-foreground">Go Live</span>
          </div>
        </div>
      </div>

      {/* Warmup Progress Panel — if models still warming */}
      {warmupStatus && !warmupComplete && (
        <div
          className={`w-full max-w-md transition-all duration-500 ${
            isVisible('stats')
              ? 'opacity-100 translate-y-0'
              : 'opacity-0 translate-y-4'
          }`}
          style={{ transitionDelay: '300ms' }}
        >
          <div className="rounded-xl border bg-muted/40 backdrop-blur-sm p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                <p className="text-sm font-medium">AI Models Warming Up</p>
              </div>
              <span className="text-xs text-muted-foreground">
                {warmupProgress}%
              </span>
            </div>

            {/* Progress Bar */}
            <div
              className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={warmupProgress}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="AI model warmup progress"
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-green-500 transition-all duration-700 ease-out"
                style={{ width: `${warmupProgress}%` }}
              />
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{warmupStatus.message || 'Your AI models are getting ready...'}</span>
              <span>
                {warmupStatus.models_ready} / {warmupStatus.models_total} models
              </span>
            </div>

            <p className="text-xs text-muted-foreground/70 italic">
              Auto-refreshing every 5 seconds. You can start using PARWA immediately.
            </p>
          </div>
        </div>
      )}

      {/* D14-P4: Auto-redirect message when stuck in loop */}
      {autoRedirecting && (
        <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400 max-w-md animate-in fade-in duration-300">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
          <p>Your AI has been activated. Redirecting to dashboard...</p>
        </div>
      )}

      {/* Mark error */}
      {markError && !autoRedirecting && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground max-w-md">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p>{markError}</p>
        </div>
      )}

      {/* Action Buttons — Progressive Reveal at 2500ms */}
      <div
        className={`flex flex-col sm:flex-row gap-3 transition-all duration-500 ${
          isVisible('buttons')
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 translate-y-6'
        }`}
        style={{ transitionDelay: '300ms' }}
        aria-hidden={getAriaHidden('buttons')}
      >
        <Button
          size="lg"
          onClick={goToDashboard}
          className="gap-2 bg-gradient-to-r from-primary to-primary/90 hover:from-primary/90 hover:to-primary shadow-lg"
        >
          Go to Dashboard
          <ArrowRight className="h-4 w-4" />
        </Button>
        <Button
          size="lg"
          variant="outline"
          onClick={() => router.push('/jarvis')}
          className="gap-2 border-2 hover:bg-muted/50"
        >
          <Sparkles className="h-4 w-4" />
          Chat with {aiName}
        </Button>
      </div>
    </div>
  );
}
