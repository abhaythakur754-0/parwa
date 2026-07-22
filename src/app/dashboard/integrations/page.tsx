'use client';

/**
 * /dashboard/integrations — Manage all integrations
 *
 * Shows:
 * 1. StoredAnalysisCard - Recommendations from onboarding (persisted in DB)
 * 2. CRMAnalyzerCard - Run new analysis anytime
 * 3. IntegrationStep - Full integration catalog
 *
 * Business Value:
 * - Persists onboarding insights into dashboard
 * - Allows re-analysis as business grows
 * - Tracks which recommendations were actioned
 */

import React from 'react';
import { IntegrationStep } from '@/components/onboarding/IntegrationStep';
import { CRMAnalyzerCard } from '@/components/integrations/CRMAnalyzerCard';
import { StoredAnalysisCard } from '@/components/integrations/StoredAnalysisCard';

export default function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Integrations</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Connect your tools. All integrations are verified before use.
        </p>
      </div>

      {/* Stored Recommendations from Onboarding */}
      <StoredAnalysisCard 
        onConnect={(integrationKey) => {
          console.log('User wants to connect recommended:', integrationKey);
          // Could scroll to integration or open connect dialog
        }}
      />

      {/* Run New Analysis Anytime */}
      <CRMAnalyzerCard 
        onConnect={(integrationKey) => {
          console.log('User wants to connect:', integrationKey);
        }}
      />

      {/* Full Integration Catalog */}
      <IntegrationStep onNext={() => {}} />
    </div>
  );
}
