'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

/**
 * HeroSection Component
 * 
 * Dark premium theme with cost comparison.
 * Shows the value proposition of PARWA AI.
 * NO emojis - using SVG icons.
 * 
 * Features:
 * - Responsive comparison cards (stacked on mobile)
 * - Scroll-triggered animations
 * - Interactive chat preview
 */

interface HeroSectionProps {
  onOpenJarvis?: () => void;
}

const comparisonData = {
  traditional: [
    { label: 'Who works', value: '1 Person Working Alone', negative: true },
    { label: 'Response Speed', value: '5-30 minutes average', negative: true },
    { label: 'Scalability', value: 'Fixed capacity', negative: true },
    { label: 'Availability', value: '8 hrs/day, 5 days/week', negative: true },
    { label: 'Annual Cost (24/7)', value: '$150,000/year', negative: true },
    { label: 'Reliability', value: 'Sick days, turnover, burnout', negative: true },
  ],
  parwa: [
    { label: 'Who works', value: 'Team of Specialized AI Agents with Strict Security Measures', highlight: true },
    { label: 'Response Speed', value: 'Under 2 seconds', highlight: true },
    { label: 'Scalability', value: 'Unlimited tickets', highlight: true },
    { label: 'Availability', value: '24 Hours / 7 Days / 365 Days', highlight: true },
    { label: 'Annual Cost', value: '$11,988/year', highlight: true },
    { label: 'Reliability', value: 'No sick days, no turnover, no burnout', highlight: true },
  ],
};

