'use client';

import {
  NavigationBar,
  FeatureCarousel,
  HeroSection,
  HowItWorks,
  WhyChooseUs,
  JarvisDemo,
  Footer,
} from '@/components/landing';
import { useEffect } from 'react';

/**
 * Landing Page (Home)
 * 
 * Premium psychologically-designed experience.
 * Layout order:
 * 1. NavigationBar - Premium nav with scroll-aware bg
 * 2. FeatureCarousel - Netflix-style full-width carousel (5 slides)
 * 3. HeroSection - Human Support vs PARWA AI comparison
 * 4. HowItWorks - "How PARWA Works" 5-step timeline
 * 5. JarvisDemo - Auto-playing chat animation (moved here)
 * 6. WhyChooseUs - "Why Businesses Choose PARWA" 6 cards
 * 7. Footer - Links + Copyright 2026
 */

export default function HomePage() {
  // Track page visit for context-aware Jarvis routing
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const existing = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]') as string[];
        if (!existing.includes('landing_page')) {
          existing.push('landing_page');
          localStorage.setItem('parwa_pages_visited', JSON.stringify(existing));
        }
      } catch {
        // ignore
      }
    }
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <NavigationBar />

      {/* Main Content */}
      <main className="flex-grow">
        {/* Feature Carousel - Netflix-style full-width */}
        <FeatureCarousel />

        {/* Hero - Human Support vs PARWA AI */}
        <HeroSection />

        {/* How It Works */}
        <HowItWorks />

        {/* Jarvis Demo - Auto-playing chat (moved after HowItWorks) */}
        <JarvisDemo />

        {/* Why Choose Us */}
        <WhyChooseUs />
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}
