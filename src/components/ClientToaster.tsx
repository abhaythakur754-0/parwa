'use client';

import dynamic from 'next/dynamic';

const Toaster = dynamic(
  () => import('react-hot-toast').then((mod) => mod.Toaster),
  { ssr: false }
);

export function ClientToaster() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: '#2A1A0A',
          color: '#FFF4E6',
          border: '1px solid rgba(255,127,17,0.25)',
          borderRadius: '12px',
          boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 40px rgba(255,127,17,0.06)',
        },
        success: {
          iconTheme: { primary: '#FF9F5A', secondary: '#2A1A0A' },
        },
        error: {
          iconTheme: { primary: '#FB7185', secondary: '#2A1A0A' },
        },
      }}
    />
  );
}
