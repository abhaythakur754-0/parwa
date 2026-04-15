'use client';

import { useEffect, useState } from 'react';

/**
 * DogfoodingBanner Component
 * 
 * Professional gold banner - trust indicator at top of page.
 * NO emojis - using SVG icon.
 * 
 * Color: Gold (#FFD700) as per Frontend Docs.
 * 
 * Features:
 * - Shimmer animation
 * - Responsive text
 * - Accessible button
 */

interface DogfoodingBannerProps {
  onOpenDemo?: () => void;
}

export default function DogfoodingBanner({ onOpenDemo }: DogfoodingBannerProps) {
  const [isVisible, setIsVisible] = useState(false);

  // Animate in on mount
  useEffect(() => {
    setIsVisible(true);
  }, []);

  return (
    <div 
      className={`bg-gradient-to-r from-gold-600 via-gold-500 to-gold-600 py-2 sm:py-3 px-4 relative overflow-hidden transition-all duration-500 ${
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-full'
      }`}
      role="banner"
    >
      {/* Subtle shine effect */}
      <div 
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" 
        style={{ backgroundSize: '200% 100%' }}
        aria-hidden="true"
      />
      
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 sm:gap-3 text-center relative">
        <svg 
          className="w-4 h-4 sm:w-5 sm:h-5 text-navy-900 flex-shrink-0" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor" 
          strokeWidth="2"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
        </svg>
        <p className="text-xs sm:text-sm md:text-base font-medium text-navy-900">
          Our support is powered by{' '}
          <button
            onClick={onOpenDemo}
            className="underline hover:no-underline font-bold focus-visible-ring rounded px-1"
            aria-label="Try PARWA AI demo"
          >
            PARWA AI
          </button>
          {' '}- Try it now!
        </p>
        <svg 
          className="w-4 h-4 sm:w-5 sm:h-5 text-navy-900 flex-shrink-0 hidden sm:block" 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor" 
          strokeWidth="2"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
    </div>
  );
}
