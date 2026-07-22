/**
 * PARWA VoiceConfigCard
 *
 * Settings card for voice channel configuration including:
 * - D3: Choose between Parwa-provided number or bring your own
 * - Parwa number: instant provisioning (no Twilio credentials needed)
 * - Bring own: client provides Twilio Account SID, Auth Token, Phone Number
 * - Caller ID name field (D3)
 * - Greeting style selector (D3)
 * - Language preference (D3)
 * - Enable/disable toggle
 * - Default variant selector
 * - Max duration setting
 * - Recording toggle
 * - TTS voice selector
 * - Transfer number
 */

'use client';

import { useState, useEffect } from 'react';
import {
  Settings, Phone, Shield, Volume2, Clock,
  PhoneForwarded, Loader2, Globe, User, MessageSquare,
  Sparkles, Key,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { voiceApi } from '@/lib/voice-api';
import type { VoiceChannelConfig, NumberSource, GreetingStyle } from '@/types/voice';
import toast from 'react-hot-toast';

interface VoiceConfigCardProps {
  open: boolean;
  onClose: () => void;
}

// ── Step indicator ──────────────────────────────────────────────────

type SetupStep = 'choose_source' | 'configure' | 'done';

export function VoiceConfigCard({ open, onClose }: VoiceConfigCardProps) {
  const [config, setConfig] = useState<VoiceChannelConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState<SetupStep>('choose_source');

  // D3: Number source
  const [numberSource, setNumberSource] = useState<NumberSource>('parwa_provided');

  // D3: Parwa-provided params
  const [areaCode, setAreaCode] = useState('');
  const [country, setCountry] = useState('US');

  // D3: Bring-own Twilio credentials
  const [twilioAccountSid, setTwilioAccountSid] = useState('');
  const [twilioAuthToken, setTwilioAuthToken] = useState('');
  const [twilioPhoneNumber, setTwilioPhoneNumber] = useState('');

  // D3: Caller ID and greeting
  const [callerIdName, setCallerIdName] = useState('');
  const [greetingStyle, setGreetingStyle] = useState<GreetingStyle>('professional');
  const [languagePreference, setLanguagePreference] = useState('en-US');

  // Channel settings
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
          // D3 fields
          setNumberSource(cfg.number_source || 'parwa_provided');
          setCallerIdName(cfg.caller_id_name || '');
          setGreetingStyle(cfg.greeting_style || 'professional');
          setLanguagePreference(cfg.language_preference || 'en-US');
          // Already configured — go to done step
          setStep('done');
        })
        .catch(() => {
          // Config may not exist yet — show setup
          setConfig(null);
          setStep('choose_source');
        })
        .finally(() => setLoading(false));
    }
  }, [open]);

  const handleCreateConfig = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        number_source: numberSource,
        is_enabled: true,
        default_variant: defaultVariant,
        max_call_duration_minutes: maxDuration,
        enable_recording: enableRecording,
        speech_language: speechLanguage,
        tts_voice: ttsVoice,
        caller_id_name: callerIdName || undefined,
        greeting_style: greetingStyle,
        language_preference: languagePreference,
        transfer_number: transferNumber || undefined,
      };

      if (numberSource === 'parwa_provided') {
        payload.area_code = areaCode || undefined;
        payload.country = country;
      } else {
        // Bring own — require Twilio credentials
        if (!twilioAccountSid || !twilioAuthToken || !twilioPhoneNumber) {
          toast.error('Twilio Account SID, Auth Token, and Phone Number are required');
          setSaving(false);
          return;
        }
        payload.twilio_account_sid = twilioAccountSid;
        payload.twilio_auth_token = twilioAuthToken;
        payload.twilio_phone_number = twilioPhoneNumber;
      }

      const result = await voiceApi.createConfig(payload as any);
      if (result.config) {
        setConfig(result.config);
        setStep('done');
        toast.success('Voice channel configured successfully!');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create voice config');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateConfig = async () => {
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
        caller_id_name: callerIdName || undefined,
        greeting_style: greetingStyle,
        language_preference: languagePreference,
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
              <p className="text-xs text-zinc-500 mt-0.5">
                {step === 'choose_source' && 'Step 1: Choose how to get your number'}
                {step === 'configure' && 'Step 2: Configure your voice channel'}
                {step === 'done' && 'Voice channel is configured'}
              </p>
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
            {/* ── Step 1: Choose Source (D3) ────────────────────────── */}
            {step === 'choose_source' && (
              <>
                <div className="space-y-3">
                  <p className="text-xs text-zinc-400">
                    Choose how you want to set up your voice number. You can use Parwa&apos;s built-in number or connect your own Twilio account.
                  </p>

                  {/* Option A: Parwa-provided */}
                  <button
                    onClick={() => { setNumberSource('parwa_provided'); setStep('configure'); }}
                    className={cn(
                      'w-full text-left p-4 rounded-xl border transition-all',
                      numberSource === 'parwa_provided'
                        ? 'bg-emerald-500/5 border-emerald-500/30'
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
                    )}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                        <Sparkles className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">Use Parwa&apos;s Number</p>
                        <p className="text-[10px] text-emerald-400">Recommended — Instant setup</p>
                      </div>
                    </div>
                    <p className="text-xs text-zinc-500 ml-12">
                      Click &quot;Enable Voice&quot; and get a number instantly. No Twilio account needed.
                      Parwa handles everything — provisioning, webhooks, and call routing.
                    </p>
                  </button>

                  {/* Option B: Bring own */}
                  <button
                    onClick={() => { setNumberSource('bring_own'); setStep('configure'); }}
                    className={cn(
                      'w-full text-left p-4 rounded-xl border transition-all',
                      numberSource === 'bring_own'
                        ? 'bg-blue-500/5 border-blue-500/30'
                        : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.12]'
                    )}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                        <Key className="w-4 h-4 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">Bring Your Own Number</p>
                        <p className="text-[10px] text-blue-400">For existing Twilio users</p>
                      </div>
                    </div>
                    <p className="text-xs text-zinc-500 ml-12">
                      Already have a Twilio number? Forward it to Parwa AI.
                      You&apos;ll need your Twilio Account SID, Auth Token, and Phone Number.
                    </p>
                  </button>
                </div>
              </>
            )}

            {/* ── Step 2: Configure ──────────────────────────────────── */}
            {step === 'configure' && (
              <>
                {/* Back button */}
                <button
                  onClick={() => setStep('choose_source')}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                >
                  ← Back to number source
                </button>

                {/* Source indicator */}
                <div className={cn(
                  'p-3 rounded-xl border',
                  numberSource === 'parwa_provided'
                    ? 'bg-emerald-500/5 border-emerald-500/20'
                    : 'bg-blue-500/5 border-blue-500/20'
                )}>
                  <div className="flex items-center gap-2">
                    {numberSource === 'parwa_provided' ? (
                      <Sparkles className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Key className="w-4 h-4 text-blue-400" />
                    )}
                    <span className="text-xs font-medium text-white">
                      {numberSource === 'parwa_provided' ? 'Parwa-provided number' : 'Bring your own number'}
                    </span>
                  </div>
                </div>

                {/* Bring-own: Twilio credentials */}
                {numberSource === 'bring_own' && (
                  <div className="space-y-3 p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                    <p className="text-xs font-medium text-zinc-300 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-blue-400" />
                      Twilio Credentials
                    </p>
                    <div>
                      <label className="text-xs text-zinc-400 mb-1 block">Account SID</label>
                      <input
                        type="text"
                        value={twilioAccountSid}
                        onChange={(e) => setTwilioAccountSid(e.target.value)}
                        placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                        className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/40"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 mb-1 block">Auth Token</label>
                      <input
                        type="password"
                        value={twilioAuthToken}
                        onChange={(e) => setTwilioAuthToken(e.target.value)}
                        placeholder="Your Twilio Auth Token"
                        className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/40"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 mb-1 block">Phone Number</label>
                      <input
                        type="tel"
                        value={twilioPhoneNumber}
                        onChange={(e) => setTwilioPhoneNumber(e.target.value)}
                        placeholder="+1234567890"
                        className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-blue-500/40"
                      />
                    </div>
                  </div>
                )}

                {/* Parwa-provided: Area code / country */}
                {numberSource === 'parwa_provided' && (
                  <div className="space-y-3 p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                    <p className="text-xs font-medium text-zinc-300 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-emerald-400" />
                      Number Preferences (Optional)
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-zinc-400 mb-1 block">Area Code</label>
                        <input
                          type="text"
                          value={areaCode}
                          onChange={(e) => setAreaCode(e.target.value)}
                          placeholder="e.g. 415"
                          maxLength={5}
                          className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-zinc-400 mb-1 block">Country</label>
                        <select
                          value={country}
                          onChange={(e) => setCountry(e.target.value)}
                          className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                        >
                          <option value="US">United States</option>
                          <option value="CA">Canada</option>
                          <option value="GB">United Kingdom</option>
                          <option value="IN">India</option>
                          <option value="AU">Australia</option>
                        </select>
                      </div>
                    </div>
                    <p className="text-[10px] text-zinc-600">
                      Leave area code empty for automatic assignment.
                    </p>
                  </div>
                )}

                {/* D3: Caller ID & Greeting */}
                <div className="space-y-3">
                  <p className="text-xs font-medium text-zinc-300 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-zinc-400" />
                    Caller Identity
                  </p>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1.5 block">Caller ID Name</label>
                    <input
                      type="text"
                      value={callerIdName}
                      onChange={(e) => setCallerIdName(e.target.value)}
                      placeholder="Your Company Name"
                      className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-zinc-400 mb-1.5 block flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        Greeting Style
                      </label>
                      <select
                        value={greetingStyle}
                        onChange={(e) => setGreetingStyle(e.target.value as GreetingStyle)}
                        className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                      >
                        <option value="professional">Professional</option>
                        <option value="friendly">Friendly</option>
                        <option value="casual">Casual</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 mb-1.5 block flex items-center gap-1">
                        <Globe className="w-3 h-3" />
                        Language
                      </label>
                      <select
                        value={languagePreference}
                        onChange={(e) => setLanguagePreference(e.target.value)}
                        className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                      >
                        <option value="en-US">English (US)</option>
                        <option value="en-IN">English (India)</option>
                        <option value="en-GB">English (UK)</option>
                        <option value="hi-IN">Hindi</option>
                        <option value="es-ES">Spanish</option>
                        <option value="fr-FR">French</option>
                        <option value="de-DE">German</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Default Variant */}
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Default AI Variant</label>
                  <select
                    value={defaultVariant}
                    onChange={(e) => setDefaultVariant(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                  >
                    <option value="mini">Mini — Basic AI agent</option>
                    <option value="parwa">Parwa — Smart AI with recommendations</option>
                    <option value="high">High — Fully autonomous AI</option>
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
              </>
            )}

            {/* ── Step 3: Done (existing config) ─────────────────────── */}
            {step === 'done' && config && (
              <>
                {/* Connection Status */}
                <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-emerald-400/60" />
                      <span className="text-xs text-zinc-400">
                        {config.number_source === 'parwa_provided' ? 'Parwa Number' : 'Your Twilio Account'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400" />
                      <span className="text-[10px] text-emerald-400">Connected</span>
                    </div>
                  </div>
                  <p className="text-[10px] text-zinc-600 mt-2 ml-6">
                    Number: {config.twilio_phone_number || config.parwa_phone_number}
                    {config.number_source === 'parwa_provided' && ' (Parwa-provisioned)'}
                  </p>
                </div>

                {/* Enable/Disable */}
                <ToggleRow
                  icon={<Phone className="w-4 h-4" />}
                  label="Enable Voice Channel"
                  description="Allow incoming and outgoing AI calls"
                  checked={isEnabled}
                  onChange={setIsEnabled}
                />

                {/* Caller ID Name */}
                <div>
                  <label className="text-xs text-zinc-400 mb-1.5 block">Caller ID Name</label>
                  <input
                    type="text"
                    value={callerIdName}
                    onChange={(e) => setCallerIdName(e.target.value)}
                    placeholder="Your Company Name"
                    className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40"
                  />
                </div>

                {/* Greeting Style + Language */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-400 mb-1.5 block">Greeting Style</label>
                    <select
                      value={greetingStyle}
                      onChange={(e) => setGreetingStyle(e.target.value as GreetingStyle)}
                      className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                    >
                      <option value="professional">Professional</option>
                      <option value="friendly">Friendly</option>
                      <option value="casual">Casual</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 mb-1.5 block">Language</label>
                    <select
                      value={languagePreference}
                      onChange={(e) => setLanguagePreference(e.target.value)}
                      className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                    >
                      <option value="en-US">English (US)</option>
                      <option value="en-IN">English (India)</option>
                      <option value="en-GB">English (UK)</option>
                      <option value="hi-IN">Hindi</option>
                    </select>
                  </div>
                </div>

                {/* Default Variant */}
                <div>
                  <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Default AI Variant</label>
                  <select
                    value={defaultVariant}
                    onChange={(e) => setDefaultVariant(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg bg-[#0F0F0F] border border-white/[0.06] text-sm text-white focus:outline-none focus:border-emerald-500/40"
                  >
                    <option value="mini">Mini — Basic AI agent</option>
                    <option value="parwa">Parwa — Smart AI with recommendations</option>
                    <option value="high">High — Fully autonomous AI</option>
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
              </>
            )}
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
          {step === 'configure' && (
            <button
              onClick={handleCreateConfig}
              disabled={saving}
              className="flex-1 h-10 rounded-lg bg-emerald-500 text-sm text-white font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {numberSource === 'parwa_provided' ? 'Get Number & Enable' : 'Connect & Enable'}
            </button>
          )}
          {step === 'done' && (
            <button
              onClick={handleUpdateConfig}
              disabled={saving}
              className="flex-1 h-10 rounded-lg bg-emerald-500 text-sm text-white font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Save Settings
            </button>
          )}
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
