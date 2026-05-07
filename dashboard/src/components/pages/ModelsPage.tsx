'use client';

import React, { useState } from 'react';
import { NavigationBar, Footer } from '@/components/landing';
import { useAppStore } from '@/lib/store';
import { useAuth } from '@/contexts/AuthContext';
import {
  Star, Check, Phone, Mail, MessageSquare,
  Video, ShoppingCart, Cloud, Truck, Briefcase, Zap, Shield, Sparkles,
} from 'lucide-react';

type Industry = 'ecommerce' | 'saas' | 'logistics' | 'others';
type VariantId = 'starter' | 'growth' | 'high';

interface IndustryConfig {
  id: Industry;
  label: string;
  description: string;
  icon: React.ReactNode;
  heroText: string;
}

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
  roi: string;
  bestFor: string;
  coreLimitation?: string;
  coreCapability?: string;
}

const industries: IndustryConfig[] = [
  { id: 'ecommerce', label: 'E-commerce', description: 'Online retail & D2C brands', icon: <ShoppingCart className="w-7 h-7" />, heroText: 'Automate order tracking, returns, cart recovery & fraud detection with AI built for online retail.' },
  { id: 'saas', label: 'SaaS', description: 'Software & tech companies', icon: <Cloud className="w-7 h-7" />, heroText: 'Handle technical support, API troubleshooting, churn prediction & in-app guidance.' },
  { id: 'logistics', label: 'Logistics', description: 'Shipping & supply chain', icon: <Truck className="w-7 h-7" />, heroText: 'Track shipments, coordinate drivers, manage proof of delivery automatically.' },
  { id: 'others', label: 'Others', description: 'All other industries', icon: <Briefcase className="w-7 h-7" />, heroText: "PARWA adapts to any industry. Tell us your needs and we'll tailor the perfect AI solution." },
];

const commonFeatures: Record<VariantId, string[]> = {
  starter: ['Up to 3 AI agents', '1,000 tickets/month', 'Email & Chat channels', 'FAQ handling from knowledge base', 'Phone — 2 concurrent calls', 'Automated data collection & intake'],
  growth: ['Up to 8 AI agents', '5,000 tickets/month', 'Email, Chat, SMS & Voice', 'AI decision recommendations', 'Smart Router — 3-tier LLM routing', 'Agent Lightning — continuous learning', 'Batch approval system', 'Advanced analytics & ROI tracking'],
  high: ['Up to 15 AI agents', '15,000 tickets/month', 'Email, Chat, SMS & Voice channels', 'Quality coaching system', 'Churn prediction & proactive retention', 'Video support & screen sharing', 'Up to 5 concurrent voice calls', 'Strategic insights & revenue analytics', 'Custom integrations & API access', 'Peer review system', 'Priority support', 'Full autonomous operations'],
};

const uniqueFeatures: Record<Industry, Record<VariantId, string[]>> = {
  ecommerce: { starter: ['Order status & tracking automation', 'Return eligibility checking'], growth: ['Cart abandonment detection', 'Visual Damage Verification', 'Recommends refunds based on policy'], high: ['Cart Recovery Intelligence', 'Sizing Anomaly Detection', 'Fraud pattern detection'] },
  saas: { starter: ['Technical FAQ handling', 'Subscription status checking'], growth: ['Technical Troubleshooting Flow', 'API Error Diagnosis', 'In-App Guidance'], high: ['Churn Prediction Engine', 'Complex technical troubleshooting', 'Feature adoption strategies'] },
  logistics: { starter: ['Shipping FAQ handling', 'Delivery tracking via APIs'], growth: ['GPS Tracking Integration', 'Driver Coordination', 'Route optimization'], high: ['Proof of Delivery Management', 'Hazmat Protocol', 'Freight Damage Claims'] },
  others: { starter: ['General inquiry handling', 'Billing & payment status'], growth: ['Multi-department routing', 'Custom workflow automation'], high: ['Full custom workflow engine', 'Advanced pattern recognition', 'Cross-department coordination'] },
};