export default function HeroSection({ onOpenJarvis }: HeroSectionProps) {
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<Array<{ type: 'user' | 'jarvis'; text: string }>>([
    {
      type: 'jarvis',
      text: "Hi! I'm your AI customer care officer. I handle tickets, answer questions, and learn from your knowledge base. What would you like to know?",
    },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [isInView, setIsInView] = useState(false);
  const [visibleCards, setVisibleCards] = useState<number[]>([]);
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

  // Stagger card animations
  useEffect(() => {
    if (!isInView) return;
    
    const timer = setTimeout(() => {
      setVisibleCards([0]);
    }, 100);

    const timer2 = setTimeout(() => {
      setVisibleCards([0, 1]);
    }, 300);

    return () => {
      clearTimeout(timer);
      clearTimeout(timer2);
    };
  }, [isInView]);

  const handleSendMessage = () => {
    if (!chatInput.trim()) return;

    setChatMessages((prev) => [...prev, { type: 'user', text: chatInput }]);
    setChatInput('');
    setIsTyping(true);

    setTimeout(() => {
      const responses = [
        "I can handle up to 90% of your repetitive support tickets automatically, saving you 40+ hours per week.",
        "I work 24/7, never take breaks, and always provide consistent, accurate responses based on your knowledge base.",
        "Setting me up is easy - just upload your docs and I'll learn everything I need to help your customers.",
        "I'm like having a tireless customer care officer who never complains and always delivers.",
      ];
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      setChatMessages((prev) => [...prev, { type: 'jarvis', text: randomResponse }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <section 
      ref={sectionRef}
      className={`relative overflow-hidden bg-gradient-to-b from-background-secondary to-navy-900 transition-opacity duration-700 ${isInView ? 'opacity-100' : 'opacity-0'}`}
    >
      {/* Background Effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-0 w-64 sm:w-96 h-64 sm:h-96 bg-teal-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 right-0 w-64 sm:w-96 h-64 sm:h-96 bg-gold-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 md:py-20 lg:py-32">
        {/* Section Header */}
        <div className={`text-center mb-10 sm:mb-16 transition-all duration-700 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 sm:mb-6">
            Traditional Support vs <span className="text-gradient">PARWA AI</span>
          </h2>
          <p className="text-base sm:text-lg text-white/60 max-w-2xl mx-auto px-4">
            See why hundreds of businesses are switching to AI-powered customer support
          </p>
        </div>

        {/* Comparison Section - Responsive Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8 mb-12 sm:mb-16 lg:mb-20">
          {/* Traditional Support */}
          <div 
            className={`card p-6 sm:p-8 border-error-500/20 bg-error-500/5 transition-all duration-700 hover-lift ${
              visibleCards.includes(0) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
            }`}
          >
            <div className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
              <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-error-500/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-error-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="text-lg sm:text-xl font-bold text-white">Traditional Support</h3>
            </div>
            <ul className="space-y-3 sm:space-y-5">
              {comparisonData.traditional.map((item, index) => (
                <li key={index} className="flex flex-col sm:flex-row sm:justify-between sm:items-center py-2 sm:py-3 border-b border-white/10 last:border-0 gap-1 sm:gap-0">
                  <span className="text-white/60 text-sm sm:text-base">{item.label}</span>
                  <span className="font-medium text-white/80 text-sm sm:text-base">{item.value}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* PARWA AI */}
          <div 
            className={`card-elevated p-6 sm:p-8 border-teal-500/30 relative overflow-hidden transition-all duration-700 hover-lift ${
              visibleCards.includes(1) ? 'opacity-100 translate-y-0 delay-200' : 'opacity-0 translate-y-8'
            }`}
          >
            <div className="absolute top-0 right-0 w-24 sm:w-32 h-24 sm:h-32 bg-teal-500/10 rounded-full blur-2xl" />
            <div className="relative">
              <div className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-teal-500/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 sm:w-6 sm:h-6 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-white">PARWA AI</h3>
                <span className="hidden sm:inline-flex ml-auto px-3 py-1 rounded-full bg-teal-500/20 text-teal-400 text-xs font-semibold">
                  RECOMMENDED
                </span>
              </div>
              <ul className="space-y-3 sm:space-y-5">
                {comparisonData.parwa.map((item, index) => (
                  <li key={index} className="flex flex-col sm:flex-row sm:justify-between sm:items-center py-2 sm:py-3 border-b border-teal-500/20 last:border-0 gap-1 sm:gap-0">
                    <span className="text-white/60 text-sm sm:text-base">{item.label}</span>
                    <span className="font-semibold text-teal-400 text-sm sm:text-base">{item.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Savings Badge - Mobile */}
        <div className={`sm:hidden text-center mb-8 transition-all duration-700 delay-300 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-teal-500/10 border border-teal-500/20">
            <svg className="w-5 h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-teal-400 font-semibold">Save $138,012/year</span>
          </div>
        </div>

        {/* Jarvis Preview Chat */}
        <div className={`max-w-2xl mx-auto transition-all duration-700 delay-500 ${isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
          <h4 className="text-center text-base sm:text-lg font-medium text-white/70 mb-4 sm:mb-6 flex items-center justify-center gap-2 sm:gap-3">
            <svg className="w-4 h-4 sm:w-5 sm:h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span className="text-sm sm:text-base">JARVIS PREVIEW - Chat with your AI Employee</span>
          </h4>
          <div className="card overflow-hidden">
            {/* Chat Header */}
            <div className="bg-gradient-to-r from-teal-600 to-teal-700 px-4 sm:px-5 py-3 sm:py-4 flex items-center gap-3 sm:gap-4">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div className="min-w-0">
                <h5 className="font-semibold text-white text-sm sm:text-base">Jarvis</h5>
                <p className="text-xs text-teal-100">AI Customer Care Officer</p>
              </div>
              <span className="ml-auto flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span className="text-xs text-green-300">Online</span>
              </span>
            </div>

            {/* Chat Messages */}
            <div className="p-4 sm:p-5 h-56 sm:h-64 md:h-72 overflow-y-auto bg-navy-900/50 space-y-3 sm:space-y-4 scrollbar-hide">
              {chatMessages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] sm:max-w-[80%] px-3 sm:px-4 py-2 sm:py-3 rounded-2xl text-sm ${
                      message.type === 'user'
                        ? 'bg-teal-600 text-white rounded-br-md'
                        : 'bg-surface text-white/90 rounded-bl-md border border-white/10'
                    }`}
                  >
                    {message.text}
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-surface px-4 py-3 rounded-2xl rounded-bl-md border border-white/10">
                    <span className="flex gap-1.5">
                      <span className="w-2 h-2 bg-teal-400 rounded-full typing-dot" />
                      <span className="w-2 h-2 bg-teal-400 rounded-full typing-dot" />
                      <span className="w-2 h-2 bg-teal-400 rounded-full typing-dot" />
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="p-4 sm:p-5 bg-surface/50 border-t border-white/10">
              <div className="flex gap-2 sm:gap-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Type your message..."
                  className="input flex-1 text-sm sm:text-base"
                  aria-label="Chat message input"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim()}
                  className="bg-teal-600 hover:bg-teal-500 text-white p-2.5 sm:p-3 rounded-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed focus-visible-ring"
                  aria-label="Send message"
                >
                  <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {/* CTA Button */}
          <div className="mt-8 sm:mt-10 text-center">
            <button
              onClick={onOpenJarvis}
              className="btn-gold btn-lg hover:-translate-y-1 transition-all duration-300 text-sm sm:text-base"
            >
              Get Started with Jarvis
            </button>
            <p className="mt-3 sm:mt-4 text-xs sm:text-sm text-white/50">
              No credit card required for demo
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
