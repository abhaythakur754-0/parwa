'use client';

import { useState, useEffect } from 'react';

/**
 * HowItWorks Component
 * 
 * Dark theme showing HOW Jarvis works.
 * 4 animated steps with professional icons.
 * NO emojis - using SVG icons.
 */

interface Step {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const steps: Step[] = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
      </svg>
    ),
    title: 'Customer Message',
    description: 'Customer sends a message through any channel',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
    ),
    title: 'Jarvis Analyzes',
    description: 'AI understands context and intent',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
      </svg>
    ),
    title: 'Smart Response',
    description: 'Generates accurate, helpful response',
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: 'Happy Client',
    description: 'Customer gets instant resolution',
  },
];

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState(0);

  // Auto-cycle through steps
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative bg-gradient-to-b from-background-secondary to-navy-900 py-20 md:py-32 overflow-hidden">
      {/* Background Effect */}
      <div className="absolute inset-0">
        <div className="absolute top-1/4 right-0 w-96 h-96 bg-teal-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-bold text-white mb-6">
            How <span className="text-gradient">Jarvis</span> Works
          </h2>
          <p className="text-lg text-white/60 max-w-2xl mx-auto">
            See how Jarvis transforms customer support in 4 simple steps
          </p>
        </div>

        {/* Steps - Desktop */}
        <div className="hidden md:block">
          <div className="relative">
            {/* Connection Line */}
            <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-teal-500/50 via-navy-500/50 to-gold-500/50 -translate-y-1/2" />
            
            <div className="relative flex justify-between">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className="flex flex-col items-center cursor-pointer group"
                  onClick={() => setActiveStep(index)}
                >
                  {/* Step Circle */}
                  <div
                    className={`w-20 h-20 rounded-2xl flex items-center justify-center transition-all duration-500 ${
                      activeStep === index
                        ? 'bg-teal-600 shadow-lg shadow-teal-500/30 scale-110'
                        : activeStep > index
                        ? 'bg-teal-500/20 border border-teal-500/30'
                        : 'bg-surface-default border border-white/10 group-hover:border-white/20'
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
                    className={`mt-5 text-sm font-medium transition-colors ${
                      activeStep >= index ? 'text-teal-400' : 'text-white/40'
                    }`}
                  >
                    Step {index + 1}
                  </span>

                  {/* Step Title */}
                  <h4
                    className={`mt-2 text-lg font-semibold text-center transition-colors ${
                      activeStep === index ? 'text-white' : 'text-white/60'
                    }`}
                  >
                    {step.title}
                  </h4>

                  {/* Step Description */}
                  <div
                    className={`mt-3 text-sm text-white/50 text-center max-w-[160px] transition-all duration-500 ${
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

        {/* Steps - Mobile */}
        <div className="md:hidden space-y-4">
          {steps.map((step, index) => (
            <div
              key={index}
              className={`card p-5 transition-all duration-300 cursor-pointer ${
                activeStep === index ? 'border-teal-500/30 bg-teal-500/5' : ''
              }`}
              onClick={() => setActiveStep(index)}
            >
              <div className="flex items-start gap-4">
                <div
                  className={`w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                    activeStep === index
                      ? 'bg-teal-600 text-white'
                      : activeStep > index
                      ? 'bg-teal-500/20 text-teal-400'
                      : 'bg-surface-default text-white/50'
                  }`}
                >
                  {step.icon}
                </div>
                <div>
                  <span className="text-xs text-teal-400 font-semibold">
                    Step {index + 1}
                  </span>
                  <h4 className="text-lg font-semibold text-white mt-1">
                    {step.title}
                  </h4>
                  <p className="text-sm text-white/60 mt-1">
                    {step.description}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Progress Indicator */}
        <div className="flex justify-center gap-2 mt-12">
          {steps.map((_, index) => (
            <button
              key={index}
              onClick={() => setActiveStep(index)}
              className={`h-2 rounded-full transition-all duration-300 ${
                index === activeStep
                  ? 'w-10 bg-gold-500'
                  : 'w-2 bg-white/20 hover:bg-white/30'
              }`}
              aria-label={`Go to step ${index + 1}`}
            />
          ))}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-20 pt-12 border-t border-white/10">
          {[
            { value: '<2s', label: 'Response Time', color: 'teal' },
            { value: '90%', label: 'Automation Rate', color: 'navy' },
            { value: '24/7', label: 'Availability', color: 'charcoal' },
            { value: '40+', label: 'Hours Saved/Week', color: 'gold' },
          ].map((stat, index) => (
            <div key={index} className="text-center">
              <div className={`text-3xl md:text-4xl font-bold ${
                stat.color === 'teal' ? 'text-teal-400' :
                stat.color === 'navy' ? 'text-navy-300' :
                stat.color === 'charcoal' ? 'text-charcoal-300' :
                'text-gold-400'
              }`}>
                {stat.value}
              </div>
              <div className="text-sm text-white/50 mt-2">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
