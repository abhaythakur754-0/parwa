'use client';

/**
 * DogfoodingBanner Component
 * 
 * Professional gold banner - trust indicator at top of page.
 * NO emojis - using SVG icon.
 * 
 * Color: Gold (#FFD700) as per Frontend Docs.
 */

interface DogfoodingBannerProps {
  onOpenDemo?: () => void;
}

export default function DogfoodingBanner({ onOpenDemo }: DogfoodingBannerProps) {
  return (
    <div className="bg-gradient-to-r from-gold-600 via-gold-500 to-gold-600 py-3 px-4 relative overflow-hidden">
      {/* Subtle shine effect */}
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" style={{ backgroundSize: '200% 100%' }} />
      
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-3 text-center relative">
        <svg className="w-5 h-5 text-navy-900 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <p className="text-sm md:text-base font-medium text-navy-900">
          Our support is powered by{' '}
          <button
            onClick={onOpenDemo}
            className="underline hover:no-underline font-bold"
          >
            PARWA AI
          </button>
          {' '}- Try it now!
        </p>
        <svg className="w-5 h-5 text-navy-900 flex-shrink-0 hidden sm:block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
    </div>
  );
}
