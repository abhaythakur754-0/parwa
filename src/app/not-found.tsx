'use client';

import Link from 'next/link';
import { AlertTriangle, ArrowLeft, Home } from 'lucide-react';

export default function NotFound() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}
    >
      <div className="text-center max-w-md">
        <div className="w-20 h-20 rounded-2xl bg-orange-500/10 border border-orange-500/15 flex items-center justify-center mx-auto mb-6">
          <AlertTriangle className="w-10 h-10 text-orange-400/60" />
        </div>
        <h1 className="text-6xl font-bold text-white mb-2">404</h1>
        <h2 className="text-xl font-semibold text-white/70 mb-3">Page Not Found</h2>
        <p className="text-sm text-white/40 mb-8 leading-relaxed">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] shadow-lg shadow-orange-600/20 hover:shadow-orange-600/40 hover:-translate-y-0.5 transition-all duration-300"
          >
            <Home className="w-4 h-4" />
            Go Home
          </Link>
          <Link
            href="/jarvis"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-orange-300 bg-orange-500/10 border border-orange-500/20 hover:bg-orange-500/15 transition-all duration-300"
          >
            Ask Jarvis
          </Link>
        </div>
      </div>
    </div>
  );
}
