'use client';

import { useState, useEffect } from 'react';

/**
 * HowItWorks Component
 * 
 * Shows HOW Jarvis works (people care about HOW after understanding WHAT).
 * 4 animated steps:
 * 1. Customer Message (envelope flying)
 * 2. Jarvis Analyzes (brain pulsing)
 * 3. Smart Response (lightbulb glowing)
 * 4. Happy Client (celebration)
 * 
 * Color scheme based on Frontend Docs:
 * - Uses Teal theme for active states
 * - Gold accent for highlights
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3.6
 */

interface Step {
  icon: string;
  title: string;
  description: string;
  animation: string;
}

const steps: Step[] = [
  {
    icon: '📩',
    title: 'Customer Message',
    description: 'Customer sends a message through any channel',
    animation: 'Envelope flying in',
  },
  {
    icon: '🧠',
    title: 'Jarvis Analyzes',
    description: 'AI understands context and intent',
    animation: 'Brain pulsing',
  },
  {
    icon: '💡',
    title: 'Smart Response',
    description: 'Generates accurate, helpful response',
    animation: 'Lightbulb glowing',
  },
  {
    icon: '✅',
    title: 'Happy Client',
    description: 'Customer gets instant resolution',
    animation: 'Celebration effect',
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
    <section className="py-16 md:py-24 bg-secondary-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-12 md:mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-secondary-900 mb-4">
            How <span className="text-teal-600">Jarvis</span> Works
          </h2>
          <p className="text-lg text-secondary-600 max-w-2xl mx-auto">
            See how Jarvis transforms customer support in 4 simple steps
          </p>
        </div>

        {/* Steps - Desktop */}
        <div className="hidden md:block">
          <div className="relative">
            {/* Connection Line */}
            <div className="absolute top-1/2 left-0 right-0 h-1 bg-gradient-to-r from-teal-200 via-navy-200 to-gold-200 -translate-y-1/2 z-0" />
            
            <div className="relative z-10 flex justify-between">
              {steps.map((step, index) => (
                <div
                  key={index}
                  className="flex flex-col items-center cursor-pointer"
                  onClick={() => setActiveStep(index)}
                >
                  {/* Step Circle */}
                  <div
                    className={`w-20 h-20 rounded-full flex items-center justify-center text-4xl transition-all duration-500 ${
                      activeStep === index
                        ? 'bg-teal-600 shadow-lg scale-110 ring-4 ring-teal-200'
                        : activeStep > index
                        ? 'bg-success-500 shadow-md'
                        : 'bg-white shadow-md hover:shadow-lg'
                    }`}
                  >
                    <span className={activeStep === index ? 'animate-bounce' : ''}>
                      {step.icon}
                    </span>
                  </div>

                  {/* Step Number */}
                  <span
                    className={`mt-4 text-sm font-medium ${
                      activeStep >= index ? 'text-teal-600' : 'text-secondary-400'
                    }`}
                  >
                    Step {index + 1}
                  </span>

                  {/* Step Title */}
                  <h4
                    className={`mt-1 text-lg font-semibold text-center ${
                      activeStep === index ? 'text-secondary-900' : 'text-secondary-600'
                    }`}
                  >
                    {step.title}
                  </h4>

                  {/* Step Description (shown for active step) */}
                  <div
                    className={`mt-2 text-sm text-secondary-500 text-center max-w-[150px] transition-all duration-300 ${
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
        <div className="md:hidden space-y-6">
          {steps.map((step, index) => (
            <div
              key={index}
              className={`card p-6 transition-all duration-300 ${
                activeStep === index ? 'ring-2 ring-teal-500' : ''
              }`}
              onClick={() => setActiveStep(index)}
            >
              <div className="flex items-start gap-4">
                <div
                  className={`w-14 h-14 rounded-full flex items-center justify-center text-2xl flex-shrink-0 transition-all duration-300 ${
                    activeStep === index
                      ? 'bg-teal-600'
                      : activeStep > index
                      ? 'bg-success-500'
                      : 'bg-secondary-100'
                  }`}
                >
                  {step.icon}
                </div>
                <div>
                  <span className="text-xs text-teal-600 font-medium">
                    Step {index + 1}
                  </span>
                  <h4 className="text-lg font-semibold text-secondary-900">
                    {step.title}
                  </h4>
                  <p className="text-sm text-secondary-600 mt-1">
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
              className={`w-3 h-3 rounded-full transition-all duration-300 ${
                index === activeStep
                  ? 'bg-gold-500 w-8'
                  : 'bg-secondary-300 hover:bg-secondary-400'
              }`}
              aria-label={`Go to step ${index + 1}`}
            />
          ))}
        </div>

        {/* Stats with Industry Colors */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-16 pt-12 border-t border-secondary-200">
          {[
            { value: '<2s', label: 'Response Time', color: 'teal' },
            { value: '90%', label: 'Automation Rate', color: 'navy' },
            { value: '24/7', label: 'Availability', color: 'charcoal' },
            { value: '40+', label: 'Hours Saved/Week', color: 'gold' },
          ].map((stat, index) => (
            <div key={index} className="text-center">
              <div className={`text-2xl md:text-3xl font-bold ${
                stat.color === 'teal' ? 'text-teal-600' :
                stat.color === 'navy' ? 'text-navy-600' :
                stat.color === 'charcoal' ? 'text-charcoal-600' :
                'text-gold-600'
              }`}>
                {stat.value}
              </div>
              <div className="text-sm text-secondary-600 mt-1">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
