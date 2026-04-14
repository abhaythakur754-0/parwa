'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  ChevronDown,
  Loader2,
  Plug,
  AlertCircle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type {
  ChannelConfig,
  ChannelTestResult,
  UpdateChannelConfigPayload,
} from '@/lib/channels-api';

// ── Channel Icon Mapping ───────────────────────────────────────────────

const channelIcons: Record<string, string> = {
  email: '\u2709\uFE0F',
  chat: '\uD83D\uDCAC',
  sms: '\uD83D\uDCF1',
  voice: '\uD83C\uDFA4',
  whatsapp: '\uD83D\uDCAC',
  messenger: '\uD83D\uDCE8',
  twitter: '\uD83D\uDC26',
  instagram: '\uD83D\uDCF8',
  telegram: '\u2708\uFE0F',
  slack: '\uD83D\uDCE1',
  webchat: '\uD83C\uDF10',
};

const channelCategoryColors: Record<string, string> = {
  email: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  chat: 'bg-green-500/15 text-green-400 border-green-500/25',
  sms: 'bg-purple-500/15 text-purple-400 border-purple-500/25',
  voice: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  social: 'bg-pink-500/15 text-pink-400 border-pink-500/25',
};

// ── Props ──────────────────────────────────────────────────────────────

interface ChannelCardProps {
  channel: ChannelConfig;
  onToggle: (channelType: string, enabled: boolean) => void;
  onSave: (
    channelType: string,
    payload: UpdateChannelConfigPayload,
  ) => Promise<void>;
  onTest: (channelType: string) => Promise<ChannelTestResult | null>;
  isSaving: boolean;
}

// ── Component ──────────────────────────────────────────────────────────

