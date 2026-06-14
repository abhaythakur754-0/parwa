'use client';

import { useAppStore } from '@/lib/store';
import { SignupForm } from '@/components/auth/SignupForm';
import toast from 'react-hot-toast';

/**
 * SignupPage — Registration page with branding and signup form.
 * Uses mock auth fallback when backend is unavailable.
 */
export default function SignupPage() {
  const navigate = useAppStore((s) => s.navigate);
  const setAuth = useAppStore((s) => s.setAuth);

  const handleSignup = async (data: {
    email: string;
    password: string;
    full_name: string;
    company_name: string;
    industry: string;
  }) => {
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        const responseData = await res.json();
        localStorage.setItem('parwa_user', JSON.stringify(responseData.user));
        setAuth(true);
        toast.success('Account created successfully!');
        return;
      }
    } catch {
      // Graceful degradation
    }

    // Mock signup fallback — works in demo mode
    const mockUser = {
      id: 'usr_mock_' + Date.now(),
      email: data.email,
      full_name: data.full_name,
      phone: null,
      avatar_url: null,
      role: 'admin',
      is_active: true,
      is_verified: false,
      company_id: 'comp_mock_' + Date.now(),
      company_name: data.company_name,
      onboarding_completed: false,
      created_at: new Date().toISOString(),
    };
    localStorage.setItem('parwa_user', JSON.stringify(mockUser));
    setAuth(true);
    toast.success('Account created! (Demo mode)');
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 sm:p-8"
      style={{ background: 'linear-gradient(180deg, #0D0D0D 0%, #1A1A1A 50%, #0D0D0D 100%)' }}
    >
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold">P</span>
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Create your account</h1>
          <p className="text-sm text-zinc-400">Get started with PARWA AI support in minutes</p>
        </div>
        <SignupForm onSubmit={handleSignup} />
      </div>
    </div>
  );
}
