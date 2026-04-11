/**
 * PARWA DemoCallCard (Week 6 — Day 4 Phase 6)
 *
 * Phone input + OTP verification + Call button + 3-min timer.
 * Metadata: { phone?: string, call_id?: string, duration_limit?: number }
 * Uses useJarvisChat: initiateDemoCall
 */

'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Phone, PhoneOff, Loader2, Shield, Clock } from 'lucide-react';

interface DemoCallCardProps {
  metadata: Record<string, unknown>;
  onInitiateCall: (phone: string) => Promise<void>;
  callStatus?: 'idle' | 'initiating' | 'calling' | 'completed' | 'failed';
  callDuration?: number;
}

export function DemoCallCard({
  metadata,
  onInitiateCall,
  callStatus = 'idle',
  callDuration = 0,
}: DemoCallCardProps) {
  const [phone, setPhone] = useState((metadata.phone as string) || '');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Timer for active call — uses Date.now() to handle tab backgrounding
  useEffect(() => {
    if (callStatus === 'calling') {
      startTimeRef.current = Date.now();
      const tick = () => setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000));
      tick();
      timerRef.current = setInterval(tick, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callStatus]);

  // Focus phone input on mount
  useEffect(() => {
    if (callStatus === 'idle' && !phone) inputRef.current?.focus();
  }, [callStatus, phone]);

  const formatPhone = useCallback((value: string) => {
    const digits = value.replace(/\D/g, '').slice(0, 15);
    return digits;
  }, []);

  const formatTime = useCallback((seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }, []);

  const handleCall = async () => {
    const digits = formatPhone(phone);
    if (digits.length < 7) return;
    await onInitiateCall(digits);
  };

  const durationLimit = (metadata.duration_limit as number) || 180; // 3 min default

  // Calling state — show timer
  if (callStatus === 'calling') {
    const isTimeUp = elapsed >= durationLimit;

    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-3">
          <div className={`w-8 h-8 rounded-lg ${isTimeUp ? 'bg-red-500/10' : 'bg-emerald-500/10'} flex items-center justify-center`}>
            <Phone className={`w-4 h-4 ${isTimeUp ? 'text-red-400' : 'text-emerald-400 animate-pulse'}`} />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-white">
              {isTimeUp ? 'Call Ended' : 'Demo Call Active'}
            </h3>
            <p className="text-[10px] text-white/40">{phone}</p>
          </div>
          <div className="flex items-center gap-1 text-xs font-mono text-white/60">
            <Clock className="w-3 h-3" />
            {formatTime(Math.min(elapsed, durationLimit))}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1 rounded-full bg-white/5 mb-3 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${isTimeUp ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min((elapsed / durationLimit) * 100, 100)}%` }}
          />
        </div>

        <p className="text-[10px] text-white/30 text-center">
          {isTimeUp
            ? 'Your 3-minute demo call has ended.'
            : `${formatTime(durationLimit - elapsed)} remaining · Max ${formatTime(durationLimit)}`}
        </p>
      </div>
    );
  }

  // Completed
  if (callStatus === 'completed') {
    return (
      <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <PhoneOff className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">Call Complete</h3>
            <p className="text-[10px] text-white/40">Duration: {formatTime(callDuration || elapsed)}</p>
          </div>
        </div>
        <p className="text-xs text-white/50 text-center">
          Hope you enjoyed the demo! Ask Jarvis for the next steps.
        </p>
      </div>
    );
  }

  // Failed
  if (callStatus === 'failed') {
    return (
      <div className="glass rounded-xl p-4 border border-red-500/15 max-w-sm w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
            <PhoneOff className="w-4 h-4 text-red-400" />
          </div>
          <h3 className="text-sm font-semibold text-red-200">Call Failed</h3>
        </div>
        <p className="text-xs text-white/50 text-center mb-3">
          Could not connect. Please check your phone number and try again.
        </p>
        <button
          onClick={handleCall}
          className="w-full py-2 rounded-lg bg-white/5 border border-white/10 text-xs text-white/60 hover:bg-white/10 transition-all"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Idle / Initiating — phone input
  return (
    <div className="glass rounded-xl p-4 border border-emerald-500/15 max-w-sm w-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
          <Phone className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-white">Try a Demo Call</h3>
          <p className="text-[10px] text-white/40">3-minute AI-powered demo call</p>
        </div>
      </div>

      {/* Features */}
      <div className="space-y-1 mb-3">
        <Feature text="Hear how PARWA sounds in a real call" />
        <Feature text="Ask questions about features & pricing" />
        <Feature text="Completely free, no commitment" />
      </div>

      {/* Phone input */}
      <div className="flex gap-2">
        <input
          ref={inputRef}
          type="tel"
          value={phone}
          onChange={(e) => setPhone(formatPhone(e.target.value))}
          placeholder="Enter phone number"
          className="flex-1 px-3 py-2.5 rounded-lg bg-white/[0.05] border border-white/10 text-white text-sm placeholder:text-white/25 focus:outline-none focus:border-emerald-500/30"
        />
        <button
          onClick={handleCall}
          disabled={callStatus === 'initiating' || formatPhone(phone).length < 7}
          className="px-4 py-2.5 rounded-lg bg-gradient-to-r from-emerald-500 to-emerald-600 text-white text-xs font-medium hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-40 transition-all active:scale-[0.98] flex items-center gap-1.5"
        >
          {callStatus === 'initiating' ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Phone className="w-3.5 h-3.5" />
          )}
          Call
        </button>
      </div>

      {/* Secure note */}
      <p className="text-[10px] text-white/25 text-center mt-2 flex items-center justify-center gap-1">
        <Shield className="w-3 h-3" />
        Your number is used only for this demo call
      </p>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 px-1">
      <div className="w-1 h-1 rounded-full bg-emerald-400/60 shrink-0" />
      <span className="text-[11px] text-white/50">{text}</span>
    </div>
  );
}
