/**
 * PARWA Onboarding Jarvis Chat — Main Container
 *
 * Full-page chat interface where potential clients interact with
 * Jarvis AI during the pre-purchase demo experience.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useOnboardingJarvis } from '@/hooks/useOnboardingJarvis';
import { OnboardingJarvisMessage } from './OnboardingJarvisMessage';
import { OnboardingJarvisInput } from './OnboardingJarvisInput';
import { MessageCounter } from './MessageCounter';
import { DemoPackCTA } from './cards/DemoPackCTA';
import { LimitReachedCard } from './cards/LimitReachedCard';
import { ErrorBanner } from './ErrorBanner';

interface Props {
  entrySource?: string;
  entryParams?: Record<string, any>;
}

export function OnboardingJarvisChat({ entrySource = 'direct', entryParams }: Props) {
  const {
    session,
    messages,
    isLoading,
    isTyping,
    remainingToday,
    isLimitReached,
    isDemoPackActive,
    error,
    detectedStage,
    initSession,
    sendMessage,
    clearError,
  } = useOnboardingJarvis();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [initialized, setInitialized] = useState(false);

  // Initialize session on mount
  useEffect(() => {
    if (!initialized) {
      initSession(entrySource, entryParams);
      setInitialized(true);
    }
  }, [initialized, entrySource, entryParams, initSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = async (content: string) => {
    if (!content.trim() || isLimitReached) return;
    await sendMessage(content);
  };

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center text-white text-lg">
              🤖
            </div>
            <div>
              <h1 className="text-white font-semibold text-sm">Jarvis</h1>
              <p className="text-gray-400 text-xs">Your AI Assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {session && (
              <span className="text-xs px-2 py-1 rounded-full bg-gray-800 text-gray-300 capitalize">
                {detectedStage.replace('_', ' ')}
              </span>
            )}
            {isDemoPackActive && (
              <span className="text-xs px-2 py-1 rounded-full bg-emerald-900/50 text-emerald-400 border border-emerald-700">
                Demo Pack
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && <ErrorBanner message={error} onDismiss={clearError} />}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {/* Welcome message if no messages yet */}
          {messages.length === 0 && !isLoading && !isTyping && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[80%]">
                <p className="text-gray-200 text-sm leading-relaxed">
                  Hello! I&apos;m Jarvis from PARWA — your AI customer care assistant.
                  I&apos;m here to help you experience what our AI agents can do for your
                  business. Would you like me to show you a demo, explain our pricing,
                  or just chat about what PARWA can do for you?
                </p>
              </div>
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg) => (
            <OnboardingJarvisMessage key={msg.id} message={msg} />
          ))}

          {/* Typing indicator */}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Limit reached card */}
          {isLimitReached && !isDemoPackActive && <LimitReachedCard />}

          {/* Demo Pack CTA when running low */}
          {!isLimitReached && remainingToday <= 5 && remainingToday > 0 && !isDemoPackActive && (
            <DemoPackCTA remaining={remainingToday} onPurchase={() => {}} />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Bottom bar: message counter + input */}
      <div className="border-t border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky bottom-0">
        <div className="max-w-3xl mx-auto">
          <MessageCounter remaining={remainingToday} total={isDemoPackActive ? 500 : 20} />
          <OnboardingJarvisInput
            onSend={handleSend}
            disabled={isLoading || isTyping || isLimitReached}
          />
        </div>
      </div>
    </div>
  );
}
