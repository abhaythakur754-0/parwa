'use client';

import { useState, useEffect, useCallback } from 'react';

/**
 * FeatureCarousel Component
 * 
 * Netflix/Prime Video style carousel with 5 slides.
 * Positioned as the FIRST thing users see (below navigation bar).
 * 
 * Slides are designed with psychological triggers:
 * 1. Control Everything by Chat - SIMPLICITY
 * 2. No Tech Skills Needed - FEAR REMOVAL
 * 3. Self-Learning AI - EFFORT REDUCTION
 * 4. Eliminates 90% Daily Work - TIME FREEDOM
 * 5. Your Iron Man Jarvis - ASPIRATION
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3.3
 */

interface Slide {
  id: number;
  icon: string;
  title: string;
  description: string;
  psychologicalTrigger: string;
  gradient: string;
}

const slides: Slide[] = [
  {
    id: 1,
    icon: '💬',
    title: 'Control Everything by Chat',
    description: 'Just type and control - no complex dashboards. No training needed. Just talk.',
    psychologicalTrigger: 'SIMPLICITY',
    gradient: 'from-primary-500 to-primary-700',
  },
  {
    id: 2,
    icon: '🎯',
    title: 'No Tech Skills Needed',
    description: 'Not technical? Never done customer care? Perfect. Jarvis handles everything. You just focus on your business.',
    psychologicalTrigger: 'FEAR REMOVAL',
    gradient: 'from-success-500 to-success-700',
  },
  {
    id: 3,
    icon: '🧠',
    title: 'Self-Learning AI',
    description: 'Upload your docs. Jarvis learns. Every question makes it smarter. Zero manual training needed.',
    psychologicalTrigger: 'EFFORT REDUCTION',
    gradient: 'from-purple-500 to-purple-700',
  },
  {
    id: 4,
    icon: '⚡',
    title: 'Eliminates 90% Daily Work',
    description: '90% of support tickets are repetitive. Jarvis handles them all. You get 40+ hours back every week.',
    psychologicalTrigger: 'TIME FREEDOM',
    gradient: 'from-warning-500 to-warning-700',
  },
  {
    id: 5,
    icon: '🦾',
    title: 'Your Iron Man Jarvis',
    description: "Like Tony Stark's Jarvis, but for your business. Your personal AI officer that never sleeps, never complains, and always delivers.",
    psychologicalTrigger: 'ASPIRATION',
    gradient: 'from-primary-600 to-purple-600',
  },
];

export default function FeatureCarousel() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  }, []);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  }, []);

  // Auto-play carousel
  useEffect(() => {
    if (!isAutoPlaying) return;

    const interval = setInterval(nextSlide, 5000);
    return () => clearInterval(interval);
  }, [isAutoPlaying, nextSlide]);

  const handleUserInteraction = () => {
    setIsAutoPlaying(false);
    // Resume auto-play after 10 seconds of inactivity
    setTimeout(() => setIsAutoPlaying(true), 10000);
  };

  return (
    <section className="relative bg-secondary-900 overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-10">
        <div className="absolute inset-0" style={{
          backgroundImage: `radial-gradient(circle at 25% 25%, rgba(255,255,255,0.1) 0%, transparent 50%),
                           radial-gradient(circle at 75% 75%, rgba(255,255,255,0.1) 0%, transparent 50%)`,
        }} />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
        {/* Main Carousel */}
        <div 
          className="relative"
          onMouseEnter={handleUserInteraction}
          onTouchStart={handleUserInteraction}
        >
          {/* Slides Container */}
          <div className="overflow-hidden rounded-2xl">
            <div
              className="flex transition-transform duration-500 ease-out"
              style={{ transform: `translateX(-${currentSlide * 100}%)` }}
            >
              {slides.map((slide) => (
                <div
                  key={slide.id}
                  className="w-full flex-shrink-0"
                >
                  <div className={`bg-gradient-to-br ${slide.gradient} p-8 md:p-16 min-h-[300px] md:min-h-[400px] flex flex-col justify-center items-center text-center`}>
                    <span className="text-6xl md:text-8xl mb-6">{slide.icon}</span>
                    <h2 className="text-2xl md:text-4xl font-bold text-white mb-4">
                      {slide.title}
                    </h2>
                    <p className="text-lg md:text-xl text-white/90 max-w-2xl">
                      {slide.description}
                    </p>
                    <span className="mt-6 px-4 py-1.5 bg-white/20 rounded-full text-sm text-white/80 backdrop-blur-sm">
                      {slide.psychologicalTrigger}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Navigation Arrows */}
          <button
            onClick={() => {
              handleUserInteraction();
              prevSlide();
            }}
            className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white backdrop-blur-sm transition-colors"
            aria-label="Previous slide"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={() => {
              handleUserInteraction();
              nextSlide();
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center rounded-full bg-white/10 hover:bg-white/20 text-white backdrop-blur-sm transition-colors"
            aria-label="Next slide"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Dots Indicator */}
        <div className="flex justify-center gap-2 mt-8">
          {slides.map((_, index) => (
            <button
              key={index}
              onClick={() => {
                handleUserInteraction();
                setCurrentSlide(index);
              }}
              className={`w-3 h-3 rounded-full transition-all duration-300 ${
                index === currentSlide
                  ? 'bg-white w-8'
                  : 'bg-white/40 hover:bg-white/60'
              }`}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>

        {/* Slide Preview (Desktop) */}
        <div className="hidden lg:flex justify-center gap-4 mt-8">
          {slides.map((slide, index) => (
            <button
              key={slide.id}
              onClick={() => {
                handleUserInteraction();
                setCurrentSlide(index);
              }}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-all duration-300 ${
                index === currentSlide
                  ? 'bg-white/20 text-white'
                  : 'bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80'
              }`}
            >
              <span className="text-2xl">{slide.icon}</span>
              <span className="text-sm font-medium truncate max-w-[150px]">
                {slide.title}
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
