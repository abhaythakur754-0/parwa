'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useAppStore, isDashboardPage } from '@/lib/store';
import toast from 'react-hot-toast';

// ── Page Components ─────────────────────────────────────────────────
import LandingPage from '@/components/pages/LandingPage';
import LoginPage from '@/components/pages/LoginPage';
import SignupPage from '@/components/pages/SignupPage';
import ForgotPasswordPage from '@/components/pages/ForgotPasswordPage';
import ROICalculatorPage from '@/components/pages/ROICalculatorPage';
import ModelsPage from '@/components/pages/ModelsPage';
import DashboardPageRenderer from '@/components/pages/DashboardPages';
import JarvisPage from '@/components/pages/JarvisPage';
import { IndustrySelect, DetailsForm } from '@/components/onboarding';

// ── Page Transition Wrapper ─────────────────────────────────────────

function PageTransition({ children, pageKey }: { children: React.ReactNode; pageKey: string }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pageKey}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

// ── Onboarding Page ─────────────────────────────────────────────────

function OnboardingPage() {
  const navigate = useAppStore((s) => s.navigate);
  const [step, setStep] = useState<'industry' | 'details'>('industry');

  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 bg-[#0A0A0A]">
      <div className="w-full max-w-lg">
        {step === 'industry' && <IndustrySelect onComplete={() => setStep('details')} />}
        {step === 'details' && (
          <DetailsForm
            onComplete={() => {
              toast.success('Setup complete!');
              navigate('dashboard');
            }}
          />
        )}
        <button
          onClick={() => navigate('dashboard')}
          className="mt-6 w-full py-2.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          Skip for now →
        </button>
      </div>
    </div>
  );
}

// ── Main SPA Router ─────────────────────────────────────────────────

export default function Home() {
  const currentPage = useAppStore((s) => s.currentPage);

  // Sync auth state from localStorage on initial mount only
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem('parwa_user');
      if (storedUser) {
        const user = JSON.parse(storedUser);
        if (user && user.email) {
          const current = useAppStore.getState();
          useAppStore.setState({
            isAuthenticated: true,
            user,
            // If user is on landing/login/signup, redirect to dashboard
            currentPage: (!current.isAuthenticated && ['landing', 'login', 'signup'].includes(current.currentPage))
              ? 'dashboard'
              : current.currentPage,
          });
        }
      }
    } catch {
      // ignore
    }
    // Expose store globally for testing
    (window as unknown as Record<string, unknown>).__PARWA_STORE__ = useAppStore;
  }, []);

  const renderPage = () => {
    if (currentPage === 'landing') {
      return <LandingPage />;
    }

    if (currentPage === 'login') {
      return <LoginPage />;
    }

    if (currentPage === 'signup') {
      return <SignupPage />;
    }

    if (currentPage === 'forgot-password') {
      return <ForgotPasswordPage />;
    }

    if (currentPage === 'onboarding') {
      return <OnboardingPage />;
    }

    if (currentPage === 'roi-calculator') {
      return <ROICalculatorPage />;
    }

    if (currentPage === 'models') {
      return <ModelsPage />;
    }

    if (currentPage === 'jarvis') {
      return <JarvisPage />;
    }

    if (isDashboardPage(currentPage)) {
      return <DashboardPageRenderer />;
    }

    // Fallback to landing
    return <LandingPage />;
  };

  return <PageTransition pageKey={currentPage}>{renderPage()}</PageTransition>;
}
