'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface SlideData {
  id: number;
  title: string;
  subtitle: string;
  description: string;
  accentGlow: string;
  slideNumber: string;
}

const slides: SlideData[] = [
  {
    id: 1,
    title: 'Control Everything with Just a Chat',
    subtitle: 'No dashboards. No menus. No training.',
    description: 'Just type what you need. Jarvis understands and does it instantly. Like texting a super-smart employee who never sleeps.',
    accentGlow: 'rgba(22, 163, 74, 0.12)',
    slideNumber: '01/05',
  },
  {
    id: 2,
    title: 'Zero Tech Skills Required',
    subtitle: 'If you can chat, you can run your support.',
    description: 'Never managed customer support? Perfect. Just tell Jarvis what you want. It handles the rest.',
    accentGlow: 'rgba(245, 158, 11, 0.12)',
    slideNumber: '02/05',
  },
  {
    id: 3,
    title: 'It Gets Smarter Every Day',
    subtitle: 'Upload your docs. Watch it learn.',
    description: 'Your manuals, FAQs, policies — feed them once. Jarvis reads, understands, and starts answering like your best agent.',
    accentGlow: 'rgba(16, 185, 129, 0.1)',
    slideNumber: '03/05',
  },
  {
    id: 4,
    title: 'Get 40+ Hours Back Every Week',
    subtitle: '90% of tickets are repetitive.',
    description: 'While you sleep, Jarvis resolves tickets. While you work, Jarvis resolves tickets. You focus on growing your business.',
    accentGlow: 'rgba(255, 215, 0, 0.1)',
    slideNumber: '04/05',
  },
  {
    id: 5,
    title: 'Meet Jarvis — Your AI Employee',
    subtitle: 'Like Iron Man\'s Jarvis, but for your business.',
    description: 'Your personal AI officer who never complains, never takes a day off, and always delivers. Available 24/7/365.',
    accentGlow: 'rgba(22, 163, 74, 0.15)',
    slideNumber: '05/05',
  },
];

// ──────────────────────────────────────────────────────────────────
// VIVID SLIDE BACKGROUNDS — Full-slide, eye-catching animations
// ──────────────────────────────────────────────────────────────────

/** Slide 1: "Control Everything with Just a Chat" — Animated chat bubbles */
function SlideBackground1() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/60 via-white to-emerald-50/40" />

      {/* Large chat bubble — user message (right side) */}
      <div className="absolute top-[12%] right-[8%] w-48 sm:w-64 h-20 sm:h-24 rounded-2xl rounded-br-sm bg-emerald-500/15 border border-emerald-300/20 backdrop-blur-sm flex items-center px-5 sm:px-6"
        style={{ animation: 'slide1BubbleFlyInLeft 6s ease-in-out infinite' }}>
        <span className="text-emerald-700/60 text-xs sm:text-sm font-medium">Handle these 15 refund requests ✨</span>
        <div className="ml-2 w-2 h-2 rounded-full bg-emerald-500/60" style={{ animation: 'slide1TypingCursor 1s infinite' }} />
      </div>

      {/* Reply bubble — Jarvis (left-ish, on right half) */}
      <div className="absolute top-[30%] right-[5%] w-56 sm:w-72 h-16 sm:h-20 rounded-2xl rounded-bl-sm bg-white/80 border border-emerald-200/30 shadow-lg shadow-emerald-600/5 flex items-center px-5 sm:px-6"
        style={{ animation: 'slide1BubbleFlyInRight 8s ease-in-out infinite 2s' }}>
        <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center mr-3 flex-shrink-0">
          <svg className="w-3.5 h-3.5 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
          </svg>
        </div>
        <span className="text-gray-600/70 text-xs sm:text-sm">✅ Done! $4,280 refunded. 3.5hrs saved.</span>
      </div>

      {/* Decorative floating bubbles */}
      <div className="absolute w-20 h-20 rounded-full bg-emerald-200/25 border border-emerald-300/20 top-[55%] right-[25%]"
        style={{ animation: 'slide1BubbleFloat 7s ease-in-out infinite' }} />
      <div className="absolute w-14 h-14 rounded-full bg-emerald-300/15 border border-emerald-300/15 top-[65%] right-[50%]"
        style={{ animation: 'slide1BubbleFloatAlt 9s ease-in-out infinite 1s' }} />
      <div className="absolute w-24 h-24 rounded-full bg-emerald-100/20 border border-emerald-200/15 top-[45%] right-[65%]"
        style={{ animation: 'slide1BubbleFloatAlt 11s ease-in-out infinite 3s' }} />
      <div className="absolute w-10 h-10 rounded-full bg-emerald-400/15 border border-emerald-400/10 top-[75%] right-[15%]"
        style={{ animation: 'slide1BubbleFloat 8s ease-in-out infinite 2s' }} />

      {/* Green glow pulse */}
      <div className="absolute top-1/2 right-1/3 -translate-y-1/2 w-72 h-72 sm:w-96 sm:h-96 rounded-full bg-emerald-400/8 blur-[80px]"
        style={{ animation: 'slide1GlowPulse 4s ease-in-out infinite' }} />

      {/* Message send indicator */}
      <div className="absolute bottom-[18%] right-[12%] flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-100/60 border border-emerald-200/30"
        style={{ animation: 'slide1MessagePulse 3s ease-in-out infinite' }}>
        <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
        <span className="text-emerald-700/60 text-xs font-medium">Sent instantly</span>
      </div>
    </div>
  );
}

