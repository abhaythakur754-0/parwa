'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type { InternalNote } from '@/types/ticket';
import toast from 'react-hot-toast';

interface InternalNotesProps {
  notes: InternalNote[];
  onAddNote: (content: string, isPinned: boolean) => void;
  className?: string;
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function InternalNotes({ notes, onAddNote, className }: InternalNotesProps) {
  const [newNote, setNewNote] = useState('');
  const [isPinned, setIsPinned] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!newNote.trim()) return;
    setIsSubmitting(true);
    try {
      await onAddNote(newNote.trim(), isPinned);
      setNewNote('');
      setIsPinned(false);
      toast.success('Note added');
    } catch {
      toast.error('Failed to add note');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmit();
    }
  };

  return (
    <div className={cn('rounded-xl bg-[#1A1A1A] border border-white/[0.06] overflow-hidden', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
        <h3 className="text-xs font-semibold text-zinc-300">Internal Notes</h3>
        <span className="text-[10px] text-zinc-600">{notes.length} notes</span>
      </div>

      {/* Notes List */}
      <div className="max-h-64 overflow-y-auto">
        {notes.length === 0 ? (
          <div className="px-4 py-8 text-center text-xs text-zinc-600">
            No internal notes yet
          </div>
        ) : (
          <div className="divide-y divide-white/[0.04]">
            {notes.map((note) => (
              <div key={note.id} className="px-4 py-3 hover:bg-white/[0.02] transition-colors">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-300">{note.author_name}</span>
                    {note.is_pinned && (
                      <svg className="w-3 h-3 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.5 3.5a.5.5 0 0 0-.5.5V15a.5.5 0 0 0 .75.433l4.5-2.5a.5.5 0 0 1 .5 0l4.5 2.5a.5.5 0 0 0 .75-.433V4a.5.5 0 0 0-.5-.5h-10Z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                  <span className="text-[10px] text-zinc-600">{timeAgo(note.created_at)}</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">{note.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Note */}
      <div className="border-t border-white/[0.06] p-3 space-y-2">
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add an internal note..."
          rows={2}
          className="w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-orange-500/40 focus:ring-1 focus:ring-orange-500/20 resize-none transition-all"
        />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={isPinned}
              onChange={(e) => setIsPinned(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-white/[0.15] bg-white/[0.04] text-orange-500 accent-orange-500"
            />
            <span className="text-[10px] text-zinc-500">Pin note</span>
          </label>
          <button
            onClick={handleSubmit}
            disabled={!newNote.trim() || isSubmitting}
            className="px-3 py-1 rounded-lg bg-orange-500/15 text-orange-400 text-[11px] font-medium border border-orange-500/25 hover:bg-orange-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {isSubmitting ? 'Adding...' : 'Add Note'}
          </button>
        </div>
      </div>
    </div>
  );
}
