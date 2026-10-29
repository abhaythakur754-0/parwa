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
          background: '#303036',
          color: '#F4F4F5',
          border: '1px solid rgba(161,161,170,0.25)',
          borderRadius: '12px',
          boxShadow: '0 25px 50px rgba(0,0,0,0.3), 0 0 40px rgba(161,161,170,0.06)',
        },
        success: {
          iconTheme: { primary: '#FF9F5A', secondary: '#303036' },
        },
        error: {
          iconTheme: { primary: '#FB7185', secondary: '#303036' },
        },
      }}
    />
  );
}
