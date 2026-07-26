'use client';

import React from 'react';
import { ArrowRightLeft, X, Check, ArrowRight, TrendingDown, Brain, Clock, Zap } from 'lucide-react';

interface MatrixRow {
  feature: string;
  parwaValue: string;
  parwaNote?: string;
  highValue: string;
  highNote?: string;
  parwaGood?: boolean;
  highGood?: boolean;
  icon?: React.ElementType;
}

const MATRIX_ROWS: MatrixRow[] = [
  {
    feature: 'Monthly Cost',
    parwaValue: '$2,499',
    highValue: '$3,999',
    parwaGood: true,
    highGood: false,
    icon: TrendingDown,
  },
  {
    feature: 'AI Agents',
    parwaValue: '5 agents',
    highValue: '8 agents (+$3/each extra)',
    highGood: true,
    icon: Brain,
  },
  {
    feature: 'Financial Actions',
    parwaValue: 'Refunds up to $500, credits up to $200',
    highValue: 'Unlimited refunds + credits',
    highGood: true,
    icon: Check,
  },
  {
    feature: 'Ticket Capacity',
    parwaValue: '2,499 tickets/mo',
    highValue: '3,999 tickets/mo',
    highGood: true,
    icon: Zap,
  },
  {
    feature: 'Team Members',
    parwaValue: '10',
    highValue: '25',
    highGood: true,
    icon: Check,
  },
  {
    feature: 'Knowledge Base',
    parwaValue: '500 docs',
    highValue: '2,000 docs',
    highGood: true,
    icon: Check,
  },
  {
    feature: 'Voice Slots',
    parwaValue: '2 concurrent',
    highValue: '5 concurrent',
    highGood: true,
    icon: Clock,
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
            <h3 className="text-xl font-bold text-white">PARWA vs PARWA High</h3>
            <p className="text-sm text-orange-200/50">Is the upgrade worth $1,500/month? Here&apos;s the real comparison</p>
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
                  PARWA
                </div>
                <span className="block text-xs font-normal text-amber-200/30 mt-0.5 normal-case">$2,499/mo</span>
              </th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-purple-400/60 uppercase tracking-wider">
                <div className="flex items-center gap-1.5">
                  <Check className="w-3.5 h-3.5" />
                  PARWA High
                </div>
                <span className="block text-xs font-normal text-purple-200/30 mt-0.5 normal-case">$3,999/mo</span>
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
                      <span className={`text-sm ${row.parwaGood ? 'text-orange-300' : 'text-orange-200/40'}`}>
                        {row.parwaValue}
                      </span>
                      {row.parwaNote && (
                        <span className="text-xs text-orange-200/25 mt-0.5">{row.parwaNote}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-col">
                      <span className={`text-sm font-medium ${row.highGood ? 'text-purple-400' : 'text-orange-200/40'}`}>
                        {row.highValue}
                      </span>
                      {row.highNote && (
                        <span className="text-xs text-purple-200/25 mt-0.5">{row.highNote}</span>
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
        <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-4 flex items-start gap-3">
          <ArrowRight className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold text-purple-300 mb-1">
              For $1,500 more/month, PARWA High gives you 60% more capacity + unlimited financial actions
            </p>
            <p className="text-xs text-purple-200/40 leading-relaxed">
              More agents, more tickets, more voice slots, and unlimited refund/credit authority. PARWA High doesn&apos;t just handle more volume — it makes autonomous financial decisions that would otherwise require human approval.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
