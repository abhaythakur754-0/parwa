'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Lock, ArrowLeft, CheckCircle, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Reset Password Page
 *
 * Page for users to reset their password using a token from email.
 * F-014: Token-based password reset (Step 2)
 */
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

  // Password strength indicators
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
    if (!token) {
      setError('Invalid reset link. Please request a new password reset.');
      return;
    }
    if (!isPasswordValid) {
      setError('Please ensure your password meets all requirements.');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/auth/reset-password`, {
        token: token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });

      if (response.data?.status === 'success') {
        setSuccess(true);
        toast.success('Password reset successfully!');
        // Redirect to login after 3 seconds
        setTimeout(() => {
          router.push('/login');
        }, 3000);
      }
    } catch (err: any) {
      const message = err.response?.data?.detail || err.response?.data?.message || 'Failed to reset password. The link may have expired.';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-[#ECFDF5] to-white">
        <div className="w-full max-w-md">
          <div className="bg-white backdrop-blur-sm border border-gray-200 rounded-xl p-6 sm:p-8 text-center space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-emerald-500/20 flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-xl font-semibold text-gray-900">Password Reset Successfully!</h2>
            <p className="text-gray-500">
              Your password has been updated. Redirecting to login...
            </p>
            <Link
              href="/login"
              className="inline-block text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Go to login now
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-emerald-50 to-white">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          {/* Logo */}
          <Link href="/" className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-600 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-600/20">
              <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-gray-900">PARWA</span>
          </Link>

          <h1 className="text-3xl font-bold text-gray-900">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            Enter a new password for your account
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-white backdrop-blur-sm border border-gray-200 rounded-xl p-6 sm:p-8">
          {!token ? (
            <div className="text-center space-y-4">
              <div className="p-4 rounded-lg bg-red-50 border border-red-200">
                <p className="text-red-600">Invalid or missing reset token.</p>
              </div>
              <Link
                href="/forgot-password"
                className="inline-block text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                Request a new reset link
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* New Password Field */}
              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 mb-2">
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="new-password"
                    name="new-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full pl-10 pr-10 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                    placeholder="Enter new password"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-500"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              {/* Password Requirements */}
              {newPassword && (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className={`flex items-center gap-1 ${isLongEnough ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{isLongEnough ? '✓' : '○'}</span> At least 8 characters
                  </div>
                  <div className={`flex items-center gap-1 ${hasUppercase ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{hasUppercase ? '✓' : '○'}</span> Uppercase letter
                  </div>
                  <div className={`flex items-center gap-1 ${hasLowercase ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{hasLowercase ? '✓' : '○'}</span> Lowercase letter
                  </div>
                  <div className={`flex items-center gap-1 ${hasDigit ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{hasDigit ? '✓' : '○'}</span> Number
                  </div>
                  <div className={`flex items-center gap-1 ${hasSpecial ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{hasSpecial ? '✓' : '○'}</span> Special character
                  </div>
                  <div className={`flex items-center gap-1 ${passwordsMatch ? 'text-emerald-400' : 'text-gray-400'}`}>
                    <span>{passwordsMatch ? '✓' : '○'}</span> Passwords match
                  </div>
                </div>
              )}

              {/* Confirm Password Field */}
              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700 mb-2">
                  Confirm Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="confirm-password"
                    name="confirm-password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                    placeholder="Confirm new password"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading || !isPasswordValid}
                className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Resetting password...
                  </>
                ) : (
                  'Reset Password'
                )}
              </button>
            </form>
          )}
        </div>

        {/* Back to Login */}
        <div className="text-center">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-emerald-400 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to login
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-[#ECFDF5]">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
