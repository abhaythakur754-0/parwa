'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * HowItWorks Component
 * 
 * Dark theme showing HOW Jarvis works.
 * 4 animated steps with professional icons.
 * NO emojis - using SVG icons.
 * 
 * Features:
 * - Scroll-triggered animations
 * - Responsive layout (vertical on mobile, horizontal on desktop)
 * - Auto-cycling through steps
 * - Animated stats counters
 */

interface Step {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const steps: Step[] = [
  {
    icon: (
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
      </svg>
    ),
    title: 'Customer Message',
    description: 'Customer sends a message through any channel',
  },
  {
    icon: (
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
    ),
    title: 'Jarvis Analyzes',
    description: 'AI understands context and intent',
  },
  {
    icon: (
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
      </svg>
    ),
    title: 'Smart Response',
    description: 'Generates accurate, helpful response',
  },
  {
    icon: (
      <svg className="w-6 h-6 sm:w-8 sm:h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: 'Happy Client',
    description: 'Customer gets instant resolution',
  },
];

const stats = [
  { value: '<2s', label: 'Response Time', color: 'teal' },
  { value: '90%', label: 'Automation Rate', color: 'navy' },
  { value: '24/7', label: 'Availability', color: 'charcoal' },
  { value: '40+', label: 'Hours Saved/Week', color: 'gold' },
] as const;

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState(0);
  const [isInView, setIsInView] = useState(false);
  const [visibleStats, setVisibleStats] = useState<number[]>([]);
  const sectionRef = useRef<HTMLElement>(null);

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

  // Stagger stats animations
  useEffect(() => {
    if (!isInView) return;
    
    stats.forEach((_, index) => {
      setTimeout(() => {
        setVisibleStats(prev => [...prev, index]);
      }, 100 * (index + 1));
    });
  }, [isInView]);

  // Auto-cycle through steps
  useEffect(() => {
    if (!isInView) return;
    
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [isInView]);

  const getStatColor = (color: string) => {
    switch (color) {
      case 'teal': return 'text-teal-400';
      case 'navy': return 'text-navy-300';
      case 'charcoal': return 'text-charcoal-300';
      case 'gold': return 'text-gold-400';
      default: return 'text-teal-400';
    }
  };

  return (
    <section 
      ref={sectionRef}
      className={`relative bg-gradient-to-b from-background-secondary to-navy-900 py-12 sm:py-16 md:py-20 lg:py-32 overflow-hidden transition-opacity duration-700 ${isInView ? 'opacity-100' : 'opacity-0'}`}
    >
      {/* Background Effect */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 right-0 w-64 sm:w-96 h-64 sm:h-96 bg-teal-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className={`text-center mb-10 sm:mb-16 transition-all duration-700 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-6">
            How <span className="text-gradient">Jarvis</span> Works
          </h2>
          <p className="text-base sm:text-lg text-white/60 max-w-2xl mx-auto px-4">
            See how Jarvis transforms customer support in 4 simple steps
          </p>
        </div>

        {/* Steps - Desktop */}
        <div className="hidden md:block">
          <div className="relative">
            {/* Connection Line */}
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-teal-500/50 via-navy-500/50 to-gold-500/50 -translate-y-1/2" />
            
            <div className="relative flex justify-between gap-2">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className={`flex flex-col items-center cursor-pointer group transition-all duration-500 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}
                  style={{ transitionDelay: `${index * 100}ms` }}
                  onClick={() => setActiveStep(index)}
                  role="button"
                  tabIndex={0}
                  aria-label={`Step ${index + 1}: ${step.title}`}
                  onKeyDown={(e) => e.key === 'Enter' && setActiveStep(index)}
                >
                  {/* Step Circle */}
                  <div
                    className={`w-16 h-16 sm:w-20 sm:h-20 rounded-2xl flex items-center justify-center transition-all duration-500 ${
                      activeStep === index
                        ? 'bg-teal-600 shadow-lg shadow-teal-500/30 scale-110'
                        : activeStep > index
                        ? 'bg-teal-500/20 border border-teal-500/30'
                        : 'bg-surface border border-white/10 group-hover:border-white/20'
                    }`}
                  >
                    <span className={`transition-all duration-300 ${
                      activeStep === index ? 'text-white scale-110' : activeStep > index ? 'text-teal-400' : 'text-white/50 group-hover:text-white/70'
                    }`}>
                      {step.icon}
                    </span>
                  </div>

                  {/* Step Number */}
                  <span
                    className={`mt-3 sm:mt-5 text-xs sm:text-sm font-medium transition-colors ${
                      activeStep >= index ? 'text-teal-400' : 'text-white/40'
                    }`}
                  >
                    Step {index + 1}
                  </span>

                  {/* Step Title */}
                  <h4
                    className={`mt-1 sm:mt-2 text-sm sm:text-lg font-semibold text-center transition-colors ${
                      activeStep === index ? 'text-white' : 'text-white/60'
                    }`}
                  >
                    {step.title}
                  </h4>

                  {/* Step Description */}
                  <div
                    className={`mt-2 sm:mt-3 text-xs sm:text-sm text-white/50 text-center max-w-[120px] sm:max-w-[160px] transition-all duration-500 ${
                      activeStep === index ? 'opacity-100 max-h-20' : 'opacity-0 max-h-0'
                    }`}
                  >
                    {step.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Steps - Mobile (Vertical Timeline) */}
        <div className="md:hidden space-y-4">
          {steps.map((step, index) => (
            <div
              key={index}
              className={`card p-4 sm:p-5 transition-all duration-500 cursor-pointer ${
                activeStep === index ? 'border-teal-500/30 bg-teal-500/5' : ''
              } ${isInView ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}
              style={{ transitionDelay: `${index * 100}ms` }}
              onClick={() => setActiveStep(index)}
              role="button"
              tabIndex={0}
              aria-label={`Step ${index + 1}: ${step.title}`}
              onKeyDown={(e) => e.key === 'Enter' && setActiveStep(index)}
            >
              <div className="flex items-start gap-3 sm:gap-4">
                <div
                  className={`w-12 h-12 sm:w-14 sm:h-14 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                    activeStep === index
                      ? 'bg-teal-600 text-white'
                      : activeStep > index
                      ? 'bg-teal-500/20 text-teal-400'
                      : 'bg-surface text-white/50'
                  }`}
                >
                  {step.icon}
                </div>
                <div className="min-w-0">
                  <span className="text-xs text-teal-400 font-semibold">
                    Step {index + 1}
                  </span>
                  <h4 className="text-base sm:text-lg font-semibold text-white mt-0.5 sm:mt-1">
                    {step.title}
                  </h4>
                  <p className="text-xs sm:text-sm text-white/60 mt-0.5 sm:mt-1">
                    {step.description}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Progress Indicator */}
        <div className="flex justify-center gap-2 mt-8 sm:mt-12" role="tablist" aria-label="Step progress">
          {steps.map((_, index) => (
            <button
              key={index}
              onClick={() => setActiveStep(index)}
              className={`h-2 rounded-full transition-all duration-300 focus-visible-ring ${
                index === activeStep
                  ? 'w-8 sm:w-10 bg-gold-500'
                  : 'w-2 bg-white/20 hover:bg-white/30'
              }`}
              aria-label={`Go to step ${index + 1}`}
              aria-selected={index === activeStep}
              role="tab"
            />
          ))}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6 mt-12 sm:mt-16 lg:mt-20 pt-8 sm:pt-12 border-t border-white/10">
          {stats.map((stat, index) => (
            <div 
              key={index} 
              className={`text-center transition-all duration-500 ${visibleStats.includes(index) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
              style={{ transitionDelay: `${(index + 4) * 100}ms` }}
            >
              <div className={`text-2xl sm:text-3xl md:text-4xl font-bold ${getStatColor(stat.color)}`}>
                {stat.value}
              </div>
              <div className="text-xs sm:text-sm text-white/50 mt-1.5 sm:mt-2">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
