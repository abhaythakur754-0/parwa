'use client';

import { useState, useEffect, useRef } from 'react';
import { X, Check } from 'lucide-react';

/**
 * HeroSection - Light green theme with REDUCED gaps
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
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsInView(true); },
      { threshold: 0.15 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
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
      className="relative overflow-hidden bg-gradient-to-b from-[#F0FDF4] to-white"
    >
      {/* Background ambient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 left-0 w-80 h-80 bg-red-100/50 rounded-full blur-[100px]" />
        <div className="absolute top-1/3 right-0 w-80 h-80 bg-emerald-200/30 rounded-full blur-[100px]" />
      </div>

      {/* REDUCED PADDING — was py-16 sm:py-20 md:py-28 lg:py-36 */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14 md:py-16 lg:py-20">
        {/* Section Header */}
        <div
          className={`text-center mb-8 sm:mb-10 lg:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-4 sm:mb-5 text-balance">
            Human Support vs <span className="text-gradient">PARWA AI</span>
          </h2>
          
          <div className="inline-flex items-center gap-3 sm:gap-4 mt-6 mb-4 px-5 sm:px-6 py-3 sm:py-4 rounded-2xl bg-emerald-50 border border-emerald-300/50 animate-pulse-slow">
            <div className="flex items-baseline gap-1">
              <span className={`text-3xl sm:text-4xl lg:text-5xl font-bold text-emerald-800 ${counterValue === 92 ? 'counter-bounce' : ''}`}>
                {counterValue}%
              </span>
            </div>
            <span className="text-sm sm:text-base text-gray-600 font-medium">cost reduction</span>
            <div className="hidden sm:flex items-center gap-2 ml-2 pl-3 border-l border-gray-200">
              <span className="text-sm text-red-500 font-semibold line-through decoration-2">$150,000/yr</span>
              <svg className="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
              <span className="text-sm text-gray-700 font-semibold">$999/mo</span>
            </div>
          </div>
          
          {/* Social proof anchor badge */}
          <div className="flex items-center justify-center gap-2 mt-3 mb-2">
            <div className="relative w-2 h-2">
              <div className="absolute inset-0 rounded-full bg-emerald-400 pulse-live" />
              <div className="absolute inset-0 rounded-full bg-emerald-500" />
            </div>
            <span className="text-xs sm:text-sm text-gray-400 font-medium">Based on 2,400+ businesses using PARWA daily</span>
          </div>
          
          <p className="text-base sm:text-lg text-gray-500 max-w-xl mx-auto px-4">
            The numbers don&apos;t lie. See the real comparison.
          </p>
        </div>

        {/* Comparison Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8 max-w-6xl mx-auto">
          {/* Human Support Card */}
          <div
            className={`rounded-2xl border-2 border-red-300 bg-red-50/50 backdrop-blur-sm p-6 sm:p-8 lg:p-10 transition-all duration-700 shadow-lg shadow-red-100/50 ${
              visibleCards.includes(0) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
            }`}
          >
            <div className="flex items-center gap-3 mb-8">
              <div className="w-11 h-11 rounded-xl bg-red-100 flex items-center justify-center">
                <X className="w-5 h-5 text-red-500" />
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-gray-900">Human Support</h3>
              <span className="hidden sm:inline-flex ml-auto px-3 py-1 rounded-full bg-red-50 border border-red-200 text-red-500 text-xs font-semibold tracking-wide">
                BEFORE
              </span>
            </div>
            <ul className="space-y-4 sm:space-y-5">
              {humanSupportItems.map((item, index) => (
                <li key={index} className="flex flex-col gap-0.5 border-b border-gray-200 last:border-0 pb-4 sm:pb-5 last:pb-0">
                  <div className="flex items-start gap-3">
                    <X className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                    <span className={`text-sm sm:text-base ${
                      item.quote ? 'text-red-600 italic font-medium' : 'text-gray-600'
                    }`}>
                      {item.value}
                    </span>
                  </div>
                  {item.note && (
                    <span className="text-xs text-red-400/80 ml-7 font-medium">{item.note}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* PARWA AI Card */}
          <div
            className={`rounded-2xl border-2 border-emerald-300 bg-gradient-to-br from-emerald-50/80 to-white backdrop-blur-sm p-6 sm:p-8 lg:p-10 relative overflow-hidden transition-all duration-700 shadow-xl shadow-emerald-200/30 ${
              visibleCards.includes(1) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'
            }`}
          >
            <div className="absolute -top-20 -right-20 w-48 h-48 bg-emerald-200/40 rounded-full blur-[80px] pointer-events-none" />
            <div className="relative flex items-center gap-3 mb-8">
              <div className="w-11 h-11 rounded-xl bg-emerald-100 flex items-center justify-center">
                <Check className="w-5 h-5 text-emerald-700" />
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-gray-900">PARWA AI</h3>
              <span className="hidden sm:inline-flex ml-auto px-3 py-1 rounded-full bg-emerald-100 border border-emerald-300/50 text-emerald-700 text-xs font-semibold tracking-wide recommended-glow">
                ✨ RECOMMENDED
              </span>
            </div>
            <ul className="relative space-y-4 sm:space-y-5">
              {parwaItems.map((item, index) => (
                <li key={index} className="flex flex-col gap-0.5 border-b border-emerald-100 last:border-0 pb-4 sm:pb-5 last:pb-0">
                  <div className="flex items-start gap-3">
                    <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                    <span className={`text-sm sm:text-base ${
                      item.quote
                        ? 'text-emerald-700 italic font-medium'
                        : item.highlight
                        ? 'text-gray-800 font-medium'
                        : 'text-gray-600'
                    }`}>
                      {item.value}
                    </span>
                  </div>
                  {item.note && (
                    <span className="text-xs text-emerald-600 ml-7 font-semibold">{item.note}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom text — REDUCED MARGIN */}
        <div
          className={`text-center mt-6 sm:mt-8 lg:mt-10 transition-all duration-700 delay-500 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <p className="text-lg sm:text-xl md:text-2xl font-semibold text-gray-700">
            The math is simple.{' '}
            <span className="text-gradient">The choice is yours.</span>
          </p>
          <p className="mt-3 text-sm sm:text-base text-gray-400 font-medium">
            ⏳ Every day without automation costs you{' '}
            <span className="loss-aversion-text font-bold text-base sm:text-lg">$410</span>
            <span className="text-gray-400"> in wasted support hours</span>
          </p>
        </div>
      </div>
    </section>
  );
}