/** Slide 2: "Zero Tech Skills Required" — Morphing shapes + confetti */
function SlideBackground2() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/50 via-white to-amber-50/30" />

      {/* Large morphing shapes */}
      <div className="absolute w-40 h-40 sm:w-52 sm:h-52 bg-emerald-200/25 border border-emerald-300/20 top-[15%] right-[12%]"
        style={{ animation: 'slide2MorphShape 10s ease-in-out infinite' }} />
      <div className="absolute w-32 h-32 sm:w-44 sm:h-44 bg-amber-200/20 border border-amber-300/15 top-[45%] right-[40%]"
        style={{ animation: 'slide2MorphAlt 8s ease-in-out infinite 2s' }} />
      <div className="absolute w-24 h-24 sm:w-36 sm:h-36 bg-emerald-100/30 border border-emerald-200/25 top-[60%] right-[20%]"
        style={{ animation: 'slide2IconMorph 12s ease-in-out infinite 1s' }} />

      {/* Gear → Checkmark icon morph */}
      <div className="absolute top-[28%] right-[55%] w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-white/80 border border-emerald-200/40 shadow-lg flex items-center justify-center"
        style={{ animation: 'slide2IconMorph 8s ease-in-out infinite' }}>
        <svg className="w-8 h-8 sm:w-10 sm:h-10 text-emerald-500/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"
          style={{ animation: 'slide2GearSpin 6s linear infinite' }}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </div>

      {/* Checkmark pop icons */}
      <div className="absolute top-[55%] right-[60%] w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-emerald-100/80 flex items-center justify-center"
        style={{ animation: 'slide2CheckmarkPop 5s ease-in-out infinite 1s' }}>
        <svg className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <div className="absolute top-[40%] right-[30%] w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-emerald-100/80 flex items-center justify-center"
        style={{ animation: 'slide2CheckmarkPop 5s ease-in-out infinite 2.5s' }}>
        <svg className="w-4 h-4 sm:w-5 sm:h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>

      {/* Confetti particles */}
      {[
        { left: '15%', delay: '0s', color: '#22C55E' },
        { left: '30%', delay: '1.5s', color: '#16A34A' },
        { left: '50%', delay: '3s', color: '#fbbf24' },
        { left: '70%', delay: '0.8s', color: '#4ADE80' },
        { left: '85%', delay: '2.2s', color: '#15803D' },
      ].map((confetti, i) => (
        <div key={i} className="absolute w-2 h-2 rounded-sm top-0"
          style={{
            left: confetti.left,
            backgroundColor: confetti.color,
            animation: `slide2ConfettiFall ${4 + i * 0.5}s linear infinite ${confetti.delay}`,
            opacity: 0.6,
          }} />
      ))}

      {/* Warm glow */}
      <div className="absolute bottom-[20%] right-[35%] w-48 h-48 bg-amber-200/10 rounded-full blur-[60px]"
        style={{ animation: 'slide1GlowPulse 5s ease-in-out infinite 1s' }} />
    </div>
  );
}

