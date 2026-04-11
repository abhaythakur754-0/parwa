'use client';

import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, User, Loader2, Sparkles, ArrowRight } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatWidgetProps {
  industry?: string;
  variant?: string;
}

// ── Detect industry/interest from conversation ──────────────────

function detectContextFromMessages(messages: Message[]): { industry: string | null; interests: string[] } {
  const allText = messages.map(m => m.content.toLowerCase()).join(' ');
  let detectedIndustry: string | null = null;
  const interests: string[] = [];

  // Industry detection
  if (allText.includes('ecommerce') || allText.includes('e-commerce') || allText.includes('online store') || allText.includes('shopify') || allText.includes('retail')) {
    detectedIndustry = 'ecommerce';
  } else if (allText.includes('saas') || allText.includes('software') || allText.includes('app') || allText.includes('subscription')) {
    detectedIndustry = 'saas';
  } else if (allText.includes('logistics') || allText.includes('shipping') || allText.includes('warehouse') || allText.includes('freight')) {
    detectedIndustry = 'logistics';
  } else if (allText.includes('health') || allText.includes('medical') || allText.includes('hospital') || allText.includes('clinic') || allText.includes('hipaa')) {
    detectedIndustry = 'healthcare';
  }

  // Interest detection
  if (allText.includes('price') || allText.includes('pricing') || allText.includes('cost') || allText.includes('plan')) interests.push('pricing');
  if (allText.includes('demo') || allText.includes('try') || allText.includes('see it')) interests.push('demo');
  if (allText.includes('roi') || allText.includes('save') || allText.includes('saving')) interests.push('roi');
  if (allText.includes('integrat') || allText.includes('connect') || allText.includes('shopify')) interests.push('integrations');
  if (allText.includes('security') || allText.includes('gdpr') || allText.includes('hipaa')) interests.push('security');

  return { industry: detectedIndustry, interests };
}

