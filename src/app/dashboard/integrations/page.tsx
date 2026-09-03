'use client';

/**
 * /dashboard/integrations — Manage all integrations
 *
 * Four sections, each with exactly one job (no duplicates):
 * 1. SuperglueIntegrationsSection — guided connect via Superglue
 * 2. StoredAnalysisCard           — recommendations saved during onboarding
 * 3. CRMAnalyzerCard              — re-run analysis anytime
 * 4. IntegrationStep              — full manual catalog (power users)
 *
 * "Connect" on a recommendation scrolls to the catalog and pre-fills
 * the search with that integration.
 */

import React, { useState } from 'react';
import { IntegrationStep } from '@/components/onboarding/IntegrationStep';
import { CRMAnalyzerCard } from '@/components/integrations/CRMAnalyzerCard';
import { StoredAnalysisCard } from '@/components/integrations/StoredAnalysisCard';
import { SuperglueIntegrationsSection } from '@/components/integrations/SuperglueIntegrationsSection';

export default function IntegrationsPage() {
  const [focusKey, setFocusKey] = useState<string>('');

  // Send the user from a recommendation to the manual catalog, pre-filtered
  const handleConnectRecommendation = (integrationKey: string) => {
    setFocusKey(integrationKey);
    document.getElementById('integration-catalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Integrations</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Connect your tools. All integrations are verified before use.
        </p>
      </div>

      {/* Superglue-powered Integrations (guided connect) */}
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
      <StoredAnalysisCard onConnect={handleConnectRecommendation} />

      {/* Run New Analysis Anytime */}
      <CRMAnalyzerCard onConnect={handleConnectRecommendation} />

      {/* Full Integration Catalog (manual, API-key based) */}
      <div id="integration-catalog" className="scroll-mt-20">
        <h2 className="text-sm font-medium text-white mb-4 flex items-center gap-2">
          <span className="text-orange-400">🔑</span>
          All Integrations
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-300 border border-orange-500/20">
            Manual setup
          </span>
        </h2>
        <IntegrationStep focusKey={focusKey} />
      </div>
    </div>
  );
}
