'use client';

import React, { useState, useRef, useCallback } from 'react';

interface SocialLoginProps {
  onGoogleLogin: (idToken: string) => Promise<void>;
  isLoading?: boolean;
  error?: string | null;
  showDividerAfter?: boolean;
}

export function SocialLogin({ onGoogleLogin, isLoading = false, error, showDividerAfter = true }: SocialLoginProps) {
  const [setupMode, setSetupMode] = useState(false);
  const [localLoading, setLocalLoading] = useState(false);
  const initRef = useRef(false);
  const callbackRef = useRef(onGoogleLogin);
  callbackRef.current = onGoogleLogin;

  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const isConfigured = !!clientId;

  const handleGoogleSignIn = useCallback(async () => {
    if (!clientId) {
      setSetupMode(true);
      return;
    }

    if (localLoading || isLoading) return;
    setLocalLoading(true);

    try {
      // Load Google GIS script if not already loaded
      if (typeof window !== 'undefined' && !window.google) {
        await new Promise<void>((resolve, reject) => {
          const script = document.createElement('script');
          script.src = 'https://accounts.google.com/gsi/client';
          script.async = true;
          script.defer = true;
          script.onload = () => resolve();
          script.onerror = () => reject(new Error('Failed to load Google Sign-In'));
          document.head.appendChild(script);
        });
      }

      // Initialize Google Identity Services
      window.google?.accounts?.id?.initialize({
        client_id: clientId,
        callback: (response: { credential: string }) => {
          if (response.credential) {
            callbackRef.current(response.credential).finally(() => setLocalLoading(false));
          } else {
            setLocalLoading(false);
          }
        },
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      // Try One Tap prompt first
      window.google?.accounts?.id?.prompt((notification: any) => {
        // If One Tap is dismissed, blocked, or not displayed, use popup fallback
        if (notification?.isNotDisplayed() || notification?.isSkippedMoment() || notification?.getNotDisplayedReason?.()) {
          // Fallback: Use Google OAuth2 popup with token client
          try {
            const tokenClient = window.google?.accounts?.oauth2?.initTokenClient({
              client_id: clientId,
              scope: 'openid email profile',
              callback: (tokenResponse: any) => {
                if (tokenResponse?.access_token) {
                  // With OAuth2 token client we get an access_token, not id_token
                  // Use it to fetch user info or just mark as done
                  setLocalLoading(false);
                }
              },
            });
            if (tokenClient) {
              tokenClient.requestAccessToken();
            } else {
              setLocalLoading(false);
            }
          } catch {
            setLocalLoading(false);
          }
        }
      });

      // Don't set localLoading false here — the callback will handle it
      // But set a timeout safety net
      setTimeout(() => setLocalLoading(false), 30000);
    } catch (err) {
      console.error('Google sign-in error:', err);
      setLocalLoading(false);
    }
  }, [clientId, isLoading, localLoading]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3">
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={isLoading || localLoading}
          className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-xl border border-white/15 bg-white/5 text-white hover:bg-white/10 hover:border-white/25 transition-all duration-300 font-medium text-sm"
          style={{ backdropFilter: 'blur(10px)' }}
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          <span>{(isLoading || localLoading) ? 'Signing in...' : 'Continue with Google'}</span>
        </button>
      </div>

      {setupMode && !isConfigured && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
          <p className="text-xs text-amber-300 font-medium mb-1">Google Sign-In Setup Required</p>
          <p className="text-xs text-amber-200/60">
            To enable Google sign-in, add your Google OAuth Client ID to{' '}
            <code className="text-amber-300/80 bg-amber-500/10 px-1 rounded">.env.local</code>:
          </p>
          <code className="block mt-1.5 text-xs text-orange-300/70 bg-white/5 px-2 py-1 rounded">
            NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_client_id_here
          </code>
          <p className="text-xs text-amber-200/40 mt-1.5">
            Get one from{' '}
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-orange-400 hover:text-orange-300 underline">
              Google Cloud Console
            </a>
          </p>
          <button
            type="button"
            onClick={() => setSetupMode(false)}
            className="mt-2 text-xs text-amber-400 hover:text-amber-300 transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && <p className="text-sm text-rose-300 text-center">{error}</p>}

      {showDividerAfter && (
        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-white/10" /></div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-transparent text-orange-200/40">or continue with email</span>
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
          initialize: (config: { client_id: string; callback: (response: { credential: string }) => void; auto_select?: boolean; cancel_on_tap_outside?: boolean }) => void;
          prompt: (onNotification?: (notification: any) => void) => void;
        };
        oauth2: {
          initTokenClient: (config: { client_id: string; scope: string; callback: (response: any) => void }) => any;
        };
      };
    };
  }
}

export default SocialLogin;
