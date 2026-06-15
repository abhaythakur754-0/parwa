'use client';

import { NavigationBar, HeroSection, FeatureCarousel, HowItWorks, JarvisDemo, WhyChooseUs, Footer } from '@/components/landing';

/**
 * LandingPage — Full landing page with navigation, hero, features, and footer.
 */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#0A0A0A]">
      <NavigationBar />
      <main>
        <HeroSection />
        <FeatureCarousel />
        <HowItWorks />
        <JarvisDemo />
        <WhyChooseUs />
      </main>
      <Footer />
    </div>
  );
}
