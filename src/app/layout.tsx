import type { Metadata } from 'next';
import { Anton, Archivo } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { ClientToaster } from '@/components/ClientToaster';
import InteractiveBackground from '@/components/InteractiveBackground';

// Archivo — site-wide default typeface (modern grotesque, variable weight).
const archivo = Archivo({
  subsets: ['latin'],
  variable: '--font-archivo-src',
  display: 'swap',
});

// Anton — brand wordmarks + dashboard sidebar only (exposed as `font-anton`
// via globals.css @theme inline mapping).
const anton = Anton({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-anton-src',
  display: 'swap',
});

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'SHOBH - AI Customer Support',
  description: 'AI-powered customer support platform',
  icons: {
    icon: '/favicon.png',
    apple: '/favicon.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${anton.variable} ${archivo.variable}`}>
      {/* Archivo is the site-wide default font via html font-family (globals.css);
          Anton is opt-in via `font-anton` (brand wordmarks + sidebar). */}
      <body>
        <InteractiveBackground />
        <AuthProvider>
          {children}
        </AuthProvider>
        <ClientToaster />
      </body>
    </html>
  );
}
