/**
 * PARWA ChatInput Component — ZAI-style Clean Design
 *
 * Text input area with send button and knowledge base upload.
 * Handles keyboard shortcuts (Enter to send, Shift+Enter for newline),
 * auto-resize, and disabled states for limit reached / typing / loading.
 */

'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import { Send, ArrowUp, Sparkles, Zap, Paperclip, BookOpen, X, CheckCircle2, Loader2, FileText, CloudUpload, AlertCircle } from 'lucide-react';

interface ChatInputProps {
  /** Send message callback */
  onSend: (content: string) => void;
  /** Whether Jarvis is currently typing (disables send) */
  isTyping: boolean;
  /** Whether the user has reached the daily message limit */
  isLimitReached: boolean;
  /** Whether the session is still initializing */
  isLoading: boolean;
  /** Number of messages remaining today */
  remainingToday: number;
  /** Whether a demo pack is active */
  isDemoPackActive: boolean;
  /** Whether the user has paid for the upgrade */
  isPaid: boolean;
  /** Number of paid messages remaining */
  paidRemaining: number;
  /** Upgrade callback (triggers $1 purchase) */
  onUpgrade: () => void;
  /** Knowledge base upload callback */
  onKnowledgeBaseUpload?: (files: File[]) => Promise<void>;
  /** Whether knowledge base upload is in progress */
  isKnowledgeBaseUploading?: boolean;
  /** Uploaded knowledge base files */
  knowledgeBaseFiles?: Array<{ name: string; size: number; status: 'pending' | 'uploading' | 'done' | 'error' }>;
  /** Whether knowledge base is available */
  hasKnowledgeBase?: boolean;
}

const MAX_CHARS = 2000;