const variantData: Record<Industry, VariantData[]> = {
  ecommerce: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'Phone', icon: <Phone className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.starter, uniqueFeatures: uniqueFeatures.ecommerce.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'E-commerce SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, badge: 'Recommended', channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.growth, uniqueFeatures: uniqueFeatures.ecommerce.growth, keyAdvantage: 'Cuts review time by 80%', smartDecisions: 'Recommends refunds based on policy', roi: 'Replaces ~$18k/month in junior agent salaries', bestFor: 'E-commerce SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, channels: [{ label: 'All Growth + Video', icon: <Video className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.high, uniqueFeatures: uniqueFeatures.ecommerce.high, keyAdvantage: 'Approves returns up to $50', roi: 'Replaces ~$28k/month in senior agent salaries', bestFor: 'E-commerce SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support.' },
  ],
  saas: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.starter, uniqueFeatures: uniqueFeatures.saas.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'SaaS SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, badge: 'Recommended', channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.growth, uniqueFeatures: uniqueFeatures.saas.growth, keyAdvantage: 'Cuts review time by 80%', roi: 'Replaces ~$18k/month in junior agent salaries', bestFor: 'SaaS SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, channels: [{ label: 'All Growth + Video', icon: <Video className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.high, uniqueFeatures: uniqueFeatures.saas.high, keyAdvantage: 'Churn prediction engine', roi: 'Replaces ~$28k/month in senior agent salaries', bestFor: 'SaaS SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support.' },
  ],
  logistics: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <Phone className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.starter, uniqueFeatures: uniqueFeatures.logistics.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'Logistics SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, badge: 'Recommended', channels: [{ label: 'All Starter + Voice', icon: <Zap className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.growth, uniqueFeatures: uniqueFeatures.logistics.growth, keyAdvantage: 'GPS tracking, driver coordination', roi: 'Replaces ~$18k/month in junior coordinator salaries', bestFor: 'Logistics SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, channels: [{ label: 'All Growth + Video', icon: <Video className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.high, uniqueFeatures: uniqueFeatures.logistics.high, keyAdvantage: 'POD management, hazmat protocol', roi: 'Replaces ~$28k/month in senior coordinator salaries', bestFor: 'Logistics SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support.' },
  ],
  others: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.starter, uniqueFeatures: uniqueFeatures.others.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, badge: 'Recommended', channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.growth, uniqueFeatures: uniqueFeatures.others.growth, keyAdvantage: 'Intelligent routing, adaptive learning', roi: 'Replaces ~$18k/month in junior agent salaries', bestFor: 'SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, channels: [{ label: 'All Growth + Video', icon: <Video className="w-3.5 h-3.5" /> }], commonFeatures: commonFeatures.high, uniqueFeatures: uniqueFeatures.others.high, keyAdvantage: 'Custom workflows, cross-department coordination', roi: 'Replaces ~$28k/month in senior agent salaries', bestFor: 'SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support.' },
  ],
};

const trustIndicators = [
  { icon: Zap, label: 'AI-Powered' },
  { icon: Shield, label: 'Enterprise Ready' },
  { icon: Sparkles, label: 'Continuous Learning' },
];

