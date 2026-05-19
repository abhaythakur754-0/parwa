/**
 * PARWA MakeCallDialog
 *
 * Modal dialog for initiating outbound voice calls.
 * Features: Phone number input with E.164 validation, variant tier selector,
 * optional custom message, and auto-close on success.
 */

'use client';

import { useState } from 'react';
import { Phone, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MakeCallDialogProps {
  open: boolean;
  onClose: () => void;
  onCall: (to: string, variant?: string, message?: string) => Promise<void>;
  defaultNumber?: string;
}

const VARIANT_OPTIONS = [
  { value: 'parwa', label: 'Mini', description: 'Basic AI agent' },
  { value: 'parwa_pro', label: 'Pro', description: 'Smart AI agent with recommendations' },
  { value: 'parwa_high', label: 'High', description: 'Fully autonomous AI agent' },
];

export function MakeCallDialog({ open, onClose, onCall, defaultNumber = '' }: MakeCallDialogProps) {
  const [phoneNumber, setPhoneNumber] = useState(defaultNumber);
  const [variant, setVariant] = useState('parwa');
  const [message, setMessage] = useState('');
  const [isCalling, setIsCalling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // E.164 validation: + followed by 7-15 digits
  const isValidPhone = /^\+?[1-9]\d{6,14}$/.test(phoneNumber.replace(/[\s\-()]/g, ''));

  const handleCall = async () => {
    if (!isValidPhone) {
      setError('Enter a valid phone number (E.164 format, e.g., +919652852014)');
      return;
    }

    setIsCalling(true);
    setError(null);

    try {
      await onCall(phoneNumber.replace(/[\s\-()]/g, ''), variant, message || undefined);
      // Reset and close on success
      setPhoneNumber(defaultNumber);
      setVariant('parwa');
      setMessage('');
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initiate call');
    } finally {
      setIsCalling(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-[#1A1A1A] border border-white/[0.08] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Phone className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Make a Call</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Initiate an outbound AI voice call</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Phone Number */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Phone Number <span className="text-red-400">*</span>
            </label>
            <input
              type="tel"
              value={phoneNumber}
              onChange={(e) => { setPhoneNumber(e.target.value); setError(null); }}
              placeholder="+919652852014"
              className={cn(
                'w-full h-10 px-3 rounded-lg bg-[#0F0F0F] border text-sm text-white placeholder:text-zinc-600 focus:outline-none transition-colors',
                error ? 'border-red-500/50 focus:border-red-500/70' : 'border-white/[0.06] focus:border-orange-500/40'
              )}
              autoFocus
            />
            <p className="text-[10px] text-zinc-600 mt-1">E.164 format: country code + number (e.g., +919652852014)</p>
          </div>

          {/* Variant Tier */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              AI Variant
            </label>
            <div className="grid grid-cols-3 gap-2">
              {VARIANT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setVariant(opt.value)}
                  className={cn(
                    'p-2.5 rounded-lg border text-center transition-all',
                    variant === opt.value
                      ? 'bg-orange-500/10 border-orange-500/30 text-orange-400'
                      : 'bg-white/[0.02] border-white/[0.06] text-zinc-500 hover:border-white/[0.1]'
                  )}
                >
                  <span className="block text-xs font-semibold">{opt.label}</span>
                  <span className="block text-[9px] mt-0.5 opacity-60">{opt.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Custom Message */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Custom Message <span className="text-zinc-600">(optional)</span>
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Optional greeting or context for the AI agent..."
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 transition-colors resize-none"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/10">
              <p className="text-xs text-red-300">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-3 p-5 border-t border-white/[0.06]">
          <button
            onClick={onClose}
            className="flex-1 h-10 rounded-lg bg-white/[0.05] border border-white/[0.06] text-sm text-zinc-400 font-medium hover:bg-white/[0.08] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCall}
            disabled={!isValidPhone || isCalling}
            className="flex-1 h-10 rounded-lg bg-gradient-to-r from-orange-500 to-orange-600 text-sm text-white font-medium hover:from-orange-400 hover:to-orange-500 disabled:opacity-40 transition-all flex items-center justify-center gap-2"
          >
            {isCalling ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Calling...
              </>
            ) : (
              <>
                <Phone className="w-4 h-4" />
                Call
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
