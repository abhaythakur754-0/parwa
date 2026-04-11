'use client';

import { useRouter } from 'next/navigation';
import {
  NavigationBar,
  FeatureCarousel,
  HeroSection,
  HowItWorks,
  WhyChooseUs,
  JarvisDemo,
  Footer,
} from '@/components/landing';

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
  const router = useRouter();

  const handleOpenJarvis = () => {
    localStorage.setItem('parwa_jarvis_context', JSON.stringify({ source: 'nav_bar' }));
    router.push('/onboarding');
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Navigation */}
      <NavigationBar onOpenJarvis={handleOpenJarvis} />

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
