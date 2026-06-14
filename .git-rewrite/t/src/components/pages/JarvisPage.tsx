'use client';

import { useAppStore } from '@/lib/store';
import { JarvisChat } from '@/components/jarvis';
import { ArrowLeft } from 'lucide-react';

/**
 * JarvisPage — Full-screen Jarvis AI chat interface.
 */
export default function JarvisPage() {
  const navigate = useAppStore((s) => s.navigate);

  return (
    <div className="relative min-h-screen bg-[#0A0A0A]">
      {/* Back button overlay */}
      <button
        onClick={() => navigate('landing')}
        className="absolute top-4 left-4 z-50 flex items-center gap-2 px-3 py-2 rounded-lg bg-black/40 backdrop-blur-xl text-zinc-300 hover:text-white hover:bg-black/60 border border-white/[0.06] transition-all duration-300"
      >
        <ArrowLeft className="w-4 h-4" />
        <span className="text-sm font-medium hidden sm:inline">Back</span>
      </button>

      {/* Full-screen chat */}
      <JarvisChat />
    </div>
  );
}
