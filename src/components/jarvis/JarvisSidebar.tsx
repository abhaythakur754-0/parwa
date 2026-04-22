'use client';

import { JarvisChat } from './JarvisChat';

interface JarvisSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function JarvisSidebar({ isOpen, onClose }: JarvisSidebarProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 lg:bg-black/40"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full sm:w-[400px] bg-[#1A1A1A] border-l border-white/[0.06] z-50 shadow-2xl animate-in slide-in-from-right duration-300">
        <JarvisChat
          isOpen={isOpen}
          onClose={onClose}
          entrySource="dashboard"
        />
      </div>
    </>
  );
}
