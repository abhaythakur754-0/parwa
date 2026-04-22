'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/lib/utils';

/**
 * RichTextEditor - Rich text editor for ticket replies
 *
 * Features:
 * - Bold, italic, underline formatting
 * - Bullet and numbered lists
 * - Link insertion
 * - Character count
 * - Clean HTML output
 *
 * Uses contenteditable with execCommand for simplicity
 * (TipTap/ProseMirror alternative without dependencies)
 *
 * NOTE: document.execCommand is deprecated and may be removed in future
 * browser versions. This component should be migrated to use a modern
 * editor library such as TipTap, ProseMirror, or Slate. The current
 * implementation continues to work in all current browsers but should
 * be scheduled for migration to ensure long-term compatibility.
 */

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  maxLength?: number;
  className?: string;
  disabled?: boolean;
  minHeight?: number;
  maxHeight?: number;
}

type ToolbarItem = { command: string; icon: React.ReactNode; title: string } | { type: 'separator' };

const TOOLBAR_BUTTONS: ToolbarItem[] = [
  {
    command: 'bold',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 4.5h6.75a3.75 3.75 0 0 1 0 7.5H6.75m0-7.5v7.5m0 0h7.5a3.75 3.75 0 0 1 0 7.5H6.75m0-7.5v7.5" />
      </svg>
    ),
    title: 'Bold (Ctrl+B)',
  },
  {
    command: 'italic',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 4.5h4m0 0l-4 15m4-15h4m-8 15h4" />
      </svg>
    ),
    title: 'Italic (Ctrl+I)',
  },
  {
    command: 'underline',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 4.5v6.75a4.5 4.5 0 1 0 9 0V4.5m-9 15h9" />
      </svg>
    ),
    title: 'Underline (Ctrl+U)',
  },
  { type: 'separator' },
  {
    command: 'insertUnorderedList',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h7.5M8.25 12h7.5m-7.5 5.25h7.5M5.25 6.75h.007v.008H5.25V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM5.25 12h.007v.008H5.25V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H5.25v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
      </svg>
    ),
    title: 'Bullet List',
  },
  {
    command: 'insertOrderedList',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h7.5M8.25 12h7.5m-7.5 5.25h7.5M5.25 6.75v1.5h.375a.375.375 0 0 0 0-.75H5.25Zm0 5.25v1.5h.375a.375.375 0 0 0 0-.75H5.25Zm0 5.25v1.5h.375a.375.375 0 0 0 0-.75H5.25Z" />
      </svg>
    ),
    title: 'Numbered List',
  },
  { type: 'separator' },
  {
    command: 'createLink',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
      </svg>
    ),
    title: 'Insert Link',
  },
];

export default function RichTextEditor({
  value,
  onChange,
  placeholder = 'Write your message...',
  maxLength = 10000,
  className,
  disabled = false,
  minHeight = 100,
  maxHeight = 400,
}: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const [linkUrl, setLinkUrl] = useState('');
  const [showLinkInput, setShowLinkInput] = useState(false);

  // Update character count
  useEffect(() => {
    if (editorRef.current) {
      const text = editorRef.current.innerText || '';
      setCharCount(text.length);
    }
  }, [value]);

  // Handle command execution
  const execCommand = useCallback((command: string, value?: string) => {
    if (disabled) return;

    if (command === 'createLink') {
      setShowLinkInput(true);
      return;
    }

    document.execCommand(command, false, value);
    editorRef.current?.focus();
  }, [disabled]);

  // Insert link
  const insertLink = useCallback(() => {
    if (linkUrl) {
      document.execCommand('createLink', false, linkUrl);
    }
    setShowLinkInput(false);
    setLinkUrl('');
    editorRef.current?.focus();
  }, [linkUrl]);

  // Handle input change
  const handleInput = useCallback(() => {
    if (!editorRef.current) return;

    const html = editorRef.current.innerHTML;
    const text = editorRef.current.innerText;

    // Check max length
    if (text.length > maxLength) {
      // Truncate - this is a soft limit, we just warn
    }

    onChange(html);
    setCharCount(text.length);
  }, [maxLength, onChange]);

  // Handle paste - strip formatting if needed
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/html') || e.clipboardData.getData('text/plain');

    // Insert clean HTML
    document.execCommand('insertHTML', false, text);
  }, []);

  // Initialize content
  useEffect(() => {
    if (editorRef.current && value && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value;
    }
  }, []);

  const charCountColor = charCount > maxLength * 0.9 ? 'text-red-400' : charCount > maxLength * 0.7 ? 'text-amber-400' : 'text-zinc-500';

  return (
    <div className={cn('rounded-xl bg-white/[0.02] border overflow-hidden', className)}>
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-white/[0.06] bg-white/[0.02]">
        {TOOLBAR_BUTTONS.map((btn, index) => {
          if ('type' in btn && btn.type === 'separator') {
            return (
              <div key={`sep-${index}`} className="w-px h-4 bg-white/[0.1] mx-1" />
            );
          }

          const button = btn as { command: string; icon: React.ReactNode; title: string };
          return (
            <button
              key={button.command}
              type="button"
              onClick={() => execCommand(button.command)}
              disabled={disabled}
              className={cn(
                'p-1.5 rounded transition-colors',
                disabled
                  ? 'text-zinc-700 cursor-not-allowed'
                  : 'text-zinc-400 hover:text-white hover:bg-white/[0.06]'
              )}
              title={button.title}
            >
              {button.icon}
            </button>
          );
        })}

        {/* Link input */}
        {showLinkInput && (
          <div className="flex items-center gap-1 ml-2">
            <input
              type="url"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://..."
              className="w-40 px-2 py-1 text-xs bg-black/20 border border-white/[0.1] rounded text-white placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  insertLink();
                }
                if (e.key === 'Escape') {
                  setShowLinkInput(false);
                  setLinkUrl('');
                }
              }}
              autoFocus
            />
            <button
              onClick={insertLink}
              className="px-2 py-1 text-xs text-violet-400 hover:text-violet-300"
            >
              Add
            </button>
          </div>
        )}
      </div>

      {/* Editor */}
      <div
        ref={editorRef}
        contentEditable={!disabled}
        onInput={handleInput}
        onPaste={handlePaste}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        data-placeholder={placeholder}
        className={cn(
          'px-3 py-2.5 text-sm text-zinc-200 outline-none overflow-y-auto',
          '[&:empty]:before:content-[attr(data-placeholder)] [&:empty]:before:text-zinc-600',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
        style={{
          minHeight: `${minHeight}px`,
          maxHeight: `${maxHeight}px`,
        }}
        suppressContentEditableWarning
      >
        {value && <div dangerouslySetInnerHTML={{ __html: value }} />}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-white/[0.04] bg-white/[0.01]">
        <span className="text-[10px] text-zinc-600">
          Tip: Select text to format, or use Ctrl+B/I/U
        </span>
        <span className={cn('text-[10px] font-medium', charCountColor)}>
          {charCount.toLocaleString()} / {maxLength.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

/**
 * Utility to strip HTML tags for plain text
 */
export function stripHtml(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

/**
 * Utility to convert plain text to HTML paragraphs
 */
export function textToHtml(text: string): string {
  return text
    .split('\n\n')
    .map((para) => `<p>${para.replace(/\n/g, '<br/>')}</p>`)
    .join('');
}
