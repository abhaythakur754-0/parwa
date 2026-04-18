'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Lock, ArrowLeft, CheckCircle, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasLowercase = /[a-z]/.test(newPassword);
  const hasDigit = /\d/.test(newPassword);
  const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(newPassword);
  const isLongEnough = newPassword.length >= 8;
  const passwordsMatch = newPassword === confirmPassword && confirmPassword !== '';
  const isPasswordValid = hasUppercase && hasLowercase && hasDigit && hasSpecial && isLongEnough && passwordsMatch;

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link. Please request a new password reset.');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) { setError('Invalid reset link. Please request a new password reset.'); return; }
    if (!isPasswordValid) { setError('Please ensure your password meets all requirements.'); return; }
    setError(null);
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/reset-password`, {
        token: token, new_password: newPassword, confirm_password: confirmPassword,
      });
      if (response.data?.status === 'success') {
        setSuccess(true);
        toast.success('Password reset successfully!');
        setTimeout(() => { router.push('/login'); }, 3000);
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || err.response?.data?.message || 'Failed to reset password. The link may have expired.';
      setError(message);
      toast.error(message);
    } finally { setIsLoading(false); }
  };

  if (success) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}>
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute w-[300px] h-[300px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, transparent 70%)', top: '20%', left: '15%', animation: 'orbFloat 10s ease-in-out infinite' }} />
          <div className="absolute w-[250px] h-[250px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,165,0,0.1) 0%, transparent 70%)', bottom: '20%', right: '15%', animation: 'orbFloat 12s ease-in-out infinite' }} />
        </div>
        <div className="w-full max-w-md relative z-10">
          <div className="rounded-2xl p-6 sm:p-8 text-center space-y-4" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)', border: '1px solid rgba(255,127,17,0.2)', backdropFilter: 'blur(20px)', boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)' }}>
            <div className="w-16 h-16 mx-auto rounded-full bg-orange-500/15 border border-orange-500/25 flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-orange-400" />
            </div>
            <h2 className="text-xl font-semibold text-white">Password Reset Successfully!</h2>
            <p className="text-orange-200/50">Your password has been updated. Redirecting to login...</p>
            <Link href="/login" className="inline-block text-orange-400 hover:text-orange-300 transition-colors">Go to login now</Link>
          </div>
        </div>
        <style jsx global>{`@keyframes orbFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-30px); } }`}</style>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 40%, #3D2A10 70%, #4A3520 100%)' }}>
      {/* Animated background */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute w-[400px] h-[400px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.02) 60%, transparent 80%)', top: '15%', left: '10%', animation: 'orbFloat1 10s ease-in-out infinite' }} />
        <div className="absolute w-[300px] h-[300px] rounded-full" style={{ background: 'radial-gradient(circle, rgba(255,215,0,0.06) 0%, transparent 70%)', bottom: '10%', right: '10%', animation: 'orbFloat2 12s ease-in-out infinite' }} />
        {Array.from({ length: 10 }).map((_, i) => {
          const row = Math.floor(i / 4); const col = i % 4;
          return <div key={i} className="absolute w-1 h-1 rounded-full bg-orange-400" style={{ left: `${(col + 0.5) * 25}%`, top: `${(row + 0.5) * 25}%`, animation: `dotPulse 3s ease-in-out infinite ${(i * 0.4) % 4}s`, opacity: 0 }} />;
        })}
      </div>

      <div className="w-full max-w-md space-y-8 relative z-10">
        <div className="text-center">
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-600/30">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-white">PARWA</span>
          </Link>
          <h1 className="text-3xl font-bold text-white">Reset your password</h1>
          <p className="mt-2 text-sm text-orange-200/50">Enter a new password for your account</p>
        </div>

        <div className="rounded-2xl p-6 sm:p-8 relative overflow-hidden" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)', border: '1px solid rgba(255,127,17,0.2)', backdropFilter: 'blur(20px)', boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 60px rgba(255,127,17,0.06)' }}>
          <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none" style={{ background: 'rgba(255,127,17,0.1)' }} />

          {!token ? (
            <div className="text-center space-y-4">
              <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/20">
                <p className="text-rose-300">Invalid or missing reset token.</p>
              </div>
              <Link href="/forgot-password" className="inline-block text-orange-400 hover:text-orange-300 transition-colors">Request a new reset link</Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* New Password */}
              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-orange-200/70 mb-2">New Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-orange-400/50" />
                  </div>
                  <input id="new-password" name="new-password" type={showPassword ? 'text' : 'password'} required value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full pl-10 pr-10 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-orange-200/30 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all duration-300"
                    placeholder="Enter new password" disabled={isLoading} />
                  <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute inset-y-0 right-0 pr-3 flex items-center text-orange-400/50 hover:text-orange-400 transition-colors" tabIndex={-1}>
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              {/* Password Requirements */}
              {newPassword && (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className={`flex items-center gap-1 ${isLongEnough ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{isLongEnough ? '✓' : '○'}</span> At least 8 characters</div>
                  <div className={`flex items-center gap-1 ${hasUppercase ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{hasUppercase ? '✓' : '○'}</span> Uppercase letter</div>
                  <div className={`flex items-center gap-1 ${hasLowercase ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{hasLowercase ? '✓' : '○'}</span> Lowercase letter</div>
                  <div className={`flex items-center gap-1 ${hasDigit ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{hasDigit ? '✓' : '○'}</span> Number</div>
                  <div className={`flex items-center gap-1 ${hasSpecial ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{hasSpecial ? '✓' : '○'}</span> Special character</div>
                  <div className={`flex items-center gap-1 ${passwordsMatch ? 'text-orange-400' : 'text-orange-200/30'}`}><span>{passwordsMatch ? '✓' : '○'}</span> Passwords match</div>
                </div>
              )}

              {/* Confirm Password */}
              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-orange-200/70 mb-2">Confirm Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-orange-400/50" />
                  </div>
                  <input id="confirm-password" name="confirm-password" type={showPassword ? 'text' : 'password'} required value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-orange-200/30 focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all duration-300"
                    placeholder="Confirm new password" disabled={isLoading} />
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <p className="text-sm text-rose-300">{error}</p>
                </div>
              )}

              {/* Submit */}
              <button type="submit" disabled={isLoading || !isPasswordValid}
                className="w-full py-3 px-4 bg-gradient-to-r from-orange-500 to-orange-400 hover:from-orange-400 hover:to-orange-300 text-[#1A1A1A] font-semibold rounded-xl transition-all duration-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-orange-600/25 hover:shadow-orange-600/40">
                {isLoading ? (<><Loader2 className="w-5 h-5 animate-spin" /> Resetting password...</>) : 'Reset Password'}
              </button>
            </form>
          )}
        </div>

        <div className="text-center">
          <Link href="/login" className="inline-flex items-center gap-2 text-sm text-orange-200/40 hover:text-orange-300 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Back to login
          </Link>
        </div>
      </div>

      <style jsx global>{`
        @keyframes orbFloat1 { 0%, 100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-30px) scale(1.05); } }
        @keyframes orbFloat2 { 0%, 100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-35px) scale(1.06); } }
        @keyframes dotPulse { 0%, 100% { opacity: 0; transform: scale(0.5); } 50% { opacity: 0.6; transform: scale(1.2); } }
      `}</style>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 50%, #4A3520 100%)' }}>
        <Loader2 className="w-8 h-8 animate-spin text-orange-400" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