export default function ModelsPage() {
  const navigate = useAppStore((s) => s.navigate);
  const { isAuthenticated } = useAuth();
  const [selectedIndustry, setSelectedIndustry] = useState<Industry | null>(null);
  const [isAnnual, setIsAnnual] = useState(false);
  const [quantities, setQuantities] = useState<Record<VariantId, number>>({ starter: 0, growth: 0, high: 0 });

  const handleIndustryClick = (id: Industry) => {
    setSelectedIndustry(selectedIndustry === id ? null : id);
    setQuantities({ starter: 0, growth: 0, high: 0 });
  };

  const handleQuantityChange = (vid: VariantId, qty: number) => {
    setQuantities((prev) => ({ ...prev, [vid]: Math.max(0, Math.min(qty, 10)) }));
  };

  const activeIndustry = selectedIndustry ? industries.find((i) => i.id === selectedIndustry) : null;
  const currentVariants = selectedIndustry ? variantData[selectedIndustry] : null;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#0A0A0A' }}>
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
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white mb-4">Meet the <span className="bg-gradient-to-r from-orange-300 via-orange-400 to-orange-200 bg-clip-text text-transparent">PARWA</span> AI Family</h1>
            <p className="text-base sm:text-lg max-w-2xl mx-auto text-gray-400">
              {activeIndustry ? activeIndustry.heroText : 'Three intelligent AI agents designed for different stages of business growth.'}
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

        {/* Industry Selector */}
        <section className="relative pb-12">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-center text-lg sm:text-xl font-semibold text-white mb-8">Select Your Industry</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {industries.map((ind) => {
                const isActive = selectedIndustry === ind.id;
                return (
                  <button key={ind.id} onClick={() => handleIndustryClick(ind.id)}
                    className="relative rounded-2xl p-6 text-left transition-all duration-500 hover:-translate-y-1 group cursor-pointer"
                    style={{ background: isActive ? 'linear-gradient(135deg, rgba(255,127,17,0.15) 0%, rgba(255,127,17,0.05) 100%)' : 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)', border: isActive ? '2px solid rgba(255,127,17,0.6)' : '2px solid rgba(255,255,255,0.1)', boxShadow: isActive ? '0 20px 50px rgba(255,127,17,0.15)' : '0 20px 50px rgba(0,0,0,0.2)' }}>
                    <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 bg-orange-500/10 border border-orange-500/15 text-orange-400">{ind.icon}</div>
                    <h3 className="text-lg font-bold text-white mb-1">{ind.label}</h3>
                    <p className="text-sm text-gray-500">{ind.description}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        {/* Pricing Cards */}
        {selectedIndustry && currentVariants && (
          <section className="relative pb-16">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="text-center mb-10">
                <h2 className="text-2xl sm:text-3xl font-bold text-white mb-2"><span className="bg-gradient-to-r from-orange-300 to-orange-400 bg-clip-text text-transparent">{activeIndustry!.label}</span> Pricing & Plans</h2>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {currentVariants.map((variant) => {
                  const isRecommended = variant.badge === 'Recommended';
                  const price = isAnnual ? variant.annualPrice : variant.monthlyPrice;
                  const qty = quantities[variant.id] || 0;
                  const isActive = qty > 0;

                  return (
                    <div key={variant.id} className={`relative rounded-2xl border-2 p-6 sm:p-8 transition-all duration-500 ${isActive ? 'hover:-translate-y-2' : 'hover:-translate-y-1'}`}
                      style={{ border: isActive ? '2px solid #FF7F11' : isRecommended ? '2px solid rgba(255,127,17,0.4)' : '2px solid rgba(255,255,255,0.1)', background: isActive ? 'linear-gradient(135deg, rgba(255,127,17,0.12) 0%, rgba(255,127,17,0.04) 100%)' : 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)' }}>
                      {isRecommended && (
                        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
                          <span className="inline-flex items-center gap-1 px-4 py-1.5 text-xs font-bold bg-gradient-to-r from-amber-400 to-yellow-400 text-gray-900 rounded-full shadow-lg"><Star className="w-3 h-3" fill="currentColor" /> Recommended</span>
                        </div>
                      )}
                      <div className="mb-4 mt-1">
                        <h3 className="text-2xl sm:text-3xl font-extrabold text-white mb-1">{variant.name}</h3>
                        <p className="text-sm font-medium text-orange-400">{variant.tagline}</p>
                      </div>
                      <div className="mb-5 pb-5 border-b border-white/10">
                        <div className="flex items-baseline gap-1">
                          <span className="text-4xl sm:text-5xl font-black" style={{ color: isActive ? '#FF7F11' : 'white' }}>${price.toLocaleString()}</span>
                          <span className="text-sm text-gray-500">/month</span>
                        </div>
                      </div>

                      {/* Features */}
                      <div className="mb-5">
                        <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-3">What&apos;s Included</p>
                        <ul className="space-y-2">
                          {variant.commonFeatures.map((f) => (
                            <li key={f} className="flex items-start gap-2 text-sm text-gray-300"><Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />{f}</li>
                          ))}
                        </ul>
                        <p className="text-xs text-orange-400 uppercase tracking-wider font-semibold mt-4 mb-3">{activeIndustry!.label} Specific</p>
                        <ul className="space-y-2">
                          {variant.uniqueFeatures.map((f) => (
                            <li key={f} className="flex items-start gap-2 text-sm text-gray-300"><Check className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />{f}</li>
                          ))}
                        </ul>
                      </div>

                      {/* Quantity */}
                      {isAuthenticated && (
                        <div className="flex items-center gap-3 mb-5">
                          <button onClick={() => handleQuantityChange(variant.id, qty - 1)} className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center">−</button>
                          <span className="text-lg font-bold text-white w-8 text-center">{qty}</span>
                          <button onClick={() => handleQuantityChange(variant.id, qty + 1)} className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-all flex items-center justify-center">+</button>
                        </div>
                      )}

                      <button onClick={() => navigate(isAuthenticated ? 'dashboard' : 'signup')} className="w-full py-3.5 rounded-xl text-sm font-bold bg-gradient-to-r from-orange-500 to-orange-400 text-[#1A1A1A] hover:from-orange-400 hover:to-orange-300 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/40 transition-all">
                        {isAuthenticated ? 'Hire Agent' : 'Get Started'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        )}
      </main>
      <Footer />
    </div>
  );
}
