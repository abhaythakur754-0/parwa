'use client';

import React from 'react';
import { ArrowRightLeft, X, Check, ArrowRight, TrendingDown, Brain, Clock, Zap } from 'lucide-react';

interface MatrixRow {
  feature: string;
  starterValue: string;
  starterNote?: string;
  growthValue: string;
  growthNote?: string;
  starterGood?: boolean;
  growthGood?: boolean;
  icon?: React.ElementType;
}

const MATRIX_ROWS: MatrixRow[] = [
  {
    feature: 'Monthly Cost',
    starterValue: '$1,998',
    growthValue: '$2,499',
    starterGood: true,
    growthGood: false,
    icon: TrendingDown,
  },
  {
    feature: 'Industry Decisions',
    starterValue: '0 — Fully manual',
    growthValue: 'AI Recommends (Approve / Review / Deny)',
    growthGood: true,
    icon: Brain,
  },
  {
    feature: 'Pattern Learning',
    starterValue: 'No',
    growthValue: 'Yes — Agent Lightning',
    growthGood: true,
    icon: Zap,
  },
  {
    feature: 'Manager Overhead',
    starterValue: '4+ hrs/day',
    starterNote: 'Reviewing every decision across 2 instances',
    growthValue: '30 min/day',
    growthNote: 'Only reviewing AI-flagged items',
    growthGood: true,
    icon: Clock,
  },
  {
    feature: 'Smart Router',
    starterValue: 'No — single LLM tier',
    growthValue: '3-tier LLM routing',
    growthGood: true,
    icon: Zap,
  },
  {
    feature: 'Batch Approvals',
    starterValue: 'No',
    growthValue: 'Semantic clustering + batch approve',
    growthGood: true,
    icon: Check,
  },
  {
    feature: 'Analytics & ROI',
    starterValue: 'Basic',
    growthValue: 'Advanced analytics & ROI tracking',
    growthGood: true,
    icon: TrendingDown,
  },
];

export function AntiArbitrageMatrix() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl overflow-hidden">
      {/* Header */}
      <div className="p-6 sm:p-8 pb-0">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-11 h-11 rounded-xl bg-orange-500/15 flex items-center justify-center">
            <ArrowRightLeft className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">Why Not Stack Starters?</h3>
            <p className="text-sm text-orange-200/50">2× PARWA Starter vs 1× PARWA Growth — the real comparison</p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="p-4 sm:p-6 sm:pt-4 overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead>
            <tr>
              <th className="text-left py-3 px-4 text-xs font-semibold text-orange-200/30 uppercase tracking-wider">
                Feature
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-amber-400/60 uppercase tracking-wider">
                <div className="flex items-center gap-1.5">
                  <X className="w-3.5 h-3.5" />
                  2× PARWA Starter
                </div>
                <span className="block text-xs font-normal text-amber-200/30 mt-0.5 normal-case">$1,998/mo</span>
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-orange-400/60 uppercase tracking-wider">
                <div className="flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />
                  1× PARWA Growth
                </div>
                <span className="block text-xs font-normal text-orange-200/30 mt-0.5 normal-case">$2,499/mo</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {MATRIX_ROWS.map((row, index) => {
              const Icon = row.icon;
              return (
                <tr
                  key={row.feature}
                  className={`border-t border-white/5 ${index % 2 === 0 ? 'bg-white/[0.02]' : ''}`}
                >
                  <td className="py-3.5 px-4">
                    <div className="flex items-center gap-2.5">
                      {Icon && (
                        <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                          <Icon className="w-3.5 h-3.5 text-orange-200/40" />
                        </div>
                      )}
                      <span className="text-sm font-medium text-orange-200/70">{row.feature}</span>
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className={`text-sm ${row.starterGood ? 'text-orange-300' : 'text-orange-200/40'}`}>
                        {row.starterValue}
                      </span>
                      {row.starterNote && (
                        <span className="text-xs text-orange-200/25 mt-0.5">{row.starterNote}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className={`text-sm font-medium ${row.growthGood ? 'text-orange-400' : 'text-orange-200/40'}`}>
                        {row.growthValue}
                      </span>
                      {row.growthNote && (
                        <span className="text-xs text-orange-200/25 mt-0.5">{row.growthNote}</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Bottom message */}
      <div className="mx-4 sm:mx-6 mb-4 sm:mb-6">
        <div className="rounded-xl border border-orange-500/20 bg-orange-500/5 p-4 flex items-start gap-3">
          <ArrowRight className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-orange-300 mb-1">
              For $501 more/month, PARWA Growth eliminates 3.5+ hours of daily management overhead
            </p>
            <p className="text-xs text-orange-200/40 leading-relaxed">
              That&apos;s the equivalent of saving a half-time manager&apos;s salary. Growth doesn&apos;t just handle more tickets — it thinks, learns, and routes so your team focuses on exceptions, not routine.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