/** Slide 3: "It Gets Smarter Every Day" — Neural network + brain */
function SlideBackground3() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/50 via-white to-emerald-50/40" />

      {/* Neural network nodes */}
      {[
        { top: '10%', right: '15%', size: 'w-3.5 h-3.5', delay: '0s', color: 'bg-emerald-400' },
        { top: '18%', right: '35%', size: 'w-2.5 h-2.5', delay: '0.5s', color: 'bg-emerald-400' },
        { top: '12%', right: '55%', size: 'w-3 h-3', delay: '1s', color: 'bg-emerald-300' },
        { top: '30%', right: '22%', size: 'w-2 h-2', delay: '1.5s', color: 'bg-emerald-500' },
        { top: '35%', right: '48%', size: 'w-3 h-3', delay: '0.3s', color: 'bg-emerald-400' },
        { top: '25%', right: '68%', size: 'w-2.5 h-2.5', delay: '2s', color: 'bg-emerald-300' },
        { top: '50%', right: '18%', size: 'w-3 h-3', delay: '0.8s', color: 'bg-emerald-500' },
        { top: '55%', right: '42%', size: 'w-2 h-2', delay: '1.2s', color: 'bg-emerald-400' },
        { top: '48%', right: '62%', size: 'w-2.5 h-2.5', delay: '0.6s', color: 'bg-emerald-300' },
        { top: '70%', right: '28%', size: 'w-2 h-2', delay: '1.8s', color: 'bg-emerald-500' },
        { top: '72%', right: '52%', size: 'w-3 h-3', delay: '0.4s', color: 'bg-emerald-400' },
        { top: '65%', right: '75%', size: 'w-2 h-2', delay: '2.2s', color: 'bg-emerald-300' },
        { top: '85%', right: '20%', size: 'w-2.5 h-2.5', delay: '1s', color: 'bg-emerald-400' },
        { top: '82%', right: '45%', size: 'w-2 h-2', delay: '0.7s', color: 'bg-emerald-400' },
        { top: '88%', right: '68%', size: 'w-3 h-3', delay: '1.5s', color: 'bg-emerald-500' },
      ].map((node, i) => (
        <div key={i} className={`absolute rounded-full ${node.size} ${node.color}/50`}
          style={{ top: node.top, right: node.right, animation: `slide3NeuralPulse ${3 + i * 0.3}s ease-in-out infinite ${node.delay}` }} />
      ))}

      {/* Central brain glow */}
      <div className="absolute top-1/2 right-[40%] -translate-y-1/2 w-48 h-48 sm:w-64 sm:h-64 rounded-full bg-emerald-300/10 blur-xl"
        style={{ animation: 'slide3BrainPulse 4s ease-in-out infinite' }} />
      <div className="absolute top-1/2 right-[40%] -translate-y-1/2 w-32 h-32 sm:w-44 sm:h-44 rounded-full bg-emerald-400/8 blur-lg"
        style={{ animation: 'slide3BrainPulse 3s ease-in-out infinite 0.5s' }} />

      {/* Concentric rings */}
      <div className="absolute top-1/2 right-[40%] -translate-y-1/2 w-56 h-56 sm:w-72 sm:h-72 rounded-full border border-emerald-200/25"
        style={{ animation: 'slide3BrainRing 5s ease-in-out infinite' }} />
      <div className="absolute top-1/2 right-[40%] -translate-y-1/2 w-72 h-72 sm:w-96 sm:h-96 rounded-full border border-emerald-100/20"
        style={{ animation: 'slide3BrainRing 5s ease-in-out infinite 1.5s' }} />

      {/* Progress bars */}
      <div className="absolute bottom-[15%] right-[15%] w-48 sm:w-56 space-y-3">
        <div className="h-2 rounded-full bg-emerald-100/50 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-400 rounded-full"
            style={{ animation: 'slide3ProgressFill 4s ease-in-out infinite' }} />
        </div>
        <div className="h-2 rounded-full bg-emerald-100/50 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-400 rounded-full"
            style={{ animation: 'slide3ProgressFill 5s ease-in-out infinite 1s' }} />
        </div>
        <div className="h-2 rounded-full bg-emerald-100/50 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full"
            style={{ animation: 'slide3ProgressFill 6s ease-in-out infinite 2s' }} />
        </div>
      </div>

      {/* Neural connection SVG */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 600" preserveAspectRatio="none" opacity="0.15">
        <line x1="200" y1="100" x2="350" y2="200" stroke="#10B981" strokeWidth="1" strokeDasharray="4 4"
          style={{ animation: 'slide3ConnectionFlow 3s linear infinite' }} />
        <line x1="350" y1="200" x2="500" y2="150" stroke="#22C55E" strokeWidth="1" strokeDasharray="4 4"
          style={{ animation: 'slide3ConnectionFlow 3s linear infinite 0.5s' }} />
        <line x1="350" y1="200" x2="400" y2="350" stroke="#10B981" strokeWidth="1" strokeDasharray="4 4"
          style={{ animation: 'slide3ConnectionFlow 3s linear infinite 1s' }} />
        <line x1="500" y1="150" x2="600" y2="300" stroke="#22C55E" strokeWidth="1" strokeDasharray="4 4"
          style={{ animation: 'slide3ConnectionFlow 3s linear infinite 1.5s' }} />
        <line x1="400" y1="350" x2="600" y2="300" stroke="#10B981" strokeWidth="1" strokeDasharray="4 4"
          style={{ animation: 'slide3ConnectionFlow 3s linear infinite 2s' }} />
      </svg>
    </div>
  );
}

