"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { OnboardingWizard, type OnboardingData } from "@/components/onboarding/OnboardingWizard";

export const metadata = {
  title: "Onboarding - PARWA",
  description: "Set up your PARWA workspace",
};

export default function OnboardingPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    // Check if user is authenticated
    // In production, this would check the auth store or session
    const checkAuth = async () => {
      try {
        // Simulate auth check
        // const response = await fetch('/api/auth/me');
        // if (!response.ok) throw new Error('Not authenticated');

        // For demo, assume authenticated
        setIsAuthenticated(true);
      } catch {
        // Redirect to login if not authenticated
        setIsAuthenticated(false);
        router.push("/auth/login");
      }
    };

    checkAuth();
  }, [router]);

  const handleComplete = async (data: OnboardingData) => {
    try {
      // In production, send onboarding data to backend
      // const response = await fetch('/api/onboarding', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(data),
      // });

      console.log("Onboarding complete:", data);

      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Redirect to dashboard
      router.push("/dashboard");
    } catch (error) {
      console.error("Onboarding failed:", error);
    }
  };

  // Loading state while checking auth
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full border-4 border-primary border-t-transparent animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Not authenticated - will redirect
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 px-4 py-8">
      {/* Background pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#8881_1px,transparent_1px),linear-gradient(to_bottom,#8881_1px,transparent_1px)] bg-[size:24px_24px]" />

      {/* Logo */}
      <div className="relative z-10 text-center mb-8">
        <a href="/" className="inline-flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-5 h-5 text-primary-foreground"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="text-xl font-bold">PARWA</span>
        </a>
      </div>

      {/* Onboarding Wizard */}
      <div className="relative z-10">
        <OnboardingWizard onComplete={handleComplete} />
      </div>
    </div>
  );
}
