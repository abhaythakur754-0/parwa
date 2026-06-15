'use client';

import React from 'react';
import dynamic from 'next/dynamic';

/**
 * IntegrationsPage — Dashboard sub-page for managing API integrations
 * with connector verification.
 *
 * Uses dynamic import to avoid duplicating the large integrations page code.
 * The actual implementation lives in /app/dashboard/integrations/page.tsx.
 */
const IntegrationsDashboardPage = dynamic(
  () => import('@/app/dashboard/integrations/page').then((mod) => mod.default),
  {
    loading: () => (
      <div className="flex items-center justify-center py-12">
        <svg className="w-8 h-8 animate-spin text-orange-400" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    ),
    ssr: false,
  }
);

export default function IntegrationsPage() {
  return <IntegrationsDashboardPage />;
}
