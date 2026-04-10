'use client';

import { useState, useEffect, useRef } from 'react';
import { MessageSquare, MessageCircle, Sparkles, PartyPopper, BarChart3 } from 'lucide-react';

/**
 * HowItWorks - Dark premium emerald theme
 */

const steps = [
  {
    icon: <MessageSquare className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'You Have a Task',
    description: 'Customer question, refund, tracking — whatever comes in.',
    color: 'green',
  },
  {
    icon: <MessageCircle className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Chat with Jarvis',
    description: 'Type naturally: "Handle this return"',
    color: 'amber',
  },
  {
    icon: <Sparkles className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Jarvis Does the Work',
    description: 'Processes using your business rules automatically',
    color: 'emerald',
  },
  {
    icon: <PartyPopper className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'Everyone\'s Happy',
    description: 'Task done, zero effort, instant resolution',
    color: 'green',
  },
  {
    icon: <BarChart3 className="w-6 h-6 sm:w-7 sm:h-7" />,
    title: 'See the Results',
    description: 'Real-time dashboard shows resolution rates, savings, and satisfaction',
    color: 'green',
  },
] as const;

const colorMap: Record<string, { bg: string; border: string; text: string; ring: string; dot: string }> = {
  green: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    ring: 'ring-emerald-500/20',
    dot: 'bg-emerald-400',
  },
  amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    ring: 'ring-amber-500/20',
    dot: 'bg-amber-400',
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    ring: 'ring-emerald-500/20',
    dot: 'bg-emerald-400',
  },
};

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState(0);
  const [isInView, setIsInView] = useState(false);
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
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [isInView]);

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden bg-gradient-to-b from-[#022C22] to-[#064E3B]"
    >
      {/* Ambient glow orbs */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 right-0 w-80 h-80 bg-emerald-500/15 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 left-0 w-64 h-64 bg-emerald-600/10 rounded-full blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-emerald-500/8 rounded-full blur-[140px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div
          className={`text-center mb-8 sm:mb-10 lg:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-5">
            How <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">PARWA</span> Works
          </h2>
          <p className="text-base sm:text-lg text-gray-400 max-w-2xl mx-auto px-4">
            Your support runs on autopilot — instant, automatic, zero effort.
          </p>
          {/* Setup time badge */}
          <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/30 mx-auto">
            <span className="text-base">⚡</span>
            <span className="text-sm font-semibold text-emerald-300">Average setup time: 5 minutes</span>
          </div>
        </div>

        {/* Steps - Desktop */}
        <div className="hidden md:block">
          <div className="relative">
            <div className="relative flex justify-between">
              {steps.map((step, index) => {
                const colors = colorMap[step.color];
                const isActive = activeStep === index;
                const isPast = activeStep > index;

                return (
                  <div
                    key={index}
                    className={`flex flex-col items-center cursor-pointer transition-all duration-500 ${
                      isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
                    }`}
                    style={{ transitionDelay: `${index * 120}ms` }}
                    onClick={() => setActiveStep(index)}
                    role="button"
                    tabIndex={0}
                    aria-label={`Step ${index + 1}: ${step.title}`}
                    onKeyDown={(e) => e.key === 'Enter' && setActiveStep(index)}
                  >
                    <div
                      className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-all duration-500 ring-4 ${
                        isActive
                          ? `${colors.bg} ${colors.border} ring ${colors.ring} scale-110`
                          : isPast
                          ? `${colors.bg} ring ${colors.ring}`
                          : 'bg-white/[0.03] border border-white/10 ring-transparent'
                      }`}
                    >
                      <span className={`transition-all duration-300 ${
                        isActive ? colors.text : isPast ? colors.text : 'text-gray-500'
                      }`}>
                        {step.icon}
                      </span>
                    </div>

                    <span className={`mt-4 text-xs font-semibold tracking-wider uppercase transition-colors duration-300 ${
                      isActive || isPast ? colors.text : 'text-gray-500'
                    }`}>
                      Step {index + 1}
                    </span>

                    <h4 className={`mt-1.5 text-base font-bold text-center transition-colors duration-300 ${
                      isActive ? 'text-white' : 'text-gray-500'
                    }`}>
                      {step.title}
                    </h4>

                    <div className={`mt-3 text-sm text-gray-400 text-center max-w-[180px] transition-all duration-500 ${
                      isActive ? 'opacity-100 max-h-20' : 'opacity-0 max-h-0 overflow-hidden'
                    }`}>
                      {step.description}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Steps - Mobile */}
        <div className="md:hidden space-y-3">
          {steps.map((step, index) => {
            const colors = colorMap[step.color];
            const isActive = activeStep === index;

            return (
              <div
                key={index}
                className={`rounded-xl border p-4 sm:p-5 transition-all duration-500 cursor-pointer backdrop-blur-sm ${
                  isActive
                    ? `${colors.border} ${colors.bg} shadow-lg shadow-emerald-500/10`
                    : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]'
                } ${isInView ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}`}
                style={{ transitionDelay: `${index * 100}ms` }}
                onClick={() => setActiveStep(index)}
                role="button"
                tabIndex={0}
                aria-label={`Step ${index + 1}: ${step.title}`}
                onKeyDown={(e) => e.key === 'Enter' && setActiveStep(index)}
              >
                <div className="flex items-start gap-3.5">
                  <div
                    className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                      isActive ? `${colors.bg} ${colors.text}` : 'bg-white/[0.05] text-gray-500'
                    }`}
                  >
                    {step.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold tracking-wider uppercase ${
                        isActive ? colors.text : 'text-gray-500'
                      }`}>
                        Step {index + 1}
                      </span>
                    </div>
                    <h4 className={`text-base font-bold mt-0.5 transition-colors ${
                      isActive ? 'text-white' : 'text-gray-400'
                    }`}>
                      {step.title}
                    </h4>
                    <p className={`text-sm mt-1 transition-all duration-300 ${
                      isActive ? 'text-gray-400 opacity-100 max-h-10' : 'text-gray-500 opacity-0 max-h-0 overflow-hidden'
                    }`}>
                      {step.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress Dots */}
        <div className="flex justify-center gap-2 mt-8 sm:mt-10" role="tablist" aria-label="Step progress">
          {steps.map((step, index) => {
            const colors = colorMap[step.color];
            return (
              <button
                key={index}
                onClick={() => setActiveStep(index)}
                className={`h-2 rounded-full transition-all duration-500 focus-visible-ring ${
                  index === activeStep
                    ? `w-8 ${colors.dot}`
                    : 'w-2 bg-gray-600 hover:bg-gray-500'
                }`}
                aria-label={`Go to step ${index + 1}`}
                aria-selected={index === activeStep}
                role="tab"
              />
            );
          })}
        </div>
      </div>
    </section>
  );
}