export function ChatInput({
  onSend,
  isTyping,
  isLimitReached,
  isLoading,
  remainingToday,
  isDemoPackActive,
  isPaid,
  paidRemaining,
  onUpgrade,
  onKnowledgeBaseUpload,
  isKnowledgeBaseUploading,
  knowledgeBaseFiles = [],
  hasKnowledgeBase,
}: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendingRef = useRef(false);
  const [showKbPopover, setShowKbPopover] = useState(false);
  const [kbSelectedFiles, setKbSelectedFiles] = useState<File[]>([]);
  const [kbError, setKbError] = useState<string | null>(null);
  const kbFileInputRef = useRef<HTMLInputElement>(null);
  const kbPopoverRef = useRef<HTMLDivElement>(null);

  const isDisabled = isTyping || isLoading || isLimitReached || !value.trim();
  const charCount = value.length;
  const isNearLimit = charCount > MAX_CHARS * 0.85;
  const isOverLimit = charCount > MAX_CHARS;

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const maxHeight = 120;
    const scrollH = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${scrollH}px`;

    if (textarea.scrollHeight > maxHeight) {
      textarea.style.overflowY = 'auto';
    } else {
      textarea.style.overflowY = 'hidden';
    }
  }, [value]);

  // Reset sending guard when typing completes
  useEffect(() => {
    if (!isTyping) sendingRef.current = false;
  }, [isTyping]);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isDisabled || isOverLimit) return;
    if (sendingRef.current) return;
    sendingRef.current = true;

    onSend(trimmed);
    setValue('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Re-focus after send
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
    });
  }, [value, isDisabled, isOverLimit, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter to send (without Shift)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
        return;
      }

      // Ctrl/Cmd + Enter as alternative send
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Close KB popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (kbPopoverRef.current && !kbPopoverRef.current.contains(e.target as Node)) {
        setShowKbPopover(false);
      }
    };
    if (showKbPopover) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showKbPopover]);

  // KB file validation
  const validateKbFile = useCallback((file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const validExts = ['pdf', 'txt', 'csv', 'md', 'docx', 'doc'];
    if (!validExts.includes(ext)) return `"${ext}" files not supported`;
    if (file.size > 10 * 1024 * 1024) return `"${file.name}" too large (max 10MB)`;
    return null;
  }, []);

  const handleKbFiles = useCallback((files: FileList | File[]) => {
    setKbError(null);
    const fileArray = Array.from(files);
    if (kbSelectedFiles.length + fileArray.length > 5) {
      setKbError('Maximum 5 files at a time');
      return;
    }
    const valid: File[] = [];
    for (const f of fileArray) {
      const err = validateKbFile(f);
      if (err) { setKbError(err); continue; }
      valid.push(f);
    }
    if (valid.length > 0) setKbSelectedFiles(prev => [...prev, ...valid]);
  }, [kbSelectedFiles, validateKbFile]);

  const handleKbUpload = useCallback(async () => {
    if (kbSelectedFiles.length === 0 || !onKnowledgeBaseUpload) return;
    try {
      await onKnowledgeBaseUpload(kbSelectedFiles);
      setKbSelectedFiles([]);
      setKbError(null);
      // Don't close popover immediately — show success state briefly
      setTimeout(() => setShowKbPopover(false), 1500);
    } catch {
      setKbError('Upload failed. Please try again.');
    }
  }, [kbSelectedFiles, onKnowledgeBaseUpload]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  return (
    <div className="shrink-0 bg-[#0D0D0D] px-4 pb-8 pt-2">
      <div className="max-w-3xl mx-auto">
        {/* Limit reached banner — $1 paywall CTA */}
        {isLimitReached && (
          <div className="mb-2 p-3 rounded-xl bg-gradient-to-br from-orange-500/10 to-amber-500/10 border border-orange-500/20">
            {!isPaid ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-orange-400 shrink-0" />
                  <p className="text-sm font-medium text-white/90">
                    Free messages completed for today
                  </p>
                </div>
                <p className="text-xs text-white/50 mb-3">
                  Upgrade for 40 more messages + a 2-min AI voice call
                </p>
                <button
                  onClick={onUpgrade}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-r from-orange-500 to-amber-500 text-white text-sm font-semibold hover:from-orange-400 hover:to-amber-400 transition-all shadow-lg shadow-orange-500/20 active:scale-[0.98]"
                >
                  <Zap className="w-4 h-4" />
                  Upgrade — $1
                </button>
                <p className="text-[10px] text-white/30 mt-2 text-center">
                  Resets in 24hrs
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-4 h-4 text-amber-400 shrink-0" />
                  <p className="text-sm font-medium text-amber-200/90">
                    Pro messages: {paidRemaining} remaining
                  </p>
                </div>
                {paidRemaining <= 5 && (
                  <p className="text-[10px] text-amber-400/50 mt-1">
                    Resets in 24hrs
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2">
          {/* Knowledge base upload button + popover */}
          {onKnowledgeBaseUpload && (
            <div className="relative" ref={kbPopoverRef}>
              <button
                onClick={() => setShowKbPopover(prev => !prev)}
                className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 mb-0.5 ${
                  hasKnowledgeBase
                    ? 'bg-orange-500/15 border border-orange-500/25 text-orange-400'
                    : showKbPopover
                      ? 'bg-orange-500/10 border border-orange-500/20 text-orange-400'
                      : 'bg-white/[0.04] border border-white/10 text-white/30 hover:text-white/50 hover:bg-white/[0.06]'
                }`}
                title="Upload Knowledge Base"
                aria-label="Upload knowledge base files"
              >
                <BookOpen className="w-4 h-4" />
              </button>

              {/* KB Upload Popover */}
              {showKbPopover && (
                <div className="absolute bottom-full left-0 mb-2 w-72 rounded-xl border border-orange-500/15 bg-[#1A1A1A] shadow-2xl shadow-black/50 p-3 z-50 animate-in fade-in slide-in-from-bottom-1 duration-150">
                  {/* Header */}
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-7 h-7 rounded-lg bg-orange-500/10 flex items-center justify-center">
                      <BookOpen className="w-3.5 h-3.5 text-orange-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-white/80">Knowledge Base</p>
                      <p className="text-[10px] text-white/40">Help Jarvis learn your business</p>
                    </div>
                    <button
                      onClick={() => setShowKbPopover(false)}
                      className="w-6 h-6 rounded-md flex items-center justify-center text-white/30 hover:text-white/60 hover:bg-white/5 transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Already uploaded files */}
                  {knowledgeBaseFiles.length > 0 && (
                    <div className="mb-2 space-y-1">
                      {knowledgeBaseFiles.map((f, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[10px]">
                          {f.status === 'done' ? (
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                          ) : f.status === 'uploading' ? (
                            <Loader2 className="w-3 h-3 text-orange-400 animate-spin shrink-0" />
                          ) : (
                            <FileText className="w-3 h-3 text-white/30 shrink-0" />
                          )}
                          <span className="text-white/50 truncate">{f.name}</span>
                          {f.status === 'done' && <span className="text-emerald-400/60 shrink-0 ml-auto">ready</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Drop zone / file select */}
                  <div
                    onClick={() => kbFileInputRef.current?.click()}
                    className="cursor-pointer rounded-lg border-2 border-dashed border-white/10 hover:border-orange-400/30 hover:bg-white/[0.02] p-3 text-center transition-all"
                  >
                    <CloudUpload className="w-5 h-5 mx-auto mb-1 text-white/20" />
                    <p className="text-[11px] text-white/50">Click to select files</p>
                    <p className="text-[9px] text-white/25">PDF, TXT, CSV, DOCX, MD · Max 10MB</p>
                  </div>

                  <input
                    ref={kbFileInputRef}
                    type="file"
                    accept=".pdf,.txt,.csv,.md,.docx,.doc"
                    multiple
                    className="hidden"
                    onChange={(e) => e.target.files && handleKbFiles(e.target.files)}
                  />

                  {/* Selected files to upload */}
                  {kbSelectedFiles.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {kbSelectedFiles.map((file, i) => (
                        <div key={i} className="flex items-center gap-1.5 p-1.5 rounded-md bg-white/[0.03] border border-white/5">
                          <FileText className="w-3.5 h-3.5 text-orange-400/60 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-[10px] text-white/70 truncate">{file.name}</p>
                            <p className="text-[9px] text-white/30">{formatSize(file.size)}</p>
                          </div>
                          <button
                            onClick={(e) => { e.stopPropagation(); setKbSelectedFiles(prev => prev.filter((_, idx) => idx !== i)); }}
                            className="w-4 h-4 rounded flex items-center justify-center hover:bg-white/10 transition-colors"
                          >
                            <X className="w-2.5 h-2.5 text-white/30" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Error */}
                  {kbError && (
                    <p className="text-[10px] text-red-300/70 mt-1.5 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      {kbError}
                    </p>
                  )}

                  {/* Upload button */}
                  {kbSelectedFiles.length > 0 && (
                    <button
                      onClick={handleKbUpload}
                      disabled={isKnowledgeBaseUploading}
                      className="mt-2 w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-orange-600 text-white text-xs font-semibold hover:from-orange-400 hover:to-orange-500 disabled:opacity-40 transition-all shadow-lg shadow-orange-500/15 active:scale-[0.98]"
                    >
                      {isKnowledgeBaseUploading ? (
                        <>
                          <Loader2 className="w-3 h-3 animate-spin" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <CloudUpload className="w-3 h-3" />
                          Upload {kbSelectedFiles.length} file{kbSelectedFiles.length !== 1 ? 's' : ''}
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex-1 relative group">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isLoading
                  ? 'Connecting...'
                  : isLimitReached
                    ? 'Taking a break — back soon!'
                    : 'Ask Jarvis anything...'
              }
              disabled={isTyping || isLoading || isLimitReached}
              rows={1}
              maxLength={MAX_CHARS + 50}
              className="w-full resize-none rounded-2xl bg-white/[0.04] border border-white/10 text-[15px] text-white px-4 py-4 pr-14 placeholder:text-white/20 focus:outline-none focus:border-orange-500/30 focus:ring-1 focus:ring-orange-500/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed leading-relaxed"
            />

            {/* Character counter (visible when near limit) */}
            {(isNearLimit || isOverLimit) && (
              <span
                className={`absolute bottom-3 right-14 text-[10px] ${
                  isOverLimit
                    ? 'text-red-400'
                    : 'text-white/30'
                }`}
              >
                {charCount}/{MAX_CHARS}
              </span>
            )}

            {/* Send button */}
            <div className="absolute right-2 bottom-2">
              <button
                onClick={handleSend}
                disabled={isDisabled || isOverLimit}
                className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 ${
                  isDisabled || isOverLimit
                    ? 'bg-white/[0.05] text-white/20 cursor-not-allowed'
                    : 'bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/20 hover:shadow-orange-500/30 hover:scale-[1.02] active:scale-[0.98]'
                }`}
                title={
                  isLimitReached
                    ? 'Daily limit reached'
                    : isTyping
                      ? 'Jarvis is typing...'
                      : 'Send message'
                }
                aria-label="Send message"
              >
                {isTyping ? (
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                ) : value.trim() ? (
                  <ArrowUp className="w-4 h-4" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Remaining messages hint */}
        <div className="flex items-center justify-between mt-1.5 px-1">
          {!isLimitReached && remainingToday > 0 && (
            <p className="text-[10px] text-white/20">
              {isPaid
                ? `${paidRemaining} Pro message${paidRemaining !== 1 ? 's' : ''} remaining`
                : `${remainingToday} message${remainingToday !== 1 ? 's' : ''} remaining today`}
            </p>
          )}
          {hasKnowledgeBase && (
            <p className="text-[10px] text-orange-400/40">
              Knowledge base active
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
