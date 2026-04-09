'use client';

import React from 'react';

interface SocialLoginProps {
  onGoogleLogin: (idToken: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  showDividerAfter?: boolean;
}

export function SocialLogin({ onGoogleLogin, isLoading = false, error, showDividerAfter = true }: SocialLoginProps) {
  const handleGoogleSignIn = async () => {
    try {
      if (typeof window !== 'undefined' && !window.google) {
        const script = document.createElement('script');
        script.src = 'https://accounts.google.com/gsi/client';
        script.async = true;
        script.defer = true;
        document.head.appendChild(script);
        await new Promise<void>((resolve) => { script.onload = () => resolve(); });
      }
      window.google?.accounts?.id?.initialize({
        client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
        callback: async (response: { credential: string }) => {
          if (response.credential) await onGoogleLogin(response.credential);
        },
      });
      window.google?.accounts?.id?.prompt();
    } catch (err) {
      console.error('Google sign-in error:', err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3">
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition-all duration-300 font-medium text-sm shadow-sm"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          <span>{isLoading ? 'Signing in...' : 'Continue with Google'}</span>
        </button>
      </div>

      {error && <p className="text-sm text-red-500 text-center">{error}</p>}

      {showDividerAfter && (
        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-white text-gray-500">or continue with email</span>
          </div>
        </div>
      )}
    </div>
  );
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (response: { credential: string }) => void }) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export default SocialLogin;