export function ChatWidget({ industry, variant }: ChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi there! I'm Jarvis, PARWA's AI assistant. I can help you find the perfect AI customer support plan. What industry are you in?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const msgCountRef = useRef(0);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    msgCountRef.current++;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg.content,
          industry: industry || undefined,
          variant: variant || undefined,
        }),
      });
      const data = await res.json();

      if (data.status === 'success' && data.reply) {
        const assistantMsg: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.reply,
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, assistantMsg]);
      } else {
        setMessages(prev => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: "Sorry, I'm having trouble right now. Please try again or book a demo for personalized help!",
            timestamp: new Date(),
          },
        ]);
      }
    } catch {
      setMessages(prev => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: "Network error. Please check your connection and try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // ── Navigate to full Jarvis with context ─────────────────────

  const handleTryFullJarvis = () => {
    const { industry: detectedIndustry, interests } = detectContextFromMessages(messages);

    // Build context from conversation
    const context: Record<string, unknown> = {
      source: 'free_chat',
      entry_source: 'free_chat',
    };

    if (industry || detectedIndustry) {
      context.industry = industry || detectedIndustry;
    }
    if (variant) {
      context.selected_variants = [variant];
    }
    if (interests.length > 0) {
      context.interests = interests;
    }

    // Store context for Jarvis to pick up
    if (typeof window !== 'undefined') {
      localStorage.setItem('parwa_jarvis_context', JSON.stringify(context));
    }

    // Navigate to full Jarvis chat with context
    const params = new URLSearchParams();
    if (context.industry) params.set('industry', String(context.industry));
    if (Array.isArray(context.selected_variants) && context.selected_variants.length > 0) params.set('variant', String(context.selected_variants[0]));
    if (context.entry_source) params.set('entry_source', String(context.entry_source));
    window.location.href = `/jarvis?${params.toString()}`;
  };

  // Show CTA after 3+ messages
  const showFullJarvisCTA = msgCountRef.current >= 3;

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center shadow-2xl transition-all duration-300 hover:scale-110 active:scale-95"
        style={{
          background: isOpen
            ? 'rgba(255,255,255,0.15)'
            : 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)',
          boxShadow: isOpen
            ? '0 8px 30px rgba(0,0,0,0.3)'
            : '0 8px 30px rgba(255,127,17,0.4), 0 0 60px rgba(255,127,17,0.15)',
          border: isOpen ? '1px solid rgba(255,255,255,0.2)' : 'none',
          backdropFilter: isOpen ? 'blur(20px)' : 'none',
        }}
        aria-label={isOpen ? 'Close chat' : 'Open chat'}
      >
        {isOpen ? (
          <X className="w-6 h-6 text-white" />
        ) : (
          <MessageCircle className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Pulse ring animation on floating button */}
      {!isOpen && (
        <div
          className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full pointer-events-none"
          style={{
            animation: 'chatPulseRing 2.5s ease-in-out infinite',
          }}
        />
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div
          className="fixed bottom-24 right-6 z-50 w-[380px] max-w-[calc(100vw-2rem)] rounded-2xl overflow-hidden flex flex-col shadow-2xl"
          style={{
            height: '520px',
            maxHeight: '70vh',
            background: 'linear-gradient(180deg, #1A1A1A 0%, #2A1A0A 100%)',
            border: '1px solid rgba(255,127,17,0.25)',
            boxShadow: '0 25px 60px rgba(0,0,0,0.5), 0 0 80px rgba(255,127,17,0.08)',
          }}
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-5 py-4 border-b" style={{ borderColor: 'rgba(255,127,17,0.15)' }}>
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)' }}>
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-white">PARWA AI Assistant</h3>
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
                <span className="text-xs text-orange-300/60">Online</span>
              </div>
            </div>
            <Sparkles className="w-4 h-4 text-orange-400/40" />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,127,17,0.2) transparent' }}>
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: 'rgba(255,127,17,0.15)' }}>
                    <Bot className="w-3.5 h-3.5 text-orange-400" />
                  </div>
                )}
                <div
                  className="max-w-[260px] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed"
                  style={{
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)'
                      : 'rgba(255,255,255,0.06)',
                    border: msg.role === 'user'
                      ? 'none'
                      : '1px solid rgba(255,255,255,0.08)',
                    color: msg.role === 'user' ? '#1A1A1A' : 'rgba(255,255,255,0.85)',
                    borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                  }}
                >
                  {msg.content}
                </div>
                {msg.role === 'user' && (
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: 'rgba(255,255,255,0.1)' }}>
                    <User className="w-3.5 h-3.5 text-white/60" />
                  </div>
                )}
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-2.5 justify-start">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ background: 'rgba(255,127,17,0.15)' }}>
                  <Bot className="w-3.5 h-3.5 text-orange-400" />
                </div>
                <div className="px-4 py-3 rounded-2xl" style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '18px 18px 18px 4px' }}>
                  <Loader2 className="w-4 h-4 text-orange-400 animate-spin" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Full Jarvis CTA */}
          {showFullJarvisCTA && !isLoading && (
            <div className="px-4 py-2" style={{ borderTop: '1px solid rgba(255,127,17,0.1)' }}>
              <button
                onClick={handleTryFullJarvis}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 hover:scale-[1.02] active:scale-95"
                style={{
                  background: 'linear-gradient(135deg, rgba(255,127,17,0.15) 0%, rgba(224,106,0,0.15) 100%)',
                  border: '1px solid rgba(255,127,17,0.25)',
                  color: 'rgba(255,127,17,0.9)',
                }}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Try Full Jarvis Experience</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Input */}
          <div className="px-4 py-3 border-t" style={{ borderColor: 'rgba(255,127,17,0.15)' }}>
            <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about plans, pricing..."
                disabled={isLoading}
                className="flex-1 px-4 py-2.5 rounded-xl text-sm text-white placeholder-white/30 focus:outline-none"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 disabled:opacity-30 active:scale-90"
                style={{
                  background: 'linear-gradient(135deg, #FF7F11 0%, #E06A00 100%)',
                  boxShadow: '0 4px 15px rgba(255,127,17,0.3)',
                }}
              >
                <Send className="w-4 h-4 text-white" />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Inline animation keyframes */}
      <style jsx global>{`
        @keyframes chatPulseRing {
          0%, 100% { box-shadow: 0 0 0 0 rgba(255,127,17,0.4); }
          50% { box-shadow: 0 0 0 15px rgba(255,127,17,0); }
        }
      `}</style>
    </>
  );
}
