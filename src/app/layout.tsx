import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from '@/contexts/AuthContext';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'PARWA - AI Customer Support',
  description: 'AI-powered customer support platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#064E3B',
              color: '#d1fae5',
              border: '1px solid rgba(16,185,129,0.25)',
              borderRadius: '12px',
              boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 40px rgba(16,185,129,0.06)',
              backdropFilter: 'blur(20px)',
            },
            success: {
              iconTheme: { primary: '#34D399', secondary: '#064E3B' },
            },
            error: {
              iconTheme: { primary: '#FB7185', secondary: '#064E3B' },
            },
          }}
        />
      </body>
    </html>
  );
}
