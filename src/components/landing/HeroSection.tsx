'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { X, Check, MessageSquare } from 'lucide-react';

/**
 * HeroSection - Dark premium theme with orange animated background
 */

const humanSupportItems = [
  { value: '$50,000/year per agent', note: '3 agents = $150,000', negative: true },
  { value: 'Works only 8 hours/day', negative: true },
  { value: '2-3 months training needed', negative: true },
  { value: 'Takes sick days, vacations, quits', negative: true },
  { value: 'Different answers to same question', negative: true },
  { value: 'Mood swings affect customers', negative: true },
  { value: '"I don\'t know, let me check with my manager"', quote: true, negative: true },
];

const parwaItems = [
  { value: 'Starting at $999/month', note: '92% cost reduction', highlight: true },
  { value: '24/7/365 — while you sleep', highlight: true },
  { value: 'Instant from Day 1 — zero training', highlight: true },
  { value: 'Never takes a day off', highlight: true },
  { value: 'Always consistent, always professional', highlight: true },
  { value: 'Automatic resolution — zero effort', highlight: true },
  { value: '"I know the answer, here\'s the solution"', quote: true, highlight: true },
];

export default function HeroSection() {
  const [isInView, setIsInView] = useState(false);
  const [visibleCards, setVisibleCards] = useState<number[]>([]);
  const [counterValue, setCounterValue] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const sectionRef = useRef<HTMLElement>(null);
  const router = useRouter();

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsInView(true); },
      { threshold: 0.15 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!sectionRef.current) return;
      const rect = sectionRef.current.getBoundingClientRect();
      setMousePos({
        x: ((e.clientX - rect.left) / rect.width - 0.5) * 2,
        y: ((e.clientY - rect.top) / rect.height - 0.5) * 2,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    if (!isInView) return;
    const t1 = setTimeout(() => setVisibleCards([0]), 150);
    const t2 = setTimeout(() => setVisibleCards([0, 1]), 400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [isInView]);

  useEffect(() => {
    if (!isInView) return;
    let current = 0;
    const target = 92;
    const stepTime = 2000 / target;
    const timer = setInterval(() => {
      current += 1;
      setCounterValue(current);
      if (current >= target) clearInterval(timer);
    }, stepTime);
    return () => clearInterval(timer);
  }, [isInView]);

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden"
    >
      {/* Animated Background */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {/* Floating orbs with parallax */}
        <div
          className="absolute w-[400px] h-[400px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,127,17,0.2) 0%, rgba(255,127,17,0.03) 60%, transparent 80%)',
            top: '20%',
            left: '10%',
            transform: `translate(${mousePos.x * 12}px, ${mousePos.y * 8}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat1 10s ease-in-out infinite',
          }}
        />
        <div
          className="absolute w-[350px] h-[350px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,215,0,0.08) 0%, rgba(255,215,0,0.01) 60%, transparent 80%)',
            top: '60%',
            right: '5%',
            transform: `translate(${mousePos.x * -15}px, ${mousePos.y * -10}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat2 12s ease-in-out infinite',
          }}
        />
        <div
          className="absolute w-[250px] h-[250px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,159,68,0.12) 0%, rgba(255,159,68,0.02) 60%, transparent 80%)',
            top: '10%',
            right: '30%',
            transform: `translate(${mousePos.x * 8}px, ${mousePos.y * 6}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat3 9s ease-in-out infinite',
          }}
        />

        {/* Particle grid dots */}
        <div className="absolute inset-0" style={{ opacity: 0.3 }}>
          {Array.from({ length: 20 }).map((_, i) => {
            const row = Math.floor(i / 5);
            const col = i % 5;
            return (
              <div
                key={i}
                className="absolute w-1 h-1 rounded-full bg-orange-400"
                style={{
                  left: `${(col + 0.5) * 20}%`,
                  top: `${(row + 0.5) * 20}%`,
                  animation: `jarvisDotPulse 3s ease-in-out infinite ${(i * 0.4) % 4}s`,
                  opacity: 0,
                }}
              />
            );
          })}
        </div>

        {/* Rising particles */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={`particle-${i}`}
            className="absolute w-1.5 h-1.5 rounded-full bg-orange-400/50"
            style={{
              left: `${12 + i * 15}%`,
              animation: `jarvisParticleRise ${7 + i * 0.6}s linear infinite ${i * 0.9}s`,
              opacity: 0,
            }}
          />
        ))}
      </div>

      {/* Content */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14 md:py-16 lg:py-20">
        {/* Section Header */}
        <div
          className={`text-center mb-8 sm:mb-10 lg:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-5 text-balance">
            Human Support vs <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">PARWA AI</span>
          </h2>
          
          <div className="inline-flex items-center gap-3 sm:gap-4 mt-6 mb-4 px-5 sm:px-6 py-3 sm:py-4 rounded-2xl border border-orange-500/20 backdrop-blur-sm" style={{ background: 'rgba(255,127,17,0.08)' }}>
            <div className="flex items-baseline gap-1">
              <span className={`text-3xl sm:text-4xl lg:text-5xl font-bold text-orange-300 ${counterValue === 92 ? 'counter-bounce' : ''}`}>
                {counterValue}%
              </span>
            </div>
            <span className="text-sm sm:text-base text-orange-200/50 font-medium">cost reduction</span>
            <div className="hidden sm:flex items-center gap-2 ml-2 pl-3 border-l border-orange-500/20">
              <span className="text-sm text-rose-400/70 font-semibold line-through decoration-2">$150,000/yr</span>
              <svg className="w-4 h-4 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              <span className="text-sm text-orange-300 font-semibold">$999/mo</span>
            </div>
          </div>
          
          {/* Social proof anchor badge */}
          <div className="flex items-center justify-center gap-2 mt-3 mb-2">
            <div className="relative w-2 h-2">
              <div className="absolute inset-0 rounded-full bg-orange-400 pulse-live" />
              <div className="absolute inset-0 rounded-full bg-orange-400" />
            </div>
            <span className="text-xs sm:text-sm text-orange-200/40 font-medium">Based on 2,400+ businesses using PARWA daily</span>
          </div>
          
          <p className="text-base sm:text-lg text-orange-100/40 max-w-xl mx-auto px-4">
            The numbers don&apos;t lie. See the real comparison.
          </p>
        </div>

        {/* Comparison Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8 max-w-6xl mx-auto">
          {/* Human Support Card */}
          <div
            className={`rounded-2xl p-6 sm:p-8 lg:p-10 relative overflow-hidden transition-all duration-700 ${
              visibleCards.includes(0) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
            }`}
            style={{
              background: 'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.01) 100%)',
              border: '1px solid rgba(244,63,94,0.25)',
              boxShadow: '0 25px 50px rgba(0,0,0,0.2), 0 0 60px rgba(244,63,94,0.05)',
            }}
          >
            <div className="absolute -top-20 -right-20 w-48 h-48 rounded-full blur-[80px] pointer-events-none" style={{ background: 'rgba(244,63,94,0.08)' }} />
            <div className="relative flex items-center gap-3 mb-8">
              <div className="w-11 h-11 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
                <X className="w-5 h-5 text-rose-400" />
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-white">Human Support</h3>
              <span className="hidden sm:inline-flex ml-auto px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold tracking-wide">
                BEFORE
              </span>
            </div>
            <ul className="relative space-y-4 sm:space-y-5">
              {humanSupportItems.map((item, index) => (
                <li key={index} className="flex flex-col gap-0.5 border-b border-white/5 last:border-0 pb-4 sm:pb-5 last:pb-0">
                  <div className="flex items-start gap-3">
                    <X className="w-4 h-4 text-rose-400 mt-0.5 flex-shrink-0" />
                    <span className={`text-sm sm:text-base ${
                      item.quote ? 'text-rose-300/80 italic font-medium' : 'text-gray-300'
                    }`}>
                      {item.value}
                    </span>
                  </div>
                  {item.note && (
                    <span className="text-xs text-rose-400/60 ml-7 font-medium">{item.note}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* PARWA AI Card */}
          <div
            className={`rounded-2xl p-6 sm:p-8 lg:p-10 relative overflow-hidden transition-all duration-700 ${
              visibleCards.includes(1) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
            }`}
            style={{
              background: 'linear-gradient(135deg, rgba(255,127,17,0.08) 0%, rgba(255,127,17,0.02) 100%)',
              border: '1px solid rgba(255,127,17,0.3)',
              boxShadow: '0 25px 50px rgba(0,0,0,0.2), 0 0 80px rgba(255,127,17,0.08), inset 0 1px 0 rgba(255,255,255,0.05)',
            }}
          >
            <div className="absolute -top-20 -right-20 w-48 h-48 rounded-full blur-[80px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.15)' }} />
            <div className="relative flex items-center gap-3 mb-8">
              <div className="w-11 h-11 rounded-xl bg-orange-500/10 border border-orange-500/25 flex items-center justify-center">
                <Check className="w-5 h-5 text-orange-400" />
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-white">PARWA AI</h3>
              <span className="hidden sm:inline-flex ml-auto px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/25 text-orange-300 text-xs font-semibold tracking-wide recommended-glow">
                ✨ RECOMMENDED
              </span>
            </div>
            <ul className="relative space-y-4 sm:space-y-5">
              {parwaItems.map((item, index) => (
                <li key={index} className="flex flex-col gap-0.5 border-b border-orange-500/10 last:border-0 pb-4 sm:pb-5 last:pb-0">
                  <div className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-orange-400 mt-0.5 flex-shrink-0" />
                    <span className={`text-sm sm:text-base ${
                      item.quote
                        ? 'text-orange-300 italic font-medium'
                        : item.highlight
                        ? 'text-gray-100 font-medium'
                        : 'text-gray-300'
                    }`}>
                      {item.value}
                    </span>
                  </div>
                  {item.note && (
                    <span className="text-xs text-orange-400/70 ml-7 font-semibold">{item.note}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom text */}
        <div
          className={`text-center mt-6 sm:mt-8 lg:mt-10 transition-all duration-700 delay-500 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <p className="text-lg sm:text-xl md:text-2xl font-semibold text-gray-100">
            The math is simple.{' '}
            <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">The choice is yours.</span>
          </p>
          <p className="mt-3 text-sm sm:text-base text-orange-100/30 font-medium">
            Every day without automation costs you{' '}
            <span className="font-bold text-base sm:text-lg text-rose-300/80">$410</span>
            <span className="text-orange-100/30"> in wasted support hours</span>
          </p>

          {/* Phase 9: Get Started with Jarvis CTA */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                localStorage.setItem('parwa_jarvis_context', JSON.stringify({ source: 'landing_page' }));
                router.push('/onboarding');
              }}
              className="flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-500/25 hover:from-orange-400 hover:to-orange-300 hover:shadow-orange-500/40 hover:-translate-y-0.5 active:translate-y-0 transition-all duration-300 focus-visible-ring"
            >
              <MessageSquare className="w-4.5 h-4.5" />
              Get Started with Jarvis
            </button>
          </div>
        </div>
      </div>

      {/* Keyframes */}
      <style jsx global>{`
        @keyframes jarvisOrbFloat1 {
          0%, 100% { transform: translateY(0) scale(1); }
          33% { transform: translateY(-25px) scale(1.04); }
          66% { transform: translateY(12px) scale(0.97); }
        }
        @keyframes jarvisOrbFloat2 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-35px) scale(1.06); }
        }
        @keyframes jarvisOrbFloat3 {
          0%, 100% { transform: translateY(0) scale(1); }
          33% { transform: translateY(-18px) scale(1.02); }
          66% { transform: translateY(20px) scale(0.96); }
        }
        @keyframes jarvisDotPulse {
          0%, 100% { opacity: 0; transform: scale(0.5); }
          50% { opacity: 0.8; transform: scale(1.2); }
        }
        @keyframes jarvisParticleRise {
          0% { transform: translateY(100%) translateX(0); opacity: 0; }
          10% { opacity: 0.6; }
          90% { opacity: 0.6; }
          100% { transform: translateY(-100vh) translateX(25px); opacity: 0; }
        }
      `}</style>
    </section>
  );
}
