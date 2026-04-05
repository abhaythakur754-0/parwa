'use client';

/**
 * DogfoodingBanner Component
 * 
 * Trust indicator at top of page.
 * Shows "Our support is powered by PARWA AI" - a trust signal.
 * 
 * Color: Gold (#FFD700) banner bar as per Frontend Docs.
 * 
 * Based on Frontend Docs Section A1.3:
 * "Gold (#FFD700) banner bar, 'Our support is powered by PARWA AI' text"
 */

interface DogfoodingBannerProps {
  onOpenDemo?: () => void;
}

export default function DogfoodingBanner({ onOpenDemo }: DogfoodingBannerProps) {
  return (
    <div className="bg-gold-500 py-2.5 px-4">
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 text-center">
        <span className="text-lg">🤖</span>
        <p className="text-sm md:text-base font-medium text-secondary-900">
          Our support is powered by{' '}
          <button
            onClick={onOpenDemo}
            className="underline hover:no-underline font-semibold"
          >
            PARWA AI
          </button>
          {' '}- Try it now!
        </p>
        <span className="text-lg hidden sm:inline">✨</span>
      </div>
    </div>
  );
}
