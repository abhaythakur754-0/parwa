'use client';

import { AuthProvider } from '@/contexts/AuthContext';

/**
 * Auth Layout
 * 
 * Wraps all auth pages (login, signup) with the AuthProvider.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      {children}
    </AuthProvider>
  );
}