/** Slide 4: "Get 40+ Hours Back Every Week" — Clock + Calendar + Hourglass */
function SlideBackground4() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-yellow-50/40 via-white to-emerald-50/30" />

      {/* Large animated clock */}
      <div className="absolute top-1/2 right-[30%] -translate-y-1/2 w-48 h-48 sm:w-64 sm:h-64">
        <svg viewBox="0 0 100 100" className="w-full h-full">
          {/* Clock face */}
          <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(22,163,74,0.15)" strokeWidth="2" />
          <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(22,163,74,0.08)" strokeWidth="1" />
          {/* Hour markers */}
          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i * 30 - 90) * (Math.PI / 180);
            const x1 = 50 + 38 * Math.cos(angle);
            const y1 = 50 + 38 * Math.sin(angle);
            const x2 = 50 + 42 * Math.cos(angle);
            const y2 = 50 + 42 * Math.sin(angle);
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(22,163,74,0.3)" strokeWidth="1.5" />;
          })}
          {/* Hour hand */}
          <line x1="50" y1="50" x2="50" y2="25" stroke="rgba(22,163,74,0.6)" strokeWidth="3" strokeLinecap="round"
            style={{ transformOrigin: '50px 50px', animation: 'slide4ClockHand 4s linear infinite' }} />
          {/* Minute hand */}
          <line x1="50" y1="50" x2="50" y2="18" stroke="rgba(22,163,74,0.4)" strokeWidth="2" strokeLinecap="round"
            style={{ transformOrigin: '50px 50px', animation: 'slide4ClockHand 12s linear infinite' }} />
          {/* Center dot */}
          <circle cx="50" cy="50" r="2.5" fill="rgba(22,163,74,0.6)" />
        </svg>
      </div>

      {/* Outer spinning ring */}
      <div className="absolute top-1/2 right-[30%] -translate-y-1/2 w-56 h-56 sm:w-72 sm:h-72 opacity-15">
        <svg viewBox="0 0 100 100" className="w-full h-full" style={{ animation: 'spin 12s linear infinite' }}>
          <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(251, 191, 36, 0.4)" strokeWidth="1" strokeDasharray="4 6" />
        </svg>
      </div>

      {/* Calendar flip animation */}
      <div className="absolute top-[15%] right-[55%] w-16 h-20 sm:w-20 sm:h-24 bg-white/70 rounded-xl border border-emerald-200/30 shadow-lg flex flex-col items-center justify-center"
        style={{ animation: 'slide4CalendarFlip 4s ease-in-out infinite' }}>
        <div className="w-full h-5 bg-emerald-500/20 rounded-t-xl flex items-center justify-center">
          <span className="text-emerald-700/50 text-[8px] sm:text-[10px] font-bold">HRS</span>
        </div>
        <span className="text-emerald-800/60 text-lg sm:text-2xl font-bold">40+</span>
      </div>

      {/* Counter animation */}
      <div className="absolute bottom-[20%] right-[55%] flex items-baseline gap-1">
        <span className="text-3xl sm:text-4xl font-bold text-emerald-700/30" style={{ animation: 'slide4Counter 3s ease-in-out infinite' }}>40</span>
        <span className="text-sm text-emerald-600/30 font-medium" style={{ animation: 'slide4Counter 3s ease-in-out infinite 0.5s' }}>hrs/week</span>
      </div>

      {/* Hourglass-inspired sand particles */}
      {[
        { top: '30%', right: '60%', delay: '0s' },
        { top: '32%', right: '63%', delay: '0.5s' },
        { top: '28%', right: '58%', delay: '1s' },
        { top: '34%', right: '65%', delay: '1.5s' },
        { top: '29%', right: '61%', delay: '2s' },
      ].map((particle, i) => (
        <div key={i} className="absolute w-1.5 h-1.5 rounded-full bg-emerald-400/50"
          style={{ top: particle.top, right: particle.right, animation: `slide4SandParticle 2s ease-in infinite ${particle.delay}` }} />
      ))}

      {/* Tick dots */}
      <div className="absolute w-2 h-2 rounded-full bg-yellow-400/40 top-[80%] right-[20%]"
        style={{ animation: 'slide4TickPulse 4s ease-in-out infinite' }} />
      <div className="absolute w-2 h-2 rounded-full bg-emerald-400/40 top-[10%] right-[80%]"
        style={{ animation: 'slide4TickPulse 3s ease-in-out infinite 1s' }} />
    </div>
  );
}

