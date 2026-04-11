'use client';

import { useState, useEffect, useRef } from 'react';

/**
 * JarvisDemo - Premium parrot-green animated background
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
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const sectionRef = useRef<HTMLElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsInView(true); },
      { threshold: 0.15 }
    );
    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!sectionRef.current) return;
      const rect = sectionRef.current.getBoundingClientRect();
      setMousePos({
        x: ((e.clientX - rect.left) / rect.width - 0.5) * 2,
        y: ((e.clientY - rect.top) / rect.height - 0.5) * 2,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
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
      className="relative overflow-hidden"
      style={{
        background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 25%, #2D1F0E 50%, #3D2A10 75%, #1A1A1A 100%)',
        minHeight: '720px',
      }}
    >
      {/* ── Animated Background Layers ── */}

      {/* Layer 1: Large floating orbs with parallax */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute w-[500px] h-[500px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,127,17,0.25) 0%, rgba(255,127,17,0.05) 50%, transparent 70%)',
            top: '10%',
            left: '15%',
            transform: `translate(${mousePos.x * 15}px, ${mousePos.y * 10}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat1 8s ease-in-out infinite',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,159,68,0.2) 0%, rgba(255,159,68,0.03) 50%, transparent 70%)',
            bottom: '5%',
            right: '10%',
            transform: `translate(${mousePos.x * -20}px, ${mousePos.y * -12}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat2 10s ease-in-out infinite',
          }}
        />
        <div
          className="absolute w-[300px] h-[300px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(255,215,0,0.12) 0%, rgba(255,215,0,0.02) 50%, transparent 70%)',
            top: '50%',
            left: '55%',
            transform: `translate(-50%, -50%) translate(${mousePos.x * 8}px, ${mousePos.y * 8}px)`,
            transition: 'transform 0.8s cubic-bezier(0.22, 1, 0.36, 1)',
            animation: 'jarvisOrbFloat3 12s ease-in-out infinite',
          }}
        />
      </div>

      {/* Layer 2: Jarvis rings (concentric expanding rings) */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none" style={{ left: '55%' }}>
        <div className="relative" style={{ width: '700px', height: '700px' }}>
          {/* Ring 1 */}
          <div
            className="absolute inset-0 rounded-full border border-orange-500/20"
            style={{
              animation: 'jarvisRingExpand 4s ease-in-out infinite',
              boxShadow: '0 0 40px rgba(255,127,17,0.08), inset 0 0 40px rgba(255,127,17,0.03)',
            }}
          />
          {/* Ring 2 */}
          <div
            className="absolute rounded-full border border-orange-400/15"
            style={{
              inset: '60px',
              animation: 'jarvisRingExpand 4s ease-in-out infinite 1s',
              boxShadow: '0 0 30px rgba(255,159,68,0.06)',
            }}
          />
          {/* Ring 3 */}
          <div
            className="absolute rounded-full border border-orange-300/10"
            style={{
              inset: '120px',
              animation: 'jarvisRingExpand 4s ease-in-out infinite 2s',
              boxShadow: '0 0 20px rgba(255,212,168,0.05)',
            }}
          />
          {/* Core glow */}
          <div
            className="absolute rounded-full"
            style={{
              inset: '200px',
              background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.03) 60%, transparent 100%)',
              animation: 'jarvisCorePulse 3s ease-in-out infinite',
            }}
          />
        </div>
      </div>

      {/* Layer 3: Particle grid dots */}
      <div className="absolute inset-0 pointer-events-none" style={{ opacity: 0.4 }}>
        {Array.from({ length: 30 }).map((_, i) => {
          const row = Math.floor(i / 6);
          const col = i % 6;
          const x = `${(col + 0.5) * 16.67}%`;
          const y = `${(row + 0.5) * 16.67}%`;
          const delay = (i * 0.3) % 4;
          return (
            <div
              key={i}
              className="absolute w-1 h-1 rounded-full bg-orange-400"
              style={{
                left: x,
                top: y,
                animation: `jarvisDotPulse 3s ease-in-out infinite ${delay}s`,
                opacity: 0,
              }}
            />
          );
        })}
      </div>

      {/* Layer 4: Connecting lines (SVG) */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.08 }}>
        <defs>
          <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FF7F11" />
            <stop offset="100%" stopColor="#FF9F44" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((i) => (
          <line
            key={i}
            x1={`${15 + i * 18}%`}
            y1="20%"
            x2={`${25 + i * 15}%`}
            y2="80%"
            stroke="url(#lineGrad)"
            strokeWidth="1"
            strokeDasharray="8 12"
            style={{
              animation: `jarvisLineFlow 6s linear infinite ${i * 1.2}s`,
            }}
          />
        ))}
      </svg>

      {/* Layer 5: Floating data particles */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={`particle-${i}`}
            className="absolute w-2 h-2 rounded-full bg-orange-400/60"
            style={{
              left: `${10 + i * 12}%`,
              animation: `jarvisParticleRise ${6 + i * 0.8}s linear infinite ${i * 0.7}s`,
              opacity: 0,
            }}
          />
        ))}
      </div>

      {/* ── Content ── */}
      <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
        {/* Section Header */}
        <div
          className={`text-center mb-10 sm:mb-12 transition-all duration-700 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
        >
          {/* Floating label */}
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-2 rounded-full border border-orange-500/30 bg-orange-500/10 backdrop-blur-sm">
            <div className="relative w-2 h-2">
              <div className="absolute inset-0 rounded-full bg-orange-400 pulse-live" />
              <div className="absolute inset-0 rounded-full bg-orange-400" />
            </div>
            <span className="text-xs sm:text-sm font-bold text-orange-300 tracking-widest uppercase">Live Demo</span>
          </div>

          <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-white mb-4 leading-tight">
            See <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">Jarvis</span> in Action
          </h2>
          <p className="text-sm sm:text-base text-orange-200/60 max-w-lg mx-auto leading-relaxed">
            A real workflow. No edits. No tricks. Give Jarvis work and watch it deliver — in real time.
          </p>
        </div>

        {/* Chat Window */}
        <div
          className={`rounded-2xl overflow-hidden transition-all duration-700 delay-200 ${
            isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 50%, rgba(255,127,17,0.05) 100%)',
            border: '1px solid rgba(255,127,17,0.2)',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 25px 60px rgba(0,0,0,0.3), 0 0 80px rgba(255,127,17,0.08), inset 0 1px 0 rgba(255,255,255,0.08)',
          }}
        >
          {/* Chat Header */}
          <div
            className="px-5 sm:px-6 py-4 flex items-center gap-3"
            style={{
              background: 'linear-gradient(135deg, rgba(255,127,17,0.25) 0%, rgba(224,109,0,0.2) 100%)',
              borderBottom: '1px solid rgba(255,127,17,0.15)',
            }}
          >
            <div className="relative w-10 h-10 rounded-full bg-orange-500/20 border border-orange-400/30 flex items-center justify-center flex-shrink-0">
              <svg className="w-5 h-5 text-orange-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
              <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-orange-400 rounded-full border-2 border-orange-900 animate-pulse" />
            </div>
            <div className="min-w-0">
              <h5 className="font-bold text-white text-sm sm:text-base">Jarvis — AI Customer Care Officer</h5>
              <p className="text-xs text-orange-300/60">Always online • Resolving tickets automatically</p>
            </div>
            <div className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20">
              <span className="w-2 h-2 bg-orange-400 rounded-full animate-pulse" />
              <span className="text-xs text-orange-300 font-medium">Online</span>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="p-5 sm:p-6 h-80 sm:h-96 md:h-[28rem] overflow-y-auto space-y-4 scrollbar-hide" style={{ background: 'rgba(2,44,34,0.4)' }}>
            {visibleMessages.map((message, index) => (
              <div
                key={`${loopCount}-${index}`}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'} chat-msg-reveal`}
              >
                {message.sender === 'jarvis' && (
                  <div className="w-7 h-7 rounded-full bg-orange-500/15 border border-orange-500/20 flex items-center justify-center flex-shrink-0 mr-2.5 mt-1">
                    <svg className="w-3.5 h-3.5 text-orange-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                    </svg>
                  </div>
                )}
                
                {message.isResult ? (
                  <div className="max-w-[85%] sm:max-w-[80%]">
                    <div
                      className="rounded-2xl rounded-bl-md p-4 sm:p-5"
                      style={{
                        background: 'linear-gradient(135deg, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.05) 100%)',
                        border: '1px solid rgba(255,127,17,0.25)',
                        boxShadow: '0 0 30px rgba(255,127,17,0.06)',
                      }}
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
                        <span className="text-xs font-semibold text-orange-400 tracking-wide uppercase">Results</span>
                      </div>
                      <p className="text-sm sm:text-base text-orange-50 leading-relaxed">
                        {message.text}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`max-w-[80%] sm:max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      message.sender === 'user'
                        ? 'text-white rounded-br-md'
                        : 'text-orange-100/80 rounded-bl-md'
                    }`}
                    style={message.sender === 'user' ? {
                      background: 'linear-gradient(135deg, #E06D00 0%, #FF7F11 100%)',
                      boxShadow: '0 4px 16px rgba(255,127,17,0.25)',
                    } : {
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    {message.text}
                  </div>
                )}
                
                {message.sender === 'user' && !message.isResult && (
                  <div className="w-7 h-7 rounded-full bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0 ml-2.5 mt-1">
                    <svg className="w-3.5 h-3.5 text-orange-300/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0" />
                    </svg>
                  </div>
                )}
              </div>
            ))}

            {/* Typing Indicator */}
            {isTyping && (
              <div className="flex justify-start chat-msg-reveal">
                <div className="w-7 h-7 rounded-full bg-orange-500/15 border border-orange-500/20 flex items-center justify-center flex-shrink-0 mr-2.5 mt-1">
                  <svg className="w-3.5 h-3.5 text-orange-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
                  </svg>
                </div>
                <div className="px-4 py-3.5 rounded-2xl rounded-bl-md" style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <span className="flex gap-1.5">
                    <span className="w-2 h-2 bg-orange-400 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-orange-400 rounded-full typing-dot" />
                    <span className="w-2 h-2 bg-orange-400 rounded-full typing-dot" />
                  </span>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Chat Footer */}
          <div className="px-5 sm:px-6 py-3.5 flex items-center gap-2" style={{ background: 'rgba(2,44,34,0.6)', borderTop: '1px solid rgba(255,127,17,0.1)' }}>
            <div className="flex-1 text-xs text-orange-500/40">
              Automated demo — loops every {((chatScript.length * (TYPING_DELAY + MESSAGE_DELAY)) / 1000 + PAUSE_BEFORE_LOOP / 1000).toFixed(0)}s
            </div>
            <div className="flex gap-1">
              <div className="w-2 h-2 rounded-full bg-orange-500/30" />
              <div className="w-2 h-2 rounded-full bg-orange-500/20" />
              <div className="w-2 h-2 rounded-full bg-orange-500/10" />
            </div>
          </div>
        </div>
      </div>

      {/* ── Keyframe Styles (inline for this component) ── */}
      <style jsx global>{`
        @keyframes jarvisOrbFloat1 {
          0%, 100% { transform: translateY(0) scale(1); }
          33% { transform: translateY(-30px) scale(1.05); }
          66% { transform: translateY(15px) scale(0.97); }
        }
        @keyframes jarvisOrbFloat2 {
          0%, 100% { transform: translateY(0) scale(1); }
          50% { transform: translateY(-40px) scale(1.08); }
        }
        @keyframes jarvisOrbFloat3 {
          0%, 100% { transform: translateY(0) scale(1); }
          33% { transform: translateY(-20px) scale(1.03); }
          66% { transform: translateY(25px) scale(0.96); }
        }
        @keyframes jarvisRingExpand {
          0% { transform: scale(0.95); opacity: 0.6; }
          50% { transform: scale(1.05); opacity: 0.2; }
          100% { transform: scale(0.95); opacity: 0.6; }
        }
        @keyframes jarvisCorePulse {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.08); }
        }
        @keyframes jarvisDotPulse {
          0%, 100% { opacity: 0; transform: scale(0.5); }
          50% { opacity: 0.8; transform: scale(1.2); }
        }
        @keyframes jarvisLineFlow {
          0% { stroke-dashoffset: 100; }
          100% { stroke-dashoffset: 0; }
        }
        @keyframes jarvisParticleRise {
          0% { transform: translateY(100%) translateX(0); opacity: 0; }
          10% { opacity: 0.7; }
          90% { opacity: 0.7; }
          100% { transform: translateY(-100vh) translateX(30px); opacity: 0; }
        }
      `}</style>
    </section>
  );
}
