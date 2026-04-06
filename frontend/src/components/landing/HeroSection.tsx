'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * HeroSection Component
 * 
 * Dark premium theme with cost comparison.
 * Shows the value proposition of PARWA AI.
 * NO emojis - using SVG icons.
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
    <section className="relative overflow-hidden bg-gradient-to-b from-background-secondary to-navy-900">
      {/* Background Effects */}
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-96 h-96 bg-teal-500/5 rounded-full blur-3xl" />
        <div className="absolute top-1/3 right-0 w-96 h-96 bg-gold-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 md:py-32">
        {/* Comparison Section */}
        <div className="grid md:grid-cols-2 gap-8 mb-20">
          {/* Traditional Support */}
          <div className="card p-8 border-error-500/20 bg-error-500/5">
            <div className="flex items-center gap-4 mb-8">
              <div className="w-12 h-12 rounded-xl bg-error-500/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-error-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-white">Traditional Support</h3>
            </div>
            <ul className="space-y-5">
              {comparisonData.traditional.map((item, index) => (
                <li key={index} className="flex justify-between items-center py-3 border-b border-white/10 last:border-0">
                  <span className="text-white/60">{item.label}</span>
                  <span className="font-medium text-white/80">{item.value}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* PARWA AI */}
          <div className="card-elevated p-8 border-teal-500/30 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl" />
            <div className="relative">
              <div className="flex items-center gap-4 mb-8">
                <div className="w-12 h-12 rounded-xl bg-teal-500/20 flex items-center justify-center">
                  <svg className="w-6 h-6 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-white">PARWA AI</h3>
                <span className="ml-auto px-3 py-1 rounded-full bg-teal-500/20 text-teal-400 text-xs font-semibold">
                  RECOMMENDED
                </span>
              </div>
              <ul className="space-y-5">
                {comparisonData.parwa.map((item, index) => (
                  <li key={index} className="flex justify-between items-center py-3 border-b border-teal-500/20 last:border-0">
                    <span className="text-white/60">{item.label}</span>
                    <span className="font-semibold text-teal-400">{item.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Jarvis Preview Chat */}
        <div className="max-w-2xl mx-auto">
          <h4 className="text-center text-lg font-medium text-white/70 mb-6 flex items-center justify-center gap-3">
            <svg className="w-5 h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            JARVIS PREVIEW - Chat with your AI Employee
          </h4>
          <div className="card overflow-hidden">
            {/* Chat Header */}
            <div className="bg-gradient-to-r from-teal-600 to-teal-700 px-5 py-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h5 className="font-semibold text-white">Jarvis</h5>
                <p className="text-xs text-teal-100">AI Customer Care Officer</p>
              </div>
              <span className="ml-auto flex items-center gap-2">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span className="text-xs text-green-300">Online</span>
              </span>
            </div>

            {/* Chat Messages */}
            <div className="p-5 h-72 overflow-y-auto bg-navy-900/50 space-y-4">
              {chatMessages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                      message.type === 'user'
                        ? 'bg-teal-600 text-white rounded-br-md'
                        : 'bg-surface-default text-white/90 rounded-bl-md border border-white/10'
                    }`}
                  >
                    <span className="text-sm">{message.text}</span>
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-surface-default px-4 py-3 rounded-2xl rounded-bl-md border border-white/10">
                    <span className="flex gap-1.5">
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-teal-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="p-5 bg-surface-default/50 border-t border-white/10">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Type your message..."
                  className="input flex-1"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!chatInput.trim()}
                  className="bg-teal-600 hover:bg-teal-500 text-white px-4 py-2.5 rounded-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {/* CTA Button */}
          <div className="mt-10 text-center">
            <button
              onClick={onOpenJarvis}
              className="btn-gold btn-lg hover:-translate-y-1 transition-all duration-300"
            >
              Get Started with Jarvis
            </button>
            <p className="mt-4 text-sm text-white/50">
              No credit card required for demo
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
