'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, Loader2 } from 'lucide-react';

import { DetailsForm } from '@/components/onboarding/DetailsForm';
import { userDetailsApi, onboardingApi } from '@/lib/api';
import { UserDetails, OnboardingState } from '@/types/onboarding';

/**
 * WelcomeDetailsPage
 * 
 * Post-payment details collection page.
 * Shown after successful Paddle checkout.
 */
export default function WelcomeDetailsPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [initialData, setInitialData] = useState<UserDetails | null>(null);
  const [onboardingState, setOnboardingState] = useState<OnboardingState | null>(null);
  
  // Fetch initial data
  useEffect(() => {
    async function fetchInitialData() {
      try {
        // Fetch existing user details if any
        const [details, state] = await Promise.all([
          userDetailsApi.get().catch(() => null),
          onboardingApi.getState().catch(() => null),
        ]);
        
        setInitialData(details);
        setOnboardingState(state);
        
        // If details already completed, redirect to onboarding wizard
        if (state?.details_completed) {
          router.push('/onboarding');
        }
      } catch (error) {
        console.error('Failed to fetch initial data:', error);
      } finally {
        setIsLoading(false);
      }
    }
    
    fetchInitialData();
  }, [router]);
  
  /**
   * Handle successful details submission.
   */
  const handleSubmit = (data: UserDetails) => {
    setInitialData(data);
  };
  
  /**
   * Handle next button click.
   */
  const handleNext = () => {
    router.push('/onboarding');
  };
  
  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#ECFDF5] to-white">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mx-auto mb-4" />
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#ECFDF5] to-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-xl mx-auto">
        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-4">
            <Step number={1} label="Details" isActive isCompleted={false} />
            <div className="w-12 h-0.5 bg-gray-200" />
            <Step number={2} label="Setup" isActive={false} isCompleted={false} />
            <div className="w-12 h-0.5 bg-gray-200" />
            <Step number={3} label="Launch" isActive={false} isCompleted={false} />
          </div>
        </div>
        
        {/* Main Card */}
        <div className="card card-padding">
          {/* Logo/Brand */}
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-gradient">PARWA</h1>
            <p className="text-gray-500 text-sm mt-1">AI-Powered Customer Support</p>
          </div>
          
          {/* Details Form */}
          <DetailsForm
            initialData={initialData}
            onSubmit={handleSubmit}
            onNext={handleNext}
          />
        </div>
        
        {/* Footer */}
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>
            Need help?{' '}
            <a href="mailto:support@parwa.io" className="text-emerald-600 hover:text-emerald-700">
              Contact Support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * Step Component
 */
function Step({ 
  number, 
  label, 
  isActive, 
  isCompleted 
}: { 
  number: number; 
  label: string; 
  isActive: boolean; 
  isCompleted: boolean;
}) {
  return (
    <div className="flex flex-col items-center">
      <div
        className={`
          w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium
          ${isCompleted 
            ? 'bg-emerald-500 text-white' 
            : isActive 
              ? 'bg-emerald-600 text-white' 
              : 'bg-gray-200 text-gray-400'
          }
        `}
      >
        {isCompleted ? (
          <CheckCircle className="w-5 h-5" />
        ) : (
          number
        )}
      </div>
      <span className={`
        mt-2 text-xs font-medium
        ${isActive ? 'text-emerald-600' : 'text-gray-400'}
      `}>
        {label}
      </span>
    </div>
  );
}
