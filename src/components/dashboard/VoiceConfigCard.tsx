/**
 * PARWA VoiceConfigCard
 *
 * Settings card for voice channel configuration including:
 * - Twilio credentials (masked)
 * - Enable/disable toggle
 * - Default variant selector
 * - Max duration setting
 * - Recording toggle
 * - TTS voice selector
 * - Transfer number
 */

'use client';

import { useState, useEffect } from 'react';
import { Settings, Phone, Shield, Volume2, Clock, PhoneForwarded, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { voiceApi } from '@/lib/voice-api';
import type { VoiceChannelConfig } from '@/types/voice';
import toast from 'react-hot-toast';

interface VoiceConfigCardProps {
  open: boolean;
  onClose: () => void;
}

export function VoiceConfigCard({ open, onClose }: VoiceConfigCardProps) {
  const [config, setConfig] = useState<VoiceChannelConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [isEnabled, setIsEnabled] = useState(false);
  const [defaultVariant, setDefaultVariant] = useState('parwa');
  const [maxDuration, setMaxDuration] = useState(30);
  const [enableRecording, setEnableRecording] = useState(true);
  const [speechLanguage, setSpeechLanguage] = useState('en');
  const [ttsVoice, setTtsVoice] = useState('Polly.Matthew');
  const [transferNumber, setTransferNumber] = useState('');

  // Load config
  useEffect(() => {
    if (open) {
      setLoading(true);
      voiceApi.getConfig()
        .then((cfg) => {
          setConfig(cfg);
          setIsEnabled(cfg.is_enabled);
          setDefaultVariant(cfg.default_variant);
          setMaxDuration(cfg.max_call_duration_minutes);
          setEnableRecording(cfg.enable_recording);
          setSpeechLanguage(cfg.speech_language);
          setTtsVoice(cfg.tts_voice);
          setTransferNumber(cfg.transfer_number || '');
        })
        .catch(() => {
          // Config may not exist yet — show defaults
          setConfig(null);
        })
        .finally(() => setLoading(false));
    }
  }, [open]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await voiceApi.updateConfig({
        is_enabled: isEnabled,
        default_variant: defaultVariant,
        max_call_duration_minutes: maxDuration,
        enable_recording: enableRecording,
        speech_language: speechLanguage,
        tts_voice: ttsVoice,
        transfer_number: transferNumber || undefined,
      });
      toast.success('Voice config updated');
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update config');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg mx-4 rounded-2xl bg-[#1A1A1A] border border-white/[0.08] shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-[#1A1A1A] border-b border-white/[0.06] p-5 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <Settings className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Voice Channel Settings</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Configure your AI voice call settings</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-emerald-400" />
          </div>
        ) : (
          <div className="p-5 space-y-5">
            {/* Twilio Status */}
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-emerald-400/60" />
                  <span className="text-xs text-zinc-400">Twilio Connection</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  <span className="text-[10px] text-emerald-400">Connected</span>
                </div>
              </div>
              {config && (
                <p className="text-[10px] text-zinc-600 mt-2 ml-6">
                  Number: {config.twilio_phone_number}
                </p>
              )}
            </div>

            {/* Enable/Disable */}
            <ToggleRow
              icon={<Phone className="w-4 h-4" />}
              label="Enable Voice Channel"
              description="Allow incoming and outgoing AI calls"
              checked={isEnabled}
              onChange={setIsEnabled}
            />

            {/* Default Variant */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Default AI Variant</label>
              <select
                value={defaultVariant}
                onChange={(e) => setDefaultVariant(e.target.value)}
                className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
              >
                <option value="parwa">Mini — Basic AI agent</option>
                <option value="parwa_pro">Pro — Smart AI with recommendations</option>
                <option value="parwa_high">High — Fully autonomous AI</option>
              </select>
            </div>

            {/* Max Duration */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Max Call Duration (minutes)</label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={1}
                  max={60}
                  value={maxDuration}
                  onChange={(e) => setMaxDuration(Number(e.target.value))}
                  className="flex-1 accent-emerald-500"
                />
                <span className="text-sm text-white/70 font-mono w-10 text-right">{maxDuration}m</span>
              </div>
            </div>

            {/* Recording Toggle */}
            <ToggleRow
              icon={<Volume2 className="w-4 h-4" />}
              label="Enable Call Recording"
              description="Record calls for quality and training"
              checked={enableRecording}
              onChange={setEnableRecording}
            />

            {/* TTS Voice */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">TTS Voice</label>
              <select
                value={ttsVoice}
                onChange={(e) => setTtsVoice(e.target.value)}
                className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
              >
                <option value="Polly.Matthew">Matthew (Male, US)</option>
                <option value="Polly.Joanna">Joanna (Female, US)</option>
                <option value="Polly.Brian">Brian (Male, UK)</option>
                <option value="Polly.Amy">Amy (Female, UK)</option>
                <option value="Polly.Aditi">Aditi (Female, Hindi)</option>
              </select>
            </div>

            {/* Transfer Number */}
            <div>
              <label className="text-xs font-medium text-zinc-400 mb-1.5 block">
                <div className="flex items-center gap-1.5">
                  <PhoneForwarded className="w-3.5 h-3.5" />
                  Transfer Number
                </div>
              </label>
              <input
                type="tel"
                value={transferNumber}
                onChange={(e) => setTransferNumber(e.target.value)}
                placeholder="+919652852014"
                className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40"
              />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center gap-3 p-5 border-t border-white/[0.06]">
          <button
            onClick={onClose}
            className="flex-1 h-10 rounded-lg bg-white/[0.05] border border-white/[0.06] text-sm text-zinc-400 font-medium hover:bg-white/[0.08] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 h-10 rounded-lg bg-emerald-500 text-sm text-white font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Toggle Row ──────────────────────────────────────────────────────

function ToggleRow({
  icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onChange: (val: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-white/30">
          {icon}
        </div>
        <div>
          <p className="text-sm text-white/80">{label}</p>
          <p className="text-[10px] text-zinc-600">{description}</p>
        </div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative w-11 h-6 rounded-full transition-colors duration-300 shrink-0',
          checked ? 'bg-emerald-500' : 'bg-white/[0.1]'
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
            checked ? 'translate-x-5' : 'translate-x-0'
          )}
        />
      </button>
    </div>
  );
}
