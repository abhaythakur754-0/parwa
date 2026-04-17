'use client';

import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import RichTextEditor from './RichTextEditor';
import TemplateSelector, { type Template } from './TemplateSelector';
import toast from 'react-hot-toast';

/**
 * ReplyBox - Enhanced reply component with rich text and templates
 *
 * Features:
 * - Rich text editor with formatting
 * - Template selector with variable filling
 * - Reply/Note mode toggle
 * - Signature auto-append
 * - File attachments (UI)
 */

interface ReplyBoxProps {
  ticketId: string;
  onSend: (content: string, isNote?: boolean) => Promise<void>;
  className?: string;
  defaultMode?: 'reply' | 'note';
  customerName?: string;
  agentName?: string;
  companyName?: string;
  ticketIdDisplay?: string;
}

export default function ReplyBox({
  ticketId,
  onSend,
  className,
  defaultMode = 'reply',
  customerName = 'Customer',
  agentName = 'Support Agent',
  companyName = 'Support',
  ticketIdDisplay = '',
}: ReplyBoxProps) {
  const [content, setContent] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [mode, setMode] = useState<'reply' | 'note'>(defaultMode);
  const [showTemplates, setShowTemplates] = useState(false);
  const [appendSignature, setAppendSignature] = useState(true);

  // Signature template
  const signature = `\n\nBest regards,\n${agentName}\n${companyName} Support Team`;

  // Default variables for templates
  const defaultVariables = {
    customer_name: customerName,
    agent_name: agentName,
    company_name: companyName,
    ticket_id: ticketIdDisplay || ticketId.slice(0, 8),
    response_time: '24 hours',
  };

  // Handle send
  const handleSend = async () => {
    const plainText = stripHtml(content);
    if (!plainText.trim()) {
      toast.error('Please enter a message');
      return;
    }

    setIsSending(true);
    try {
      // Append signature if in reply mode and enabled
      let finalContent = content;
      if (mode === 'reply' && appendSignature) {
        finalContent += signature;
      }

      await onSend(finalContent, mode === 'note');
      setContent('');
      toast.success(mode === 'reply' ? 'Reply sent' : 'Note added');
    } catch {
      toast.error('Failed to send');
    } finally {
      setIsSending(false);
    }
  };

  // Handle template insert
  const handleTemplateInsert = useCallback((template: Template, variables: Record<string, string>) => {
    // Render template with variables
    let rendered = template.body_template;
    Object.entries(variables).forEach(([key, value]) => {
      rendered = rendered.replace(new RegExp(`{{${key}}}`, 'g'), value || `[${key}]`);
    });

    // Add subject as first line if exists
    if (template.subject_template) {
      let subject = template.subject_template;
      Object.entries(variables).forEach(([key, value]) => {
        subject = subject.replace(new RegExp(`{{${key}}}`, 'g'), value || `[${key}]`);
      });
      rendered = `**${subject}**\n\n${rendered}`;
    }

    setContent(rendered);
    setShowTemplates(false);
  }, []);

  // Strip HTML for plain text check
  const stripHtml = (html: string): string => {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
  };

  // Keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Cmd/Ctrl + Enter to send
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
    // Cmd/Ctrl + Shift + T for templates
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'T') {
      e.preventDefault();
      setShowTemplates((prev) => !prev);
    }
  };

  const plainContent = stripHtml(content);
  const hasContent = plainContent.trim().length > 0;

  return (
    <div
      className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}
      onKeyDown={handleKeyDown}
    >
      {/* Mode Toggle */}
      <div className="flex items-center justify-between px-3 pt-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMode('reply')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              mode === 'reply'
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
            )}
          >
            <span className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
              </svg>
              Reply to Customer
            </span>
          </button>
          <button
            onClick={() => setMode('note')}
            className={cn(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              mode === 'note'
                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/25'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
            )}
          >
            <span className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
              </svg>
              Internal Note
            </span>
          </button>
        </div>

        {/* Signature toggle (reply mode only) */}
        {mode === 'reply' && (
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={appendSignature}
              onChange={(e) => setAppendSignature(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-zinc-600 bg-transparent checked:bg-violet-500 checked:border-violet-500 focus:ring-0 focus:ring-offset-0"
            />
            <span className="text-[10px] text-zinc-500">Signature</span>
          </label>
        )}
      </div>

      {/* Editor */}
      <div className="p-3 relative">
        <RichTextEditor
          value={content}
          onChange={setContent}
          placeholder={mode === 'reply' ? 'Type your reply to the customer...' : 'Add an internal note (visible to team only)...'}
          maxLength={10000}
          minHeight={80}
          maxHeight={300}
        />

        {/* Template Selector */}
        <TemplateSelector
          isOpen={showTemplates}
          onClose={() => setShowTemplates(false)}
          onSelect={(template) => {
            // Just select, let user fill variables
          }}
          onInsert={handleTemplateInsert}
          position="top"
          variables={defaultVariables}
          className="right-0"
        />
      </div>

      {/* Bottom toolbar */}
      <div className="flex items-center justify-between px-3 pb-3">
        <div className="flex items-center gap-1">
          {/* Attachment button */}
          <button
            className="p-2 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all"
            title="Attach file"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="m18.375 12.739-7.693 7.693a4.5 4.5 0 0 1-6.364-6.364l10.94-10.94A3 3 0 1 1 19.5 7.372L8.552 18.32m.009-.01-.01.01m5.699-9.941-7.81 7.81a1.5 1.5 0 0 0 2.112 2.13" />
            </svg>
          </button>

          {/* Template button */}
          <button
            onClick={() => setShowTemplates((prev) => !prev)}
            className={cn(
              'p-2 rounded-lg transition-all',
              showTemplates
                ? 'text-violet-400 bg-violet-500/10'
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05]'
            )}
            title="Use template (Ctrl+Shift+T)"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </button>

          {/* Canned response hint */}
          <button
            className="p-2 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-all"
            title="Insert emoji"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 0 1-6.364 0M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75Zm-.375 0h.008v.015h-.008V9.75Z" />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[10px] text-zinc-600 hidden sm:inline">
            ⌘ + Enter to send • ⌘ + Shift + T for templates
          </span>
          <button
            onClick={handleSend}
            disabled={!hasContent || isSending}
            className={cn(
              'px-4 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed',
              mode === 'reply'
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 hover:bg-emerald-500/25'
                : 'bg-amber-500/15 text-amber-400 border border-amber-500/25 hover:bg-amber-500/25'
            )}
          >
            {isSending ? (
              <span className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Sending...
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                {mode === 'reply' ? (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0 1 21.485 12 59.77 59.77 0 0 1 3.27 20.876L5.999 12Zm0 0h7.5" />
                    </svg>
                    Send Reply
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
                    </svg>
                    Add Note
                  </>
                )}
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