/** Slide 5: "Meet Jarvis — Your AI Employee" — Jarvis rings + energy */
function SlideBackground5() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/40 via-white to-emerald-100/30" />

      {/* Jarvis core glow */}
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-28 h-28 sm:w-36 sm:h-36 rounded-full bg-emerald-500/10 blur-xl"
        style={{ animation: 'slide5CoreGlow 3s ease-in-out infinite' }} />

      {/* Concentric expanding rings (Iron Man Jarvis style) */}
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-40 h-40 sm:w-52 sm:h-52 rounded-full border-2 border-emerald-400/20"
        style={{ animation: 'slide5RingExpand 4s ease-in-out infinite' }} />
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-56 h-56 sm:w-72 sm:h-72 rounded-full border border-emerald-300/15"
        style={{ animation: 'slide5RingExpand 4s ease-in-out infinite 0.8s' }} />
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-72 h-72 sm:w-96 sm:h-96 rounded-full border border-emerald-200/10"
        style={{ animation: 'slide5RingExpandAlt 5s ease-in-out infinite 1.5s' }} />
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-80 h-80 sm:w-[28rem] sm:h-[28rem] rounded-full border border-emerald-100/8"
        style={{ animation: 'slide5RingExpandAlt 5s ease-in-out infinite 2.5s' }} />

      {/* AI face outline — futuristic */}
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-24 h-24 sm:w-32 sm:h-32 rounded-full bg-emerald-100/20 border-2 border-emerald-400/15"
        style={{ animation: 'slide5FacePulse 3s ease-in-out infinite' }}>
        {/* Eyes */}
        <div className="absolute top-1/3 left-1/4 w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full bg-emerald-500/40"
          style={{ animation: 'slide5DotPulse 2s ease-in-out infinite' }} />
        <div className="absolute top-1/3 right-1/4 w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full bg-emerald-500/40"
          style={{ animation: 'slide5DotPulse 2s ease-in-out infinite 0.3s' }} />
        {/* Mouth arc */}
        <div className="absolute top-[60%] left-1/3 w-1/3 h-1.5 rounded-full bg-emerald-400/25" />
      </div>

      {/* Circuit board SVG pattern */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 800 600" preserveAspectRatio="none" opacity="0.1">
        {/* Horizontal lines */}
        <line x1="300" y1="150" x2="550" y2="150" stroke="#16A34A" strokeWidth="0.8" strokeDasharray="6 4"
          style={{ animation: 'slide5CircuitFlow 4s linear infinite' }} />
        <line x1="350" y1="250" x2="600" y2="250" stroke="#22C55E" strokeWidth="0.8" strokeDasharray="6 4"
          style={{ animation: 'slide5CircuitFlow 4s linear infinite 1s' }} />
        <line x1="280" y1="350" x2="520" y2="350" stroke="#16A34A" strokeWidth="0.8" strokeDasharray="6 4"
          style={{ animation: 'slide5CircuitFlow 4s linear infinite 2s' }} />
        <line x1="320" y1="450" x2="580" y2="450" stroke="#22C55E" strokeWidth="0.8" strokeDasharray="6 4"
          style={{ animation: 'slide5CircuitFlow 4s linear infinite 3s' }} />
        {/* Vertical connections */}
        <line x1="400" y1="150" x2="400" y2="250" stroke="#16A34A" strokeWidth="0.5" />
        <line x1="500" y1="250" x2="500" y2="350" stroke="#22C55E" strokeWidth="0.5" />
        <line x1="450" y1="350" x2="450" y2="450" stroke="#16A34A" strokeWidth="0.5" />
        {/* Junction dots */}
        <circle cx="400" cy="150" r="2" fill="#16A34A" style={{ animation: 'slide5DotPulse 3s ease-in-out infinite' }} />
        <circle cx="500" cy="250" r="2" fill="#22C55E" style={{ animation: 'slide5DotPulse 3s ease-in-out infinite 0.5s' }} />
        <circle cx="450" cy="350" r="2" fill="#16A34A" style={{ animation: 'slide5DotPulse 3s ease-in-out infinite 1s' }} />
      </svg>

      {/* Energy particles floating up */}
      {[
        { right: '25%', delay: '0s', duration: '3s' },
        { right: '35%', delay: '0.8s', duration: '3.5s' },
        { right: '45%', delay: '1.6s', duration: '2.8s' },
        { right: '55%', delay: '0.4s', duration: '3.2s' },
        { right: '65%', delay: '2s', duration: '3s' },
        { right: '30%', delay: '2.5s', duration: '2.5s' },
        { right: '50%', delay: '1.2s', duration: '3.8s' },
        { right: '60%', delay: '3s', duration: '2.6s' },
      ].map((particle, i) => (
        <div key={i} className="absolute w-1.5 h-1.5 rounded-full bg-emerald-400/60"
          style={{ bottom: '20%', right: particle.right, animation: `slide5EnergyParticle ${particle.duration} ease-out infinite ${particle.delay}` }} />
      ))}

      {/* Deep green ambient glow */}
      <div className="absolute top-1/2 right-[35%] -translate-y-1/2 w-64 h-64 sm:w-80 sm:h-80 rounded-full bg-emerald-600/5 blur-[100px]" />
    </div>
  );
}

