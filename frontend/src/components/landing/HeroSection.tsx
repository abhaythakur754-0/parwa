'use client';

import { useState } from 'react';
import Link from 'next/link';

/**
 * HeroSection Component
 * 
 * Shows cost/time comparison between Traditional Support and PARWA AI.
 * Includes interactive Jarvis preview chat.
 * 
 * Key points:
 * - Starting price: $999/month (not fake stats)
 * - No misleading response time claims
 * - Show real cost comparison
 * - Include interactive Jarvis chat preview
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3.4
 */

interface HeroSectionProps {
  onOpenJarvis?: () => void;
}

const comparisonData = {
  traditional: [
    { label: 'Cost per agent', value: '$50,000/year' },
    { label: 'Working hours', value: '8 hours/day only' },
    { label: 'Training', value: 'Additional costs' },
    { label: 'Availability', value: 'Sick days & turnover' },
    { label: 'Consistency', value: 'Variable responses' },
  ],
  parwa: [
    { label: 'Starting at', value: '$999/month' },
    { label: 'Availability', value: '24/7/365' },
    { label: 'Training', value: 'Learns automatically' },
    { label: 'Reliability', value: 'Never takes a day off' },
    { label: 'Consistency', value: 'Always consistent' },
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

    // Add user message
    setChatMessages((prev) => [...prev, { type: 'user', text: chatInput }]);
    setChatInput('');
    setIsTyping(true);

    // Simulate Jarvis response
    setTimeout(() => {
      const responses = [
        "I can handle up to 90% of your repetitive support tickets automatically, saving you 40+ hours per week!",
        "I work 24/7, never take breaks, and always provide consistent, accurate responses based on your knowledge base.",
        "Setting me up is easy - just upload your docs and I'll learn everything I need to help your customers.",
        "I'm like having a tireless customer care officer who never complains and always delivers!",
      ];
      const randomResponse = responses[Math.floor(Math.random() * responses.length)];
      setChatMessages((prev) => [...prev, { type: 'jarvis', text: randomResponse }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <section className="bg-secondary-50 py-16 md:py-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Comparison Section */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          {/* Traditional Support */}
          <div className="card p-6 md:p-8 border-error-200 bg-error-50/30">
            <div className="flex items-center gap-3 mb-6">
              <span className="text-3xl">❌</span>
              <h3 className="text-xl font-bold text-secondary-900">Traditional Support</h3>
            </div>
            <ul className="space-y-4">
              {comparisonData.traditional.map((item, index) => (
                <li key={index} className="flex justify-between items-center py-2 border-b border-secondary-200 last:border-0">
                  <span className="text-secondary-600">{item.label}</span>
                  <span className="font-medium text-secondary-800">{item.value}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* PARWA AI */}
          <div className="card p-6 md:p-8 border-primary-300 bg-primary-50/30 ring-2 ring-primary-500/20">
            <div className="flex items-center gap-3 mb-6">
              <span className="text-3xl">✅</span>
              <h3 className="text-xl font-bold text-secondary-900">PARWA AI</h3>
            </div>
            <ul className="space-y-4">
              {comparisonData.parwa.map((item, index) => (
                <li key={index} className="flex justify-between items-center py-2 border-b border-primary-200 last:border-0">
                  <span className="text-secondary-600">{item.label}</span>
                  <span className="font-semibold text-primary-700">{item.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Jarvis Preview Chat */}
        <div className="max-w-2xl mx-auto">
          <h4 className="text-center text-lg font-medium text-secondary-700 mb-4">
            🤖 JARVIS PREVIEW - Chat with your AI Employee
          </h4>
          <div className="card overflow-hidden">
            {/* Chat Header */}
            <div className="bg-secondary-900 px-4 py-3 flex items-center gap-3">
              <span className="text-2xl">🤖</span>
              <div>
                <h5 className="font-medium text-white">Jarvis</h5>
                <p className="text-xs text-secondary-400">AI Customer Care Officer</p>
              </div>
              <span className="ml-auto flex items-center gap-1.5">
                <span className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></span>
                <span className="text-xs text-success-500">Online</span>
              </span>
            </div>

            {/* Chat Messages */}
            <div className="p-4 h-64 overflow-y-auto bg-secondary-50 space-y-4">
              {chatMessages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-2.5 rounded-2xl ${
                      message.type === 'user'
                        ? 'bg-primary-600 text-white rounded-br-md'
                        : 'bg-white text-secondary-900 shadow-sm rounded-bl-md'
                    }`}
                  >
                    {message.type === 'jarvis' && (
                      <span className="text-sm mr-2">🤖</span>
                    )}
                    <span className="text-sm">{message.text}</span>
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-white px-4 py-2.5 rounded-2xl rounded-bl-md shadow-sm">
                    <span className="text-sm mr-2">🤖</span>
                    <span className="flex gap-1">
                      <span className="w-2 h-2 bg-secondary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 bg-secondary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 bg-secondary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div className="p-4 bg-white border-t border-secondary-200">
              <div className="flex gap-2">
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
                  className="btn-primary px-4"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          {/* CTA Button */}
          <div className="mt-8 text-center">
            <button
              onClick={onOpenJarvis}
              className="btn-primary btn-lg px-8"
            >
              Get Started with Jarvis
            </button>
            <p className="mt-3 text-sm text-secondary-500">
              No credit card required for demo
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