export default function ChannelCard({
  channel,
  onToggle,
  onSave,
  onTest,
  isSaving,
}: ChannelCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [testResult, setTestResult] = useState<ChannelTestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  // Local state for editable fields
  const [autoCreateTicket, setAutoCreateTicket] = useState(
    channel.auto_create_ticket,
  );
  const [charLimit, setCharLimit] = useState(
    channel.char_limit?.toString() ?? '',
  );
  const [allowedFileTypes, setAllowedFileTypes] = useState(
    channel.allowed_file_types.join(', '),
  );
  const [maxFileSize, setMaxFileSize] = useState(
    (channel.max_file_size / (1024 * 1024)).toString(),
  );

  const icon = channelIcons[channel.channel_type] ?? '\uD83D\uDCE1';
  const categoryColor =
    channelCategoryColors[channel.channel_category] ??
    'bg-gray-500/15 text-gray-400 border-gray-500/25';

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await onTest(channel.channel_type);
      setTestResult(result);
    } catch {
      setTestResult({
        channel_type: channel.channel_type,
        success: false,
        message: 'Connection test failed',
        tested_at: new Date().toISOString(),
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    const payload: UpdateChannelConfigPayload = {
      auto_create_ticket: autoCreateTicket,
      char_limit: charLimit ? parseInt(charLimit, 10) : null,
      allowed_file_types: allowedFileTypes
        .split(',')
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean),
      max_file_size: maxFileSize
        ? parseInt(maxFileSize, 10) * 1024 * 1024
        : undefined,
    };
    await onSave(channel.channel_type, payload);
  };

  const hasChanges =
    autoCreateTicket !== channel.auto_create_ticket ||
    (channel.char_limit ?? '').toString() !== charLimit ||
    channel.allowed_file_types.join(', ') !== allowedFileTypes ||
    (channel.max_file_size / (1024 * 1024)).toString() !== maxFileSize;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          'rounded-xl border transition-all duration-300',
          channel.is_enabled
            ? 'bg-[#1A1A1A] border-white/[0.08] hover:border-white/[0.15]'
            : 'bg-[#111111] border-white/[0.04] hover:border-white/[0.08] opacity-80',
          isOpen && 'border-[#FF7F11]/30',
        )}
      >
        {/* Card Header - Always visible */}
        <div className="p-4 sm:p-5">
          <CollapsibleTrigger asChild>
            <button className="w-full flex items-center justify-between group focus-visible-ring rounded-lg">
              <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                {/* Channel Icon */}
                <div
                  className={cn(
                    'w-10 h-10 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center text-lg sm:text-xl shrink-0 transition-colors duration-300',
                    channel.is_enabled
                      ? 'bg-white/[0.06]'
                      : 'bg-white/[0.03]',
                  )}
                >
                  {icon}
                </div>

                {/* Channel Info */}
                <div className="min-w-0 text-left">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-white font-semibold text-sm sm:text-base capitalize">
                      {channel.channel_type}
                    </h3>
                    <Badge
                      variant="outline"
                      className={cn(
                        'text-[10px] font-semibold px-2 py-0 rounded-full border',
                        categoryColor,
                      )}
                    >
                      {channel.channel_category}
                    </Badge>
                  </div>
                  <p className="text-gray-500 text-xs sm:text-sm truncate">
                    {channel.description}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 sm:gap-4 shrink-0">
                {/* Status indicator */}
                <div className="hidden sm:flex items-center gap-2">
                  {testResult && (
                    <div className="flex items-center gap-1.5">
                      {testResult.success ? (
                        <CheckCircle2 className="w-4 h-4 text-green-400" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-400" />
                      )}
                    </div>
                  )}
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full transition-colors duration-300',
                      channel.is_enabled ? 'bg-green-400' : 'bg-gray-600',
                    )}
                  />
                  <span
                    className={cn(
                      'text-xs font-medium',
                      channel.is_enabled ? 'text-green-400' : 'text-gray-500',
                    )}
                  >
                    {channel.is_enabled ? 'Active' : 'Disabled'}
                  </span>
                </div>

                {/* Toggle Switch */}
                <div onClick={(e) => e.stopPropagation()}>
                  <Switch
                    checked={channel.is_enabled}
                    onCheckedChange={(checked) =>
                      onToggle(channel.channel_type, checked)
                    }
                    aria-label={`Toggle ${channel.channel_type}`}
                  />
                </div>

                {/* Expand Arrow */}
                <ChevronDown
                  className={cn(
                    'w-4 h-4 text-gray-500 transition-transform duration-300',
                    isOpen && 'rotate-180',
                  )}
                />
              </div>
            </button>
          </CollapsibleTrigger>
        </div>

        {/* Expanded Settings */}
        <CollapsibleContent>
          <div className="px-4 sm:px-5 pb-4 sm:pb-5 border-t border-white/[0.06] pt-4">
            {/* Test Connection Button + Status */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2">
                <Plug className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-400 font-medium">
                  Connection Status
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTest}
                disabled={isTesting || !channel.is_enabled}
                className="bg-white/[0.05] border-white/[0.1] text-gray-300 hover:text-white hover:bg-white/[0.1] text-xs rounded-lg h-8 px-3"
              >
                {isTesting ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Plug className="w-3.5 h-3.5 mr-1.5" />
                )}
                Test Connection
              </Button>
            </div>

            {/* Test Result */}
            {testResult && (
              <div
                className={cn(
                  'flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-sm mb-5',
                  testResult.success
                    ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20',
                )}
              >
                {testResult.success ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 shrink-0" />
                )}
                <span>{testResult.message}</span>
              </div>
            )}

            {/* Settings Form */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Auto Create Ticket */}
              <div className="flex items-center justify-between p-3.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <div>
                  <p className="text-sm text-white font-medium">
                    Auto-create Tickets
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Automatically create tickets from incoming messages
                  </p>
                </div>
                <Switch
                  checked={autoCreateTicket}
                  onCheckedChange={setAutoCreateTicket}
                  aria-label="Auto-create tickets"
                />
              </div>

              {/* Character Limit */}
              <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <label
                  htmlFor={`charlimit-${channel.channel_type}`}
                  className="text-sm text-white font-medium block mb-1"
                >
                  Character Limit
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Max chars per message (leave empty for no limit)
                </p>
                <input
                  id={`charlimit-${channel.channel_type}`}
                  type="number"
                  value={charLimit}
                  onChange={(e) => setCharLimit(e.target.value)}
                  placeholder="No limit"
                  className="w-full bg-[#0D0D0D] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-[#FF7F11]/50 transition-colors"
                />
              </div>

              {/* Allowed File Types */}
              <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/[0.06] sm:col-span-2">
                <label
                  htmlFor={`filetypes-${channel.channel_type}`}
                  className="text-sm text-white font-medium block mb-1"
                >
                  Allowed File Types
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Comma-separated extensions (e.g. pdf, doc, png, jpg)
                </p>
                <input
                  id={`filetypes-${channel.channel_type}`}
                  type="text"
                  value={allowedFileTypes}
                  onChange={(e) => setAllowedFileTypes(e.target.value)}
                  placeholder="pdf, doc, png, jpg"
                  className="w-full bg-[#0D0D0D] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-[#FF7F11]/50 transition-colors"
                />
              </div>

              {/* Max File Size */}
              <div className="p-3.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                <label
                  htmlFor={`maxfilesize-${channel.channel_type}`}
                  className="text-sm text-white font-medium block mb-1"
                >
                  Max File Size
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Maximum upload size in MB
                </p>
                <input
                  id={`maxfilesize-${channel.channel_type}`}
                  type="number"
                  value={maxFileSize}
                  onChange={(e) => setMaxFileSize(e.target.value)}
                  placeholder="5"
                  min="1"
                  max="100"
                  className="w-full bg-[#0D0D0D] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-[#FF7F11]/50 transition-colors"
                />
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end mt-5 pt-4 border-t border-white/[0.06]">
              <Button
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                className={cn(
                  'rounded-lg text-sm font-medium px-6 transition-all duration-300',
                  hasChanges
                    ? 'bg-gradient-to-r from-[#FF7F11] to-orange-500 hover:from-orange-500 hover:to-orange-400 text-white shadow-lg shadow-[#FF7F11]/25'
                    : 'bg-white/[0.05] text-gray-500 cursor-not-allowed',
                )}
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                Save Configuration
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
