'use client';

/**
 * /dashboard/integrations — Manage all integrations
 *
 * Shows:
 * 1. SuperglueIntegrationsSection - Connect apps via Superglue (Shopify, Gmail, Slack, etc.)
 * 2. StoredAnalysisCard - Recommendations from onboarding (persisted in DB)
 * 3. CRMAnalyzerCard - Run new analysis anytime
 * 4. IntegrationStep - Full API-key-based integration catalog
 */

import React from 'react';
import { IntegrationStep } from '@/components/onboarding/IntegrationStep';
import { CRMAnalyzerCard } from '@/components/integrations/CRMAnalyzerCard';
import { StoredAnalysisCard } from '@/components/integrations/StoredAnalysisCard';
import { SuperglueIntegrationsSection } from '@/components/integrations/SuperglueIntegrationsSection';
import { useAuth } from '@/hooks/useAuth';

export default function IntegrationsPage() {
  const { user } = useAuth();
  const userId = user?.id;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Integrations</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Connect your tools. All integrations are verified before use.
        </p>
      </div>

      {/* Superglue-powered Integrations (replaces Nango) */}
      <div className="rounded-xl border border-violet-500/10 bg-white/[0.01] p-6">
        <h2 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
          <span className="text-violet-400">⚡</span>
          Connect Your Apps
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
            Powered by Superglue
          </span>
        </h2>
        <SuperglueIntegrationsSection />
      </div>

      {/* Stored Recommendations from Onboarding */}
      <StoredAnalysisCard 
        onConnect={(integrationKey) => {
          console.log('User wants to connect recommended:', integrationKey);
        }}
      />

      {/* Run New Analysis Anytime */}
      <CRMAnalyzerCard 
        onConnect={(integrationKey) => {
          console.log('User wants to connect:', integrationKey);
        }}
      />

      {/* Full Integration Catalog (API Key based) */}
      <div>
        <h2 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
          <span className="text-orange-400">🔑</span>
          API Key Integrations
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-300 border border-orange-500/20">
            Manual setup
          </span>
        </h2>
        <IntegrationStep onNext={() => {}} />
      </div>
    </div>
  );
}
