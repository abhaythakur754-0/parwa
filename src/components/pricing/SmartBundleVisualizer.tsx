'use client';

import React, { useState, useMemo } from 'react';
import { SlidersHorizontal, TrendingUp, AlertTriangle, CheckCircle2, Sparkles, ArrowRight } from 'lucide-react';
import { IndustrySelector, type Industry } from './IndustrySelector';

type RecommendationTier = 'starter' | 'growth' | 'high' | 'starter-stacked';

interface BundleRecommendation {
  tier: RecommendationTier;
  quantity: number;
  monthlyCost: number;
  annualCost: number;
  message: string;
  subMessage: string;
  color: string;
  isWarning: boolean;
}

const TIER_CONFIG = {
  starter: { monthlyPrice: 999, annualPrice: 799, maxTickets: 1000, name: 'PARWA Starter' },
  growth: { monthlyPrice: 2499, annualPrice: 1999, maxTickets: 5000, name: 'PARWA Growth' },
  high: { monthlyPrice: 3999, annualPrice: 3199, maxTickets: 15000, name: 'PARWA High' },
};

function getRecommendation(ticketsPerDay: number, _industry: Industry | null): BundleRecommendation {
  const ticketsPerMonth = ticketsPerDay * 30;

  // High tier
  if (ticketsPerMonth > 5000) {
    return {
      tier: 'high',
      quantity: 1,
      monthlyCost: TIER_CONFIG.high.monthlyPrice,
      annualCost: TIER_CONFIG.high.annualPrice,
      message: `1× PARWA High ($${TIER_CONFIG.high.monthlyPrice.toLocaleString()}/mo)`,
      subMessage: 'Handles complex operations with autonomous approval flows',
      color: 'orange',
      isWarning: false,
    };
  }

  // Growth tier
  if (ticketsPerMonth > 1000) {
    return {
      tier: 'growth',
      quantity: 1,
      monthlyCost: TIER_CONFIG.growth.monthlyPrice,
      annualCost: TIER_CONFIG.growth.annualPrice,
      message: `1× PARWA Growth ($${TIER_CONFIG.growth.monthlyPrice.toLocaleString()}/mo)`,
      subMessage: 'Handles tickets + thinks for you',
      color: 'orange',
      isWarning: false,
    };
  }

  // Sweet spot for Starter
  if (ticketsPerMonth <= 1000) {
    return {
      tier: 'starter',
      quantity: 1,
      monthlyCost: TIER_CONFIG.starter.monthlyPrice,
      annualCost: TIER_CONFIG.starter.annualPrice,
      message: `1× PARWA Starter ($${TIER_CONFIG.starter.monthlyPrice}/mo)`,
      subMessage: 'Perfect for FAQ deflection & basic automation',
      color: 'orange',
      isWarning: false,
    };
  }

  // Fallback
  return {
    tier: 'starter',
    quantity: 1,
    monthlyCost: TIER_CONFIG.starter.monthlyPrice,
    annualCost: TIER_CONFIG.starter.annualPrice,
    message: `1× PARWA Starter ($${TIER_CONFIG.starter.monthlyPrice}/mo)`,
    subMessage: 'Perfect for FAQ deflection',
    color: 'orange',
    isWarning: false,
  };
}

function getStackedWarning(ticketsPerDay: number): BundleRecommendation | null {
  const ticketsPerMonth = ticketsPerDay * 30;

  // If in the range where 2 starters might be tempting but Growth is better
  if (ticketsPerMonth > 1000 && ticketsPerMonth <= 2000) {
    return {
      tier: 'starter-stacked',
      quantity: 2,
      monthlyCost: TIER_CONFIG.starter.monthlyPrice * 2,
      annualCost: TIER_CONFIG.starter.annualPrice * 2,
      message: `2× PARWA Starter ($${(TIER_CONFIG.starter.monthlyPrice * 2).toLocaleString()}/mo)`,
      subMessage: 'Creates 2× review work for your team — Growth is smarter',
      color: 'amber',
      isWarning: true,
    };
  }

  return null;
}

interface SmartBundleVisualizerProps {
  selectedIndustry: Industry | null;
  onIndustrySelect: (industry: Industry) => void;
}

