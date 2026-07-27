'use client';

import React, { useState } from 'react';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import { AntiArbitrageMatrix } from '@/components/models/AntiArbitrageMatrix';
import { ChatWidget } from '@/components/chat/ChatWidget';
import { BookDemoModal } from '@/components/demo/BookDemoModal';
import { useAppStore } from '@/lib/store';
import { useAuth } from '@/contexts/AuthContext';
import {
  Star, Check, Phone, Mail, MessageSquare,
  Video, Zap, Shield, Sparkles,
} from 'lucide-react';

// Only 2 tiers — Mini removed
type VariantId = 'parwa' | 'high';

interface VariantData {
  id: VariantId;
  name: string;
  tagline: string;
  monthlyPrice: number;
  annualPrice: number;
  ticketsPerMonth: number;
  badge?: string;
  channels: { label: string; icon: React.ReactNode }[];
  commonFeatures: string[];
  uniqueFeatures: string[];
  keyAdvantage?: string;
  smartDecisions?: string;
  roi: string;
  bestFor: string;
  coreCapability?: string;
}

const commonFeatures: Record<VariantId, string[]> = {
  parwa: ['Up to 5 AI agents', '2,499 tickets/month', 'Email, Chat, SMS & Voice', 'AI decision recommendations', 'Smart Router — 3-tier LLM routing', 'Agent Lightning — continuous learning', 'Batch approval system', 'Advanced analytics & ROI tracking'],
  high: ['Up to 8 AI agents (+$3/each extra)', '3,999 tickets/month', 'Email, Chat, SMS & Voice channels', 'Quality coaching system', 'Churn prediction & proactive retention', 'Video support & screen sharing', 'Up to 5 concurrent voice calls', 'Strategic insights & revenue analytics', 'Custom integrations & API access', 'Peer review system', 'Priority support', 'Full autonomous operations'],
};

