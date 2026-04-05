'use client';

import { useState } from 'react';
import {
  NavigationBar,
  DogfoodingBanner,
  FeatureCarousel,
  HeroSection,
  WhyChooseUs,
  HowItWorks,
  Footer,
} from '@/components/landing';

/**
 * Landing Page (Home)
 * 
 * Page structure based on psychological impact:
 * 0. DogfoodingBanner - Trust indicator (Gold banner)
 * 1. NavigationBar - Top navigation
 * 2. FeatureCarousel - Netflix-style 5 slides (FIRST impression)
 * 3. HeroSection - Cost comparison + Jarvis preview
 * 4. WhyChooseUs - WHAT Jarvis does
 * 5. HowItWorks - HOW Jarvis works
 * 6. Footer - Links + Copyright 2026
 * 
 * Color scheme based on Frontend Docs:
 * - E-commerce: Teal/Gold
 * - SaaS: Navy/Silver
 * - Logistics: Charcoal/Orange
 * - Dogfooding Banner: Gold (#FFD700)
 * 
 * Based on ONBOARDING_SPEC.md v2.0 Section 2.3
 */

export default function HomePage() {
  const [isJarvisOpen, setIsJarvisOpen] = useState(false);

  const handleOpenJarvis = () => {
    // TODO: Open Jarvis chat modal
    setIsJarvisOpen(true);
    console.log('Opening Jarvis chat...');
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Dogfooding Banner - Trust indicator */}
      <DogfoodingBanner onOpenDemo={handleOpenJarvis} />

      {/* Navigation */}
      <NavigationBar onOpenJarvis={handleOpenJarvis} />

      {/* Main Content */}
      <main className="flex-grow">
        {/* Section 1: Feature Carousel (Netflix-style) - FIRST thing users see */}
        <FeatureCarousel />

        {/* Section 2: Hero with Cost Comparison */}
        <HeroSection onOpenJarvis={handleOpenJarvis} />

        {/* Section 3: Why Choose PARWA (WHAT Jarvis does) */}
        <WhyChooseUs />

        {/* Section 4: How It Works (HOW Jarvis works) */}
        <HowItWorks />
      </main>

      {/* Footer */}
      <Footer />

      {/* TODO: Jarvis Chat Modal */}
      {/* {isJarvisOpen && <JarvisChatModal onClose={() => setIsJarvisOpen(false)} />} */}
    </div>
  );
}