const slideBackgrounds = [
  SlideBackground1,
  SlideBackground2,
  SlideBackground3,
  SlideBackground4,
  SlideBackground5,
];

export default function FeatureCarousel() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [progressKey, setProgressKey] = useState(0);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => { setIsMounted(true); }, []);

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
    setProgressKey((prev) => prev + 1);
  }, []);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
    setProgressKey((prev) => prev + 1);
  }, []);

  const goToSlide = useCallback((index: number) => {
    setCurrentSlide(index);
    setProgressKey((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (!isMounted || isPaused) return;
    const interval = setInterval(nextSlide, 6000);
    return () => clearInterval(interval);
  }, [isMounted, isPaused, nextSlide]);

  useEffect(() => {
    const handleVisibility = () => setIsPaused(document.hidden);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') prevSlide();
      else if (e.key === 'ArrowRight') nextSlide();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextSlide, prevSlide]);

  return (
    <section className="relative w-full" aria-label="Feature carousel" role="region">
      <div className="slide-full-width relative">
        <div
          className="relative h-[60vh] sm:h-[65vh] md:h-[70vh] overflow-hidden"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          {slides.map((slide, index) => {
            const BackgroundComponent = slideBackgrounds[index];
            return (
              <div
                key={slide.id}
                className="carousel-slide absolute inset-0"
                style={{ opacity: index === currentSlide ? 1 : 0, zIndex: index === currentSlide ? 1 : 0 }}
                role="group"
                aria-roledescription="slide"
                aria-label={`Slide ${index + 1} of ${slides.length}: ${slide.title}`}
              >
                <BackgroundComponent />
                {/* Light overlay for text readability */}
                <div className="absolute inset-0 bg-gradient-to-r from-white/95 via-white/70 to-white/30" />
                <div className="absolute inset-0 bg-gradient-to-t from-white/80 via-transparent to-white/20" />

                {/* Accent Glow */}
                <div
                  className="absolute bottom-0 left-1/4 w-96 h-96 rounded-full blur-[120px] pointer-events-none"
                  style={{ background: slide.accentGlow }}
                />

                {/* Content */}
                <div className="relative z-10 h-full flex flex-col justify-center px-6 sm:px-10 md:px-16 lg:px-24 xl:px-32 max-w-2xl">
                  <span className="text-xs sm:text-sm font-mono text-gray-400 tracking-widest mb-4 sm:mb-6">
                    {slide.slideNumber}
                  </span>
                  <p className="text-sm sm:text-base md:text-lg text-emerald-700 font-medium mb-3 sm:mb-4 tracking-wide">
                    {slide.subtitle}
                  </p>
                  <h2 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 leading-tight mb-4 sm:mb-6 text-balance">
                    {slide.title}
                  </h2>
                  <p className="text-base sm:text-lg md:text-xl text-gray-500 max-w-lg leading-relaxed">
                    {slide.description}
                  </p>
                  {/* Micro-commitment CTA nudge */}
                  <div className="mt-6 sm:mt-8 flex items-center gap-2 text-emerald-600 hover:text-emerald-700 transition-colors duration-300 cursor-pointer group">
                    <span className="text-sm sm:text-base font-medium">See How It Works</span>
                    <svg className="w-4 h-4 cta-arrow-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                    </svg>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Bottom Controls */}
          <div className="absolute bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-white/70 to-transparent pt-16 pb-5 sm:pb-6 md:pb-8 px-4 sm:px-6">
            <div className="flex items-center justify-between max-w-7xl mx-auto">
              <button
                onClick={prevSlide}
                className="flex-shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-white/80 hover:bg-gray-100 backdrop-blur-sm border border-gray-200 hover:border-gray-300 text-gray-600 hover:text-gray-900 flex items-center justify-center transition-all duration-300 focus-visible-ring shadow-sm"
                aria-label="Previous slide"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>

              <div className="flex flex-col items-center gap-2 sm:gap-3">
                <div className="flex items-center gap-2" role="tablist" aria-label="Slide navigation">
                  {slides.map((_, index) => (
                    <button
                      key={index}
                      onClick={() => goToSlide(index)}
                      className={`rounded-full transition-all duration-500 focus-visible-ring ${
                        index === currentSlide
                          ? 'w-8 h-2.5 bg-emerald-500'
                          : 'w-2.5 h-2.5 bg-gray-300 hover:bg-gray-400'
                      }`}
                      aria-label={`Go to slide ${index + 1}`}
                      aria-selected={index === currentSlide}
                      role="tab"
                    />
                  ))}
                </div>
                <div className="w-48 sm:w-56 h-0.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    key={progressKey}
                    className={`h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full ${
                      isPaused ? '' : 'progress-animate'
                    }`}
                    style={isPaused ? { width: '0%' } : undefined}
                  />
                </div>
              </div>

              <button
                onClick={nextSlide}
                className="flex-shrink-0 w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-white/80 hover:bg-gray-100 backdrop-blur-sm border border-gray-200 hover:border-gray-300 text-gray-600 hover:text-gray-900 flex items-center justify-center transition-all duration-300 focus-visible-ring shadow-sm"
                aria-label="Next slide"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
