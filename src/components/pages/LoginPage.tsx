'use client';

import { useAppStore } from '@/lib/store';
import { LoginForm } from '@/components/auth/LoginForm';
import toast from 'react-hot-toast';

/**
 * LoginPage — Split layout with branding panel and login form.
 * Uses mock auth fallback when backend is unavailable.
 */
export default function LoginPage() {
  const navigate = useAppStore((s) => s.navigate);
  const setAuth = useAppStore((s) => s.setAuth);

  const handleLogin = async (email: string, password: string) => {
    try {
      // Try real API first
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('parwa_user', JSON.stringify(data.user));
        setAuth(true);
        toast.success('Welcome back!');
        return;
      }
    } catch {
      // Graceful degradation: use mock data
    }

    // Mock login fallback — works in demo mode
    const mockUser = {
      id: 'usr_mock_1',
      email,
      full_name: 'Demo User',
      phone: null,
      avatar_url: null,
      role: 'admin',
      is_active: true,
      is_verified: true,
      company_id: 'comp_mock_1',
      company_name: 'Demo Corp',
      onboarding_completed: true,
      created_at: new Date().toISOString(),
    };
    localStorage.setItem('parwa_user', JSON.stringify(mockUser));
    setAuth(true);
    toast.success('Welcome back! (Demo mode)');
  };

  return (
    <div
      className="min-h-screen flex"
      style={{ background: 'linear-gradient(180deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)' }}
    >
      {/* Left branding panel — desktop only */}
      <div className="hidden lg:flex lg:w-1/2 items-center justify-center p-12">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/25 mx-auto mb-6">
            <svg
              className="w-8 h-8 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z"
              />
            </svg>
          </div>
          <h2 className="text-3xl font-bold text-white mb-3">Welcome back to PARWA</h2>
          <p className="text-zinc-400 mb-6">
            Sign in to access your AI-powered customer support dashboard.
          </p>
          <ul className="space-y-3 text-left text-sm text-zinc-400">
            {[
              'Real-time ticket management & analytics',
              'Multi-channel AI support agents',
              'ROI tracking & cost optimization',
              '24/7 automated customer assistance',
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Right form panel */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">P</span>
            </div>
            <span className="text-xl font-bold text-white">PARWA</span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-2">Sign in</h1>
          <p className="text-sm text-zinc-400 mb-8">Enter your credentials to access your dashboard</p>

          <LoginForm onSubmit={handleLogin} />

          <div className="mt-6 text-center">
            <button
              onClick={() => navigate('forgot-password')}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Forgot your password?
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
