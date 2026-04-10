'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * JarvisDemo - Light green theme
 * Auto-playing chat: work given → Jarvis processes → Results shown
 */

interface ChatMessage {
  sender: 'user' | 'jarvis';
  text: string;
  isResult?: boolean;
}

const chatScript: ChatMessage[] = [
  { sender: 'user', text: 'Handle these 15 refund requests' },
  { sender: 'jarvis', text: 'On it! Analyzing each request against your refund policy...' },
  { sender: 'jarvis', text: '✅ 12 approved for instant refund • ⏳ 3 need your approval (policy exceptions) • 💰 $4,280 refunded automatically', isResult: true },
  { sender: 'user', text: 'Approve all 3 pending ones' },
  { sender: 'jarvis', text: 'Done! All 15 refunds processed. Total: $5,120. Time saved: 3.5 hours. Customer satisfaction: 98%', isResult: true },
];

const MESSAGE_DELAY = 2500;
const TYPING_DELAY = 1500;
const PAUSE_BEFORE_LOOP = 4000;

export default function JarvisDemo() {
  const [visibleMessages, setVisibleMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isInView, setIsInView] = useState(false);
  const [loopCount, setLoopCount] = useState(0);
  const sectionRef = useRef<HTMLElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsInView(true); },
      { threshold: 0.2 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isInView) return;
    let messageIndex = 0;
    let currentMessages: ChatMessage[] = [];
    let timeouts: NodeJS.Timeout[] = [];

    const resetAndPlay = () => {
      currentMessages = [];
      messageIndex = 0;
      setVisibleMessages([]);
      setIsTyping(false);
      scheduleNext();
    };

    const scheduleNext = () => {
      if (messageIndex >= chatScript.length) {
        const loopTimeout = setTimeout(() => {
          setLoopCount((prev) => prev + 1);
          resetAndPlay();
        }, PAUSE_BEFORE_LOOP);
        timeouts.push(loopTimeout);
        return;
      }
      const typingTimeout = setTimeout(() => setIsTyping(true), 300);
      timeouts.push(typingTimeout);
      const msgTimeout = setTimeout(() => {
        currentMessages = [...currentMessages, chatScript[messageIndex]];
        setVisibleMessages([...currentMessages]);
        setIsTyping(false);
        messageIndex++;
        scheduleNext();
      }, TYPING_DELAY);
      timeouts.push(msgTimeout);
    };

    const startDelay = setTimeout(() => scheduleNext(), 500);
    timeouts.push(startDelay);
    return () => { timeouts.forEach(clearTimeout); };
  }, [isInView, loopCount]);

  useEffect(() => {
    if (chatEndRef.current) {
      const chatContainer = chatEndRef.current.parentElement;
      if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }, [visibleMessages, isTyping]);

  return (
    <section
      ref={sectionRef}
      className="relative overflow-hidden bg-gradient-to-b from-white to-[#F0FDF4]"
    >
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-emerald-200/30 rounded-full blur-[120px]" />
      </div>

      <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div
          className={`text-center mb-8 sm:mb-10 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 mb-3 sm:mb-4">
            See <span className="text-gradient">Jarvis</span> in Action
          </h2>
          <p className="text-sm sm:text-base text-gray-500">
            A real workflow. No edits. No tricks. Just give Jarvis work and watch it deliver.
          </p>
          {/* LIVE DEMO badge with pulsing indicator */}
          <div className="mt-4 inline-flex items-center gap-2.5 px-4 py-2 rounded-full bg-red-50 border border-red-200">
            <div className="relative w-2.5 h-2.5">
              <div className="absolute inset-0 rounded-full bg-red-500 pulse-live" />
              <div className="absolute inset-0 rounded-full bg-red-500" />
            </div>
            <span className="text-xs sm:text-sm font-bold text-red-600 tracking-wide uppercase">Live Demo</span>
            <span className="text-xs text-red-400 font-medium">— Happening right now</span>
          </div>
        </div>

        {/* Chat Window */}
        <div
          className={`glass-premium rounded-2xl overflow-hidden transition-all duration-700 delay-200 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
        >
          {/* Chat Header */}
          <div className="bg-gradient-to-r from-emerald-600 to-emerald-500 backdrop-blur-xl px-5 sm:px-6 py-4 flex items-center gap-3 border-b border-emerald-300/20">
            <div className="relative w-10 h-10 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
              <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-emerald-400 rounded-full border-2 border-emerald-600" />
            </div>
            <div className="min-w-0">
              <h5 className="font-bold text-white text-sm sm:text-base">Jarvis — AI Customer Care Officer</h5>
              <p className="text-xs text-emerald-100/80">Always online • Resolving tickets automatically</p>
            </div>
            <div className="ml-auto flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-300 rounded-full animate-pulse" />
              <span className="text-xs text-emerald-200 font-medium">Online</span>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="p-5 sm:p-6 h-80 sm:h-96 md:h-[28rem] overflow-y-auto bg-emerald-50/30 space-y-4 scrollbar-hide">
            {visibleMessages.map((message, index) => (
              <div
                key={`${loopCount}-${index}`}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'} chat-msg-reveal`}
              >
                {message.sender === 'jarvis' && (
                  <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 mr-2.5 mt-1">
                    <svg className="w-3.5 h-3.5 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                    </svg>
                  </div>
                )}
                
                {message.isResult ? (
                  <div className="max-w-[85%] sm:max-w-[80%]">
                    <div className="rounded-2xl rounded-bl-md border border-emerald-200 bg-emerald-50 backdrop-blur-sm p-4 sm:p-5">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs font-semibold text-emerald-600 tracking-wide uppercase">Results</span>
                      </div>
                      <p className="text-sm sm:text-base text-gray-800 leading-relaxed">
                        {message.text}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`max-w-[80%] sm:max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      message.sender === 'user'
                        ? 'bg-emerald-600 text-white rounded-br-md'
                        : 'bg-white text-gray-700 rounded-bl-md border border-gray-200'
                    }`}
                  >
                    {message.text}
                  </div>
                )}
                
                {message.sender === 'user' && !message.isResult && (
                  <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0 ml-2.5 mt-1">
                    <svg className="w-3.5 h-3.5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0" />
                    </svg>
                  </div>
                )}
              </div>
            ))}

            {/* Typing Indicator */}
            {isTyping && (
              <div className="flex justify-start chat-msg-reveal">
                <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 mr-2.5 mt-1">
                  <svg className="w-3.5 h-3.5 text-emerald-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                  </svg>
                </div>
                <div className="bg-white px-4 py-3.5 rounded-2xl rounded-bl-md border border-gray-200">
                  <span className="flex gap-1.5">
                    <span className="w-2 h-2 bg-emerald-400 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-emerald-400 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-emerald-400 rounded-full typing-dot" />
                  </span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Chat Footer */}
          <div className="px-5 sm:px-6 py-3.5 bg-white border-t border-gray-200 flex items-center gap-2">
            <div className="flex-1 text-xs text-gray-400">
              Automated demo — loops every {((chatScript.length * (TYPING_DELAY + MESSAGE_DELAY)) / 1000 + PAUSE_BEFORE_LOOP / 1000).toFixed(0)}s
            </div>
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-emerald-300" />
              <div className="w-2 h-2 rounded-full bg-emerald-200" />
              <div className="w-2 h-2 rounded-full bg-emerald-100" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
