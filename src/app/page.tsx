'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import {
  NavigationBar,
  HeroSection,
  WhyChooseUs,
  HowItWorks,
  JarvisDemo,
  Footer,
} from '@/components/landing';

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isInitialized } = useAuth();

  // Netflix rule: no subscription = no dashboard.
  // Only redirect to dashboard if user has an ACTIVE subscription.
  // Users without a subscription stay on the landing page.
  useEffect(() => {
    if (!isInitialized || !isAuthenticated) return;

    let cancelled = false;

    const checkSubscription = async () => {
      try {
        // Check if user has any active subscriptions via Razorpay billing
        const res = await fetch('/api/billing/razorpay/subscriptions', { credentials: 'include' });
        if (!res.ok) return; // stay on landing page if API fails
        const subs = await res.json();
        if (cancelled) return;

        // Only redirect if user has at least one ACTIVE subscription
        const hasActive = Array.isArray(subs) && subs.some(
          (s: any) => s.status === 'active' || s.status === 'created' || s.status === 'authenticated'
        );

        if (hasActive) {
          router.replace('/dashboard/tickets');
        }
        // No subscription → stay on landing page (Netflix rule)
      } catch {
        // Backend unreachable → stay on landing page
      }
    };

    checkSubscription();
    return () => { cancelled = true; };
  }, [isAuthenticated, isInitialized, router]);

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      <NavigationBar />
      <HeroSection />
      <HowItWorks />
      <JarvisDemo />
      <WhyChooseUs />
      <Footer />
    </main>
  );
}
