'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * FeatureCarousel Component
 * 
 * Netflix/Prime Video style carousel with 5 slides.
 * Dark premium theme with SVG icons (NO emojis).
 * 
 * Features:
 * - Touch swipe support for mobile
 * - Keyboard navigation (arrow keys)
 * - Auto-play with pause on interaction
 * - Scroll-triggered animations
 * - Hydration-safe localStorage
 * 
 * Slides with psychological triggers:
 * 1. Control Everything by Chat - SIMPLICITY
 * 2. No Tech Skills Needed - FEAR REMOVAL
 * 3. Self-Learning AI - EFFORT REDUCTION
 * 4. Eliminates 90% Daily Work - TIME FREEDOM
 * 5. Your Iron Man Jarvis - ASPIRATION
 */

interface Slide {
  id: number;
  icon: React.ReactNode;
  title: string;
  description: string;
  psychologicalTrigger: string;
  accentColor: string;
}

// SVG Icons - NO EMOJIS
const ChatIcon = () => (
  <svg className="w-12 h-12 sm:w-16 sm:h-16 md:w-20 md:h-20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
  </svg>
);

const ShieldIcon = () => (
  <svg className="w-12 h-12 sm:w-16 sm:h-16 md:w-20 md:h-20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);

const BrainIcon = () => (
  <svg className="w-12 h-12 sm:w-16 sm:h-16 md:w-20 md:h-20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
  </svg>
);

const BoltIcon = () => (
  <svg className="w-12 h-12 sm:w-16 sm:h-16 md:w-20 md:h-20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
  </svg>
);

const CpuChipIcon = () => (
  <svg className="w-12 h-12 sm:w-16 sm:h-16 md:w-20 md:h-20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
  </svg>
);

const slides: Slide[] = [
  {
    id: 1,
    icon: <ChatIcon />,
    title: 'Control Everything by Chat',
    description: 'Just type and control - no complex dashboards. No training needed. Simply tell Jarvis what you need.',
    psychologicalTrigger: 'SIMPLICITY',
    accentColor: 'teal',
  },
  {
    id: 2,
    icon: <ShieldIcon />,
    title: 'No Tech Skills Needed',
    description: 'Not technical? Never done customer care? Perfect. Jarvis handles everything. You focus on your business.',
    psychologicalTrigger: 'FEAR REMOVAL',
    accentColor: 'navy',
  },
  {
    id: 3,
    icon: <BrainIcon />,
    title: 'Self-Learning AI',
    description: 'Upload your docs. Jarvis learns. Every question makes it smarter. Zero manual training required.',
    psychologicalTrigger: 'EFFORT REDUCTION',
    accentColor: 'charcoal',
  },
  {
    id: 4,
    icon: <BoltIcon />,
    title: 'Eliminates 90% Daily Work',
    description: '90% of support tickets are repetitive. Jarvis handles them all. Get 40+ hours back every week.',
    psychologicalTrigger: 'TIME FREEDOM',
    accentColor: 'orange',
  },
  {
    id: 5,
    icon: <CpuChipIcon />,
    title: 'Your Iron Man Jarvis',
    description: "Like Tony Stark's Jarvis, but for your business. Your personal AI officer that never sleeps and always delivers.",
    psychologicalTrigger: 'ASPIRATION',
    accentColor: 'gold',
  },
];

export default function FeatureCarousel() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const [isInView, setIsInView] = useState(false);
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchEnd, setTouchEnd] = useState<number | null>(null);
  const sectionRef = useRef<HTMLElement>(null);
  const userPausedRef = useRef(false);

  // Minimum swipe distance (in px)
  const minSwipeDistance = 50;

  // Hydration-safe initialization
  useEffect(() => {
    setIsMounted(true);
    // Read from localStorage after mount to avoid hydration mismatch
    try {
      const saved = localStorage.getItem('parwa_carousel_slide');
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= 0 && parsed < slides.length) {
          setCurrentSlide(parsed);
        }
      }
    } catch {
      // localStorage might be unavailable
    }
  }, []);

  // Intersection Observer for scroll-triggered animation
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsInView(entry.isIntersecting);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) {
      observer.observe(sectionRef.current);
    }

    return () => observer.disconnect();
  }, []);

  // Save slide to localStorage (only after mount)
  useEffect(() => {
    if (!isMounted) return;
    try {
      localStorage.setItem('parwa_carousel_slide', currentSlide.toString());
    } catch {
      // localStorage might be full or unavailable
    }
  }, [currentSlide, isMounted]);

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  }, []);

  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  }, []);

  // Auto-play carousel (only when in view and not paused)
  useEffect(() => {
    if (!isAutoPlaying || !isInView || userPausedRef.current) return;
    const interval = setInterval(nextSlide, 5000);
    return () => clearInterval(interval);
  }, [isAutoPlaying, isInView, nextSlide]);

  // Handle page visibility (pause when tab is hidden)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        userPausedRef.current = true;
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  const handleUserInteraction = useCallback(() => {
    userPausedRef.current = true;
    setIsAutoPlaying(false);
    // Resume after 10 seconds
    setTimeout(() => {
      setIsAutoPlaying(true);
      userPausedRef.current = false;
    }, 10000);
  }, []);

  // Touch handlers for swipe
  const onTouchStart = (e: React.TouchEvent) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const onTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const onTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > minSwipeDistance;
    const isRightSwipe = distance < -minSwipeDistance;

    handleUserInteraction();

    if (isLeftSwipe) {
      nextSlide();
    } else if (isRightSwipe) {
      prevSlide();
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isInView) return;
      
      if (e.key === 'ArrowLeft') {
        handleUserInteraction();
        prevSlide();
      } else if (e.key === 'ArrowRight') {
        handleUserInteraction();
        nextSlide();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isInView, handleUserInteraction, nextSlide, prevSlide]);

  const getAccentClasses = (color: string) => {
    const colors: Record<string, { bg: string; text: string; border: string; glow: string }> = {
      teal: { bg: 'bg-teal-600/20', text: 'text-teal-400', border: 'border-teal-500/30', glow: 'shadow-teal-500/20' },
      navy: { bg: 'bg-navy-600/20', text: 'text-navy-300', border: 'border-navy-500/30', glow: 'shadow-navy-500/20' },
      charcoal: { bg: 'bg-charcoal-600/20', text: 'text-charcoal-300', border: 'border-charcoal-500/30', glow: 'shadow-charcoal-500/20' },
      orange: { bg: 'bg-orange-600/20', text: 'text-orange-400', border: 'border-orange-500/30', glow: 'shadow-orange-500/20' },
      gold: { bg: 'bg-gold-600/20', text: 'text-gold-400', border: 'border-gold-500/30', glow: 'shadow-gold-500/20' },
    };
    return colors[color] || colors.teal;
  };

  return (
    <section 
      ref={sectionRef}
      className={`relative overflow-hidden bg-gradient-to-b from-navy-900 via-navy-900 to-background-secondary transition-opacity duration-700 ${isInView ? 'opacity-100' : 'opacity-0'}`}
      aria-label="Feature carousel"
      role="region"
    >
      {/* Animated Background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-64 sm:w-96 h-64 sm:h-96 bg-teal-500/10 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-0 right-1/4 w-64 sm:w-96 h-64 sm:h-96 bg-gold-500/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 md:py-20 lg:py-32">
        {/* Main Carousel */}
        <div 
          className="relative touch-action-pan-x"
          onMouseEnter={handleUserInteraction}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
        >
          {/* Slides Container */}
          <div className="overflow-hidden rounded-xl sm:rounded-2xl border border-white/10 bg-surface/30 backdrop-blur-sm">
            <div
              className="flex transition-transform duration-700 ease-out"
              style={{ transform: `translateX(-${currentSlide * 100}%)` }}
              role="list"
            >
              {slides.map((slide, index) => {
                const accent = getAccentClasses(slide.accentColor);
                return (
                  <div
                    key={slide.id}
                    className="w-full flex-shrink-0"
                    role="listitem"
                    aria-label={`Slide ${index + 1} of ${slides.length}: ${slide.title}`}
                  >
                    <div className={`p-6 sm:p-10 md:p-16 lg:p-20 min-h-[300px] sm:min-h-[350px] md:min-h-[400px] lg:min-h-[500px] flex flex-col justify-center items-center text-center relative`}>
                      {/* Icon */}
                      <div className={`mb-6 sm:mb-8 ${accent.text} transition-transform duration-500 hover:scale-110`}>
                        {slide.icon}
                      </div>
                      
                      {/* Title */}
                      <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-6 leading-tight px-4">
                        {slide.title}
                      </h2>
                      
                      {/* Description */}
                      <p className="text-base sm:text-lg md:text-xl text-white/70 max-w-xl sm:max-w-2xl leading-relaxed px-4">
                        {slide.description}
                      </p>
                      
                      {/* Badge */}
                      <span className={`mt-6 sm:mt-8 px-4 sm:px-5 py-1.5 sm:py-2 rounded-full text-xs sm:text-sm font-semibold ${accent.bg} ${accent.text} border ${accent.border}`}>
                        {slide.psychologicalTrigger}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Navigation Arrows - Desktop */}
          <button
            onClick={() => { handleUserInteraction(); prevSlide(); }}
            className="hidden sm:flex absolute left-2 md:left-4 top-1/2 -translate-y-1/2 w-10 h-10 md:w-12 md:h-12 items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-white backdrop-blur-sm border border-white/10 transition-all duration-300 hover:scale-110 focus-visible-ring"
            aria-label="Previous slide"
          >
            <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <button
            onClick={() => { handleUserInteraction(); nextSlide(); }}
            className="hidden sm:flex absolute right-2 md:right-4 top-1/2 -translate-y-1/2 w-10 h-10 md:w-12 md:h-12 items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-white backdrop-blur-sm border border-white/10 transition-all duration-300 hover:scale-110 focus-visible-ring"
            aria-label="Next slide"
          >
            <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>

          {/* Mobile Swipe Hint */}
          <div className="sm:hidden absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 text-white/40 text-xs">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
            </svg>
            Swipe to navigate
          </div>
        </div>

        {/* Dots Indicator */}
        <div className="flex justify-center gap-2 sm:gap-3 mt-8 sm:mt-10" role="tablist" aria-label="Carousel navigation">
          {slides.map((_, index) => (
            <button
              key={index}
              onClick={() => { handleUserInteraction(); setCurrentSlide(index); }}
              className={`h-2 rounded-full transition-all duration-300 focus-visible-ring ${
                index === currentSlide
                  ? 'w-8 sm:w-10 bg-gold-500'
                  : 'w-2 bg-white/30 hover:bg-white/50'
              }`}
              aria-label={`Go to slide ${index + 1}`}
              aria-selected={index === currentSlide}
              role="tab"
            />
          ))}
        </div>

        {/* Slide Preview (Desktop) */}
        <div className="hidden lg:flex justify-center gap-3 mt-10">
          {slides.map((slide, index) => {
            const accent = getAccentClasses(slide.accentColor);
            return (
              <button
                key={slide.id}
                onClick={() => { handleUserInteraction(); setCurrentSlide(index); }}
                className={`flex items-center gap-3 px-4 lg:px-5 py-2.5 lg:py-3 rounded-xl transition-all duration-300 border focus-visible-ring ${
                  index === currentSlide
                    ? `${accent.bg} ${accent.text} ${accent.border}`
                    : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/80 border-white/10'
                }`}
                aria-label={`Go to ${slide.title}`}
              >
                <span className={accent.text}>
                  <svg className="w-5 h-5 lg:w-6 lg:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    {slide.id === 1 && <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />}
                    {slide.id === 2 && <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />}
                    {slide.id === 3 && <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />}
                    {slide.id === 4 && <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />}
                    {slide.id === 5 && <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />}
                  </svg>
                </span>
                <span className="text-xs lg:text-sm font-medium whitespace-nowrap">
                  {slide.title.split(' ').slice(0, 2).join(' ')}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