const variantData: VariantData[] = [
  {
    id: 'parwa',
    name: 'PARWA',
    tagline: '"The Junior Agent"',
    monthlyPrice: 2499,
    annualPrice: 1999,
    ticketsPerMonth: 2499,
    badge: 'Recommended',
    channels: [{ label: 'Email, Chat, SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }],
    commonFeatures: commonFeatures.parwa,
    uniqueFeatures: ['Multi-department routing', 'Custom workflow automation', 'Intelligent routing', 'Adaptive learning'],
    keyAdvantage: 'Cuts review time by 80%',
    smartDecisions: 'Recommends refunds based on policy',
    roi: 'Replaces ~$18k/month in junior agent salaries',
    bestFor: 'SMBs with 200–500 daily tickets',
    coreCapability: 'Intelligent Recommendations + AI Decision Engine.',
  },
  {
    id: 'high',
    name: 'PARWA High',
    tagline: '"The Senior Agent"',
    monthlyPrice: 3999,
    annualPrice: 3199,
    ticketsPerMonth: 3999,
    channels: [{ label: 'All Parwa + Video', icon: <Video className="w-3.5 h-3.5" /> }],
    commonFeatures: commonFeatures.high,
    uniqueFeatures: ['Full custom workflow engine', 'Advanced pattern recognition', 'Cross-department coordination', 'VIP handling'],
    keyAdvantage: 'Unlimited financial actions',
    roi: 'Replaces ~$28k/month in senior agent salaries',
    bestFor: 'SMBs with 500+ daily tickets',
    coreCapability: 'VIP Handling, Strategic Intelligence, Video Support.',
  },
];

const trustIndicators = [
  { icon: Zap, label: 'AI-Powered' },
  { icon: Shield, label: 'Enterprise Ready' },
  { icon: Sparkles, label: 'Continuous Learning' },
];

export default function ModelsPage() {
  const navigate = useAppStore((s) => s.navigate);
  const { isAuthenticated } = useAuth();
  const [isAnnual, setIsAnnual] = useState(false);
  const [quantities, setQuantities] = useState<Record<VariantId, number>>({ parwa: 0, high: 0 });
  const [showDemoModal, setShowDemoModal] = useState(false);

  const handleQuantityChange = (vid: VariantId, qty: number) => {
    setQuantities((prev) => ({ ...prev, [vid]: Math.max(0, Math.min(qty, 10)) }));
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'linear-gradient(165deg, #1A1A1A 0%, #2A1A0A 30%, #2D1F0E 60%, #3D2A10 80%, #1A1A1A 100%)' }}>
      <NavigationBar />
      <main className="flex-grow relative">
        {/* Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full blur-[150px]" style={{ backgroundColor: 'rgba(255,127,17,0.08)' }} />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full blur-[120px]" style={{ backgroundColor: 'rgba(255,127,17,0.06)' }} />
        </div>

        {/* Hero */}
        <section className="relative py-16 sm:py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border mb-6 bg-orange-500/10 border-orange-500/20">
              <div className="w-2 h-2 rounded-full animate-pulse bg-orange-400" />
              <span className="text-sm font-medium text-orange-400">AI-Powered Support Agents</span>
            </div>
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">
              Meet the <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">PARWA</span> AI Family
            </h1>
            <p className="text-base sm:text-lg max-w-2xl mx-auto text-gray-400">
              Two intelligent AI agents designed for different stages of business growth.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 mt-8">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-center gap-2 px-3 py-2 rounded-full border bg-orange-500/10 border-orange-500/30">
                    <Icon className="w-3.5 h-3.5 text-orange-400" />
                    <span className="text-xs font-medium text-gray-300">{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Pricing Cards — shown directly, no industry selector */}
        <section className="relative pb-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-10">
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2">
                Pricing & <span className="bg-gradient-to-r from-orange-300 to-orange-400 bg-clip-text text-transparent">Plans</span>
              </h2>
              {/* Annual toggle */}
              <button
                onClick={() => setIsAnnual(!isAnnual)}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-orange-500/30 bg-orange-500/10"
              >
                <span className={`text-sm ${isAnnual ? 'text-gray-500' : 'text-orange-400 font-bold'}`}>Monthly</span>
                <span className={`w-10 h-5 rounded-full transition-colors ${isAnnual ? 'bg-orange-500' : 'bg-white/15'}`}>
                  <span className={`block w-4 h-4 rounded-full bg-white transition-transform ${isAnnual ? 'translate-x-5' : 'translate-x-1'}`} />
                </span>
                <span className={`text-sm ${isAnnual ? 'text-orange-400 font-bold' : 'text-gray-500'}`}>Annual</span>
              </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {variantData.map((variant) => {
                const isRecommended = variant.badge === 'Recommended';
                const price = isAnnual ? variant.annualPrice : variant.monthlyPrice;
                const qty = quantities[variant.id] || 0;
                const isActive = qty > 0;

                return (
                  <div
                    key={variant.id}
                    className={`relative rounded-2xl border-2 p-6 sm:p-8 transition-all duration-500 ${isActive ? 'hover:-translate-y-2' : 'hover:-translate-y-1'}`}
                    style={{
                      border: isActive ? '2px solid #FF7F11' : isRecommended ? '2px solid rgba(255,127,17,0.4)' : '2px solid rgba(255,255,255,0.1)',
                      background: isActive
                        ? 'linear-gradient(135deg, rgba(255,127,17,0.12) 0%, rgba(255,127,17,0.04) 100%)'
                        : 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
                    }}
                  >
                    {isRecommended && (
                      <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
                        <span className="inline-flex items-center gap-1 px-4 py-1.5 text-xs font-bold bg-gradient-to-r from-amber-400 to-yellow-400 text-gray-900 rounded-full shadow-lg">
                          <Star className="w-3 h-3" fill="currentColor" /> Recommended
                        </span>
                      </div>
                    )}
                    <div className="mb-4 mt-1">
                      <h3 className="text-2xl sm:text-3xl font-extrabold text-white mb-1">{variant.name}</h3>
                      <p className="text-sm font-medium text-orange-400">{variant.tagline}</p>
                    </div>
                    <div className="mb-5 pb-5 border-b border-white/10">
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl sm:text-5xl font-black" style={{ color: isActive ? '#FF7F11' : 'white' }}>
                          ${price.toLocaleString()}
                        </span>
                        <span className="text-sm text-gray-500">/month</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{variant.ticketsPerMonth.toLocaleString()} tickets/month included</p>
                    </div>

                    {/* Features */}
                    <div className="mb-5">
                      <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-3">What&apos;s Included</p>
                      <ul className="space-y-2">
                        {variant.commonFeatures.map((f) => (
                          <li key={f} className="flex items-start gap-2 text-sm text-gray-300">
                            <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                            {f}
                          </li>
                        ))}
                      </ul>
                      <p className="text-xs text-orange-400 uppercase tracking-wider font-semibold mt-4 mb-3">Key Features</p>
                      <ul className="space-y-2">
                        {variant.uniqueFeatures.map((f) => (
                          <li key={f} className="flex items-start gap-2 text-sm text-gray-300">
                            <Check className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Quantity */}
                    {isAuthenticated && (
                      <div className="flex items-center gap-3 mb-5">
                        <button
                          onClick={() => handleQuantityChange(variant.id, qty - 1)}
                          className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center"
                        >
                          −
                        </button>
                        <span className="text-lg font-bold text-white w-8 text-center">{qty}</span>
                        <button
                          onClick={() => handleQuantityChange(variant.id, qty + 1)}
                          className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center"
                        >
                          +
                        </button>
                      </div>
                    )}

                    <button
                      onClick={() => navigate(isAuthenticated ? 'dashboard' : 'signup')}
                      className="w-full py-3.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] hover:from-orange-400 hover:to-orange-300 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 transition-all"
                    >
                      {isAuthenticated ? 'Hire Agent' : 'Get Started'}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Anti-Arbitrage Matrix */}
        <section className="relative pb-16">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <AntiArbitrageMatrix />
          </div>
        </section>
      </main>
      <Footer />
      <ChatWidget onBookDemo={() => setShowDemoModal(true)} />
      {showDemoModal && <BookDemoModal onClose={() => setShowDemoModal(false)} />}
    </div>
  );
}
