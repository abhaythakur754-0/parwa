import type { Metadata } from 'next';
import './globals.css';
import Providers from '@/components/Providers';

export const metadata: Metadata = {
  title: 'JARVIS — AI Operating System',
  description: 'PARWA Jarvis AI Operating System Dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-jarvis-bg text-jarvis-text font-mono antialiased min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}