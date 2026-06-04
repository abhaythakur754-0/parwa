import Link from 'next/link';
import { Home, Search, ArrowLeft } from 'lucide-react';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center">
        {/* 404 illustration */}
        <div className="mb-8">
          <h1 className="text-8xl font-black bg-gradient-to-r from-orange-500 to-amber-400 bg-clip-text text-transparent">
            404
          </h1>
        </div>

        <h2 className="text-2xl font-bold text-white mb-3">
          Page not found
        </h2>

        <p className="text-sm text-zinc-400 mb-8 max-w-sm mx-auto">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
          Check the URL or head back to the dashboard.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
          >
            <Home className="w-4 h-4" />
            Go to Dashboard
          </Link>

          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