export function SmartBundleVisualizer({ selectedIndustry, onIndustrySelect }: SmartBundleVisualizerProps) {
  const [ticketVolume, setTicketVolume] = useState(200);

  const ticketsPerMonth = ticketVolume * 30;

  const recommendation = useMemo(
    () => getRecommendation(ticketVolume, selectedIndustry),
    [ticketVolume, selectedIndustry]
  );

  const stackedWarning = useMemo(
    () => getStackedWarning(ticketVolume),
    [ticketVolume]
  );

  const getVolumeLabel = (volume: number) => {
    if (volume <= 100) return 'Low volume';
    if (volume <= 350) return 'Medium volume';
    if (volume <= 650) return 'High volume';
    return 'Enterprise volume';
  };

  const savingsWithAnnual = recommendation.monthlyCost * 12 - recommendation.annualCost * 12;

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 sm:p-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-11 h-11 rounded-xl bg-orange-500/15 flex items-center justify-center">
          <SlidersHorizontal className="w-6 h-6 text-orange-400" />
        </div>
        <div>
          <h3 className="text-xl font-bold text-white">Smart Bundle Visualizer</h3>
          <p className="text-sm text-orange-200/50">Find the right plan for your ticket volume</p>
        </div>
      </div>

      {/* Industry Selector */}
      <div className="mb-6">
        <IndustrySelector
          selectedIndustry={selectedIndustry}
          onSelect={onIndustrySelect}
        />
      </div>

      {/* Ticket Volume Slider */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <label className="text-sm font-semibold text-orange-200/70">Daily Ticket Volume</label>
          <div className="flex items-center gap-2">
            <span className="text-lg font-black text-white">{ticketVolume}</span>
            <span className="text-xs text-orange-200/30">tickets/day</span>
          </div>
        </div>

        <input
          type="range"
          min={50}
          max={1000}
          step={10}
          value={ticketVolume}
          onChange={(e) => setTicketVolume(Number(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer"
          style={{
            background: `linear-gradient(to right, #FF7F11 0%, #FF7F11 ${((ticketVolume - 50) / 950) * 100}%, rgba(255,255,255,0.1) ${((ticketVolume - 50) / 950) * 100}%, rgba(255,255,255,0.1) 100%)`,
          }}
          aria-label="Ticket volume slider"
        />

        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-orange-200/30">50/day</span>
          <span className="text-xs font-medium text-orange-400">{getVolumeLabel(ticketVolume)}</span>
          <span className="text-xs text-orange-200/30">1,000/day</span>
        </div>

        {/* Stats row */}
        <div className="flex flex-wrap gap-3 mt-4">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
            <TrendingUp className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-xs text-orange-200/50">
              <span className="font-semibold text-orange-300">{ticketsPerMonth.toLocaleString()}</span> tickets/mo
            </span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10">
            <Sparkles className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-xs text-orange-200/50">
              ~<span className="font-semibold text-orange-300">{Math.ceil(ticketsPerMonth / 22)}</span> tickets/weekday
            </span>
          </div>
        </div>
      </div>

      {/* Recommendation */}
      <div
        className={`rounded-xl border-2 p-5 transition-all duration-500 ${
          recommendation.isWarning
            ? 'border-amber-500/30 bg-amber-500/10'
            : 'border-orange-500/30 bg-orange-500/10'
        }`}
      >
        <div className="flex items-start gap-3">
          {recommendation.isWarning ? (
            <AlertTriangle className="w-6 h-6 text-amber-400 flex-shrink-0 mt-0.5" />
          ) : (
            <CheckCircle2 className="w-6 h-6 text-orange-400 flex-shrink-0 mt-0.5" />
          )}
          <div className="flex-1">
            <p className="text-base font-bold text-white mb-1">{recommendation.message}</p>
            <p className="text-sm text-orange-200/50 mb-3">{recommendation.subMessage}</p>

            {/* Annual savings callout */}
            <div className="flex items-center gap-4">
              <div>
                <span className="text-xs text-orange-200/30">Monthly</span>
                <p className="text-sm font-bold text-white">${recommendation.monthlyCost.toLocaleString()}/mo</p>
              </div>
              <ArrowRight className="w-4 h-4 text-orange-200/30" />
              <div>
                <span className="text-xs text-orange-200/30">Annual</span>
                <p className="text-sm font-bold text-orange-400">${recommendation.annualCost.toLocaleString()}/mo</p>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-300 font-semibold">
                Save ${savingsWithAnnual.toLocaleString()}/yr
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Stacked Warning */}
      {stackedWarning && (
        <div className="mt-4 rounded-xl border-2 border-dashed border-amber-500/20 bg-amber-500/5 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400/70 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-amber-300 mb-1">
                {stackedWarning.message}
              </p>
              <p className="text-xs text-amber-200/50">{stackedWarning.subMessage}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">
                  Extra cost
                </span>
                <span className="text-xs text-amber-200/40">
                  ${(stackedWarning.monthlyCost - TIER_CONFIG.growth.monthlyPrice) > 0
                    ? `+$${stackedWarning.monthlyCost - TIER_CONFIG.growth.monthlyPrice} vs Growth`
                    : `-$${TIER_CONFIG.growth.monthlyPrice - stackedWarning.monthlyCost} vs Growth, but no AI decisions`}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
