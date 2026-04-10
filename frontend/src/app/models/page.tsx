'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import NavigationBar from '@/components/landing/NavigationBar';
import Footer from '@/components/landing/Footer';
import { AntiArbitrageMatrix } from '@/components/pricing';
import { ChatWidget } from '@/components/chat/ChatWidget';
import { BookDemoModal } from '@/components/demo/BookDemoModal';
import { useAuth } from '@/contexts/AuthContext';
import {
  Star, Check, Phone, Mail, MessageSquare, Instagram, Facebook,
  Hash, Video, ShoppingCart, Cloud, Truck, Heart,
  ArrowRight, Zap, Shield, TrendingUp, Sparkles,
  CalendarClock, CreditCard, Info, XCircle, X,
  Bot, ShieldCheck, Minus, Plus, Calendar, Eye,
  Ticket, Users, DollarSign, BarChart3,
} from 'lucide-react';

// ─── Types ───────────────────────────────────────────────────────────────────

type Industry = 'ecommerce' | 'saas' | 'logistics' | 'healthcare';
type VariantId = 'starter' | 'growth' | 'high';

interface IndustryConfig {
  id: Industry;
  label: string;
  description: string;
  primary: string;
  accent: string;
  accentRgb: string;
  icon: React.ReactNode;
  heroText: string;
}

interface ChannelInfo {
  label: string;
  icon: React.ReactNode;
}

interface VariantData {
  id: VariantId;
  name: string;
  tagline: string;
  monthlyPrice: number;
  annualPrice: number;
  ticketsPerMonth: number;
  humanAgentsReplaced: number;
  avgHumanCostPerMonth: number;
  badge?: string;
  scenario: string;
  channels: ChannelInfo[];
  integrations: string[];
  commonFeatures: string[];
  uniqueFeatures: string[];
  keyAdvantage?: string;
  smartDecisions?: string;
  roi: string;
  bestFor: string;
  coreLimitation?: string;
  coreCapability?: string;
}

// ─── Industry Configs ────────────────────────────────────────────────────────

const industries: IndustryConfig[] = [
  {
    id: 'ecommerce',
    label: 'E-commerce',
    description: 'Online retail & D2C brands',
    primary: '#0A3D2E',
    accent: '#D4AF37',
    accentRgb: '212,175,55',
    icon: <ShoppingCart className="w-7 h-7" />,
    heroText: 'Automate order tracking, returns, cart recovery & fraud detection with AI built for online retail.',
  },
  {
    id: 'saas',
    label: 'SaaS',
    description: 'Software & tech companies',
    primary: '#0A1A2E',
    accent: '#C0C0C0',
    accentRgb: '192,192,192',
    icon: <Cloud className="w-7 h-7" />,
    heroText: 'Handle technical support, API troubleshooting, churn prediction & in-app guidance for software teams.',
  },
  {
    id: 'logistics',
    label: 'Logistics',
    description: 'Shipping & supply chain',
    primary: '#1A1A1A',
    accent: '#FF7F11',
    accentRgb: '255,127,17',
    icon: <Truck className="w-7 h-7" />,
    heroText: 'Track shipments, coordinate drivers, manage proof of delivery & handle freight damage claims automatically.',
  },
  {
    id: 'healthcare',
    label: 'Healthcare',
    description: 'Clinics, hospitals & telehealth',
    primary: '#1B5E40',
    accent: '#4ADE80',
    accentRgb: '74,222,128',
    icon: <Heart className="w-7 h-7" />,
    heroText: 'Manage appointments, insurance verification & prescription status — with full HIPAA compliance.',
  },
];

// ─── Common Features ────────────────────────────────────────────────────────

const commonFeaturesByVariant: Record<VariantId, string[]> = {
  starter: [
    'Up to 3 AI agents',
    '1,000 tickets/month',
    'Email & Chat channels',
    'FAQ handling from knowledge base',
    'Phone — 2 concurrent calls',
    'Automated data collection & intake',
  ],
  growth: [
    'Up to 8 AI agents',
    '5,000 tickets/month',
    'Email, Chat, SMS & Voice channels',
    'AI decision recommendations (Approve / Review / Deny)',
    'Smart Router — 3-tier LLM routing',
    'Agent Lightning — continuous learning from corrections',
    'Batch approval system with semantic clustering',
    'Advanced analytics & ROI tracking',
  ],
  high: [
    'Up to 15 AI agents',
    '15,000 tickets/month',
    'All channels including Social Media',
    'Quality coaching system',
    'Churn prediction & proactive retention',
    'Video support & screen sharing',
    'Up to 5 concurrent voice calls',
    'Strategic insights & revenue impact analytics',
    'Custom integrations & API access',
    'Peer review (Junior asks Senior before escalation)',
    'Priority support from PARWA team',
    'Full autonomous operations with approval flows',
  ],
};

// ─── Industry-Specific Unique Features ───────────────────────────────────────

const uniqueFeaturesByIndustry: Record<Industry, Record<VariantId, string[]>> = {
  ecommerce: {
    starter: ['Order status & tracking automation', 'Return eligibility checking'],
    growth: ['Cart abandonment detection via Shopify webhook', 'Visual Damage Verification — camera upload for damage claims', 'Recommends refunds based on return policy', 'Detects cart abandonment patterns, suggests FAQ updates'],
    high: ['Cart Recovery Intelligence — personalized re-engagement', 'Sizing Anomaly Detection — flags product team on size issues', 'Seasonal Spike Preparation — identifies upcoming volume spikes', 'Approves returns up to $50, predicts churn', 'Fraud pattern detection & flagging'],
  },
  saas: {
    starter: ['Technical FAQ handling', 'Subscription status checking', 'Bug report collection & escalation'],
    growth: ['Technical Troubleshooting Flow — multi-step guided diagnosis', 'API Error Diagnosis — checks GitHub deployments & status pages', 'Recommends account changes; flags security issues', 'In-App Guidance Intelligence — contextual help by feature'],
    high: ['Churn Prediction Engine — monitors usage via Stripe API', 'Complex technical troubleshooting with security analysis', 'Approves account changes up to $50', 'Feature adoption strategies & proactive outreach'],
  },
  logistics: {
    starter: ['Shipping FAQ handling', 'Delivery tracking via carrier APIs', 'Delivery issue collection & escalation'],
    growth: ['GPS Tracking Integration — real-time carrier API tracking', 'Driver Coordination Protocol — scheduling & route changes via TMS', 'Recommends routing changes; flags delivery exceptions', 'Detects delivery patterns, suggests route optimizations'],
    high: ['Proof of Delivery Management — retrieves POD on demand', 'Hazmat Protocol — auto-detects & routes to human specialist', 'Freight Damage Claims — guided photo documentation', 'Approves routing changes up to $50', 'Carrier performance analysis & management'],
  },
  healthcare: {
    starter: ['Appointment scheduling (book / reschedule / cancel)', 'Insurance coverage type verification', 'Prescription availability checking'],
    growth: ['HIPAA Safety Check — auto-detects clinical keywords & escalates', 'Insurance portal integration for coverage verification', 'Scheduling platform integration for real-time availability', 'BAA compliance verification before deployment'],
    high: ['Full HIPAA/HITECH compliance with state regulations', 'Clinical escalation for PHI keywords (diagnosis, medication, lab results)', 'Mental health crisis detection → immediate human escalation', 'Epic EHR integration via FHIR API', 'No PHI in AI training data — full data isolation'],
  },
};

// ─── Variant Data per Industry (with accurate cost details) ─────────────────

const variantData: Record<Industry, VariantData[]> = {
  ecommerce: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 14000, scenario: "A customer calls at 2 AM asking 'Where\\'s my order?' PARWA Starter answers instantly, checks Shopify, and texts them the tracking link.", channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Instagram DMs', icon: <Instagram className="w-3.5 h-3.5" /> }, { label: 'Facebook DMs', icon: <Facebook className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Phone (2 at once)', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['Shopify', 'Magento', 'BigCommerce', 'WooCommerce'], commonFeatures: commonFeaturesByVariant.starter, uniqueFeatures: uniqueFeaturesByIndustry.ecommerce.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'E-commerce SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 18000, badge: 'Recommended', scenario: "Customer's product won't work. PARWA walks them through 5 troubleshooting steps, determines it's a real defect, creates a return label, and recommends a $30 refund.", channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '3 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['Shopify', 'Magento', 'BigCommerce', 'CRM', 'Analytics'], commonFeatures: commonFeaturesByVariant.growth, uniqueFeatures: uniqueFeaturesByIndustry.ecommerce.growth, keyAdvantage: 'Cuts review time by 80%, detects cart abandonment patterns', smartDecisions: 'Recommends refunds based on policy; flags fraud patterns', roi: 'Replaces ~$18k/month in junior agent salaries', bestFor: 'E-commerce SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations. 3 concurrent calls.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, humanAgentsReplaced: 5, avgHumanCostPerMonth: 28000, scenario: 'VIP customer threatens to cancel over repeated order issues. PARWA High reviews their history, detects a product flaw pattern, offers a $50 credit, and alerts your product team.', channels: [{ label: 'All Growth channels', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '5 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'Video screen-sharing', icon: <Video className="w-3.5 h-3.5" /> }], integrations: ['Shopify', 'Magento', 'BigCommerce', 'CRM', 'Analytics', 'Marketing'], commonFeatures: commonFeaturesByVariant.high, uniqueFeatures: uniqueFeaturesByIndustry.ecommerce.high, keyAdvantage: 'Approves returns up to $50, predicts churn, coordinates with marketing', roi: 'Replaces ~$28k/month in senior agent salaries', bestFor: 'E-commerce SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support. 5 calls + video.' },
  ],
  saas: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 14000, scenario: "A user calls at 2 AM asking 'Why is my API not working?' PARWA Starter answers instantly, checks system status, and creates a support ticket.", channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Slack', icon: <Hash className="w-3.5 h-3.5" /> }, { label: 'Discord', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Phone (2 at once)', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['GitHub', 'GitLab', 'Zendesk', 'Intercom'], commonFeatures: commonFeaturesByVariant.starter, uniqueFeatures: uniqueFeaturesByIndustry.saas.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'SaaS SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 18000, badge: 'Recommended', scenario: "User's API integration is failing. PARWA walks them through troubleshooting, determines it's a real bug, creates a bug report, and recommends a credit for downtime.", channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '3 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['GitHub', 'GitLab', 'Zendesk', 'Intercom', 'Jira', 'Slack'], commonFeatures: commonFeaturesByVariant.growth, uniqueFeatures: uniqueFeaturesByIndustry.saas.growth, keyAdvantage: 'Cuts review time by 80%, detects usage patterns', smartDecisions: 'Recommends account changes; flags security issues', roi: 'Replaces ~$18k/month in junior agent salaries', bestFor: 'SaaS SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations. 3 concurrent calls.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, humanAgentsReplaced: 5, avgHumanCostPerMonth: 28000, scenario: 'VIP customer threatens to cancel over repeated API issues. PARWA High reviews their usage, detects a service degradation pattern, offers a $50 credit, and alerts your engineering team.', channels: [{ label: 'All Growth channels', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '5 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'Video screen-sharing', icon: <Video className="w-3.5 h-3.5" /> }], integrations: ['GitHub', 'GitLab', 'Zendesk', 'Intercom', 'Jira', 'Slack', 'PagerDuty'], commonFeatures: commonFeaturesByVariant.high, uniqueFeatures: uniqueFeaturesByIndustry.saas.high, keyAdvantage: 'Approves account changes up to $50, churn prediction engine', roi: 'Replaces ~$28k/month in senior agent salaries', bestFor: 'SaaS SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support. 5 calls + video.' },
  ],
  logistics: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 14000, scenario: "A customer calls at 2 AM asking 'Where's my shipment?' PARWA Starter answers instantly, checks TMS, and texts them the tracking link.", channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Phone (2 at once)', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['TMS', 'WMS', 'Carrier APIs', 'AfterShip'], commonFeatures: commonFeaturesByVariant.starter, uniqueFeatures: uniqueFeaturesByIndustry.logistics.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'Logistics SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make decisions — only collects data.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 18000, badge: 'Recommended', scenario: "Customer's delivery is delayed. PARWA checks the tracking system, determines the issue, reroutes the package, and recommends a shipping credit.", channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '3 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['TMS', 'WMS', 'Carrier APIs', 'GPS Tracking', 'Google Maps'], commonFeatures: commonFeaturesByVariant.growth, uniqueFeatures: uniqueFeaturesByIndustry.logistics.growth, keyAdvantage: 'GPS tracking, driver coordination, route optimization', smartDecisions: 'Recommends routing changes; flags delivery exceptions', roi: 'Replaces ~$18k/month in junior coordinator salaries', bestFor: 'Logistics SMBs with 200–500 daily tickets', coreCapability: 'Everything Starter does + Intelligent Recommendations. 3 concurrent calls.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, humanAgentsReplaced: 5, avgHumanCostPerMonth: 28000, scenario: 'VIP customer threatens to cancel over repeated delivery issues. PARWA High reviews their shipping history, detects a carrier performance pattern, offers a $50 credit, and alerts your operations team.', channels: [{ label: 'All Growth channels', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '5 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'Video screen-sharing', icon: <Video className="w-3.5 h-3.5" /> }], integrations: ['TMS', 'WMS', 'Carrier APIs', 'GPS Tracking', 'Operations'], commonFeatures: commonFeaturesByVariant.high, uniqueFeatures: uniqueFeaturesByIndustry.logistics.high, keyAdvantage: 'POD management, hazmat protocol, freight damage claims', roi: 'Replaces ~$28k/month in senior coordinator salaries', bestFor: 'Logistics SMBs with 500+ daily tickets', coreCapability: 'VIP Handling, Strategic Intelligence, Video Support. 5 calls + video.' },
  ],
  healthcare: [
    { id: 'starter', name: 'PARWA Starter', tagline: '"The 24/7 Trainee"', monthlyPrice: 999, annualPrice: 799, ticketsPerMonth: 1000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 14000, scenario: "A patient calls at 2 AM asking 'Can I reschedule my appointment?' PARWA Starter checks the scheduling platform and reschedules instantly.", channels: [{ label: 'Email', icon: <Mail className="w-3.5 h-3.5" /> }, { label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> }, { label: 'Phone (2 at once)', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'SMS', icon: <MessageSquare className="w-3.5 h-3.5" /> }], integrations: ['Epic EHR (FHIR)', 'Scheduling platforms', 'Insurance portals'], commonFeatures: commonFeaturesByVariant.starter, uniqueFeatures: uniqueFeaturesByIndustry.healthcare.starter, roi: 'Replaces ~$14k/month in trainee salaries', bestFor: 'Healthcare SMBs with 50–200 daily tickets', coreLimitation: 'CANNOT make clinical decisions — only collects data. No PHI access.' },
    { id: 'growth', name: 'PARWA Growth', tagline: '"The Junior Agent"', monthlyPrice: 2499, annualPrice: 1999, ticketsPerMonth: 5000, humanAgentsReplaced: 4, avgHumanCostPerMonth: 18000, badge: 'Recommended', scenario: "A patient asks about their insurance coverage. PARWA Growth verifies the coverage type, checks the insurance portal, and provides the information while flagging any clinical keywords for human review.", channels: [{ label: 'All Starter + SMS & Voice', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '3 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }], integrations: ['Epic EHR (FHIR)', 'Scheduling platforms', 'Insurance portals', 'Billing portals'], commonFeatures: commonFeaturesByVariant.growth, uniqueFeatures: uniqueFeaturesByIndustry.healthcare.growth, keyAdvantage: 'HIPAA Safety Check, BAA compliance, insurance portal integration', smartDecisions: 'Detects clinical keywords → immediate escalation; verifies coverage', roi: 'Replaces ~$18k/month in junior staff salaries', bestFor: 'Healthcare SMBs with 200–500 daily tickets', coreCapability: 'HIPAA-compliant AI. 3 concurrent calls. No clinical decisions.' },
    { id: 'high', name: 'PARWA High', tagline: '"The Senior Agent"', monthlyPrice: 3999, annualPrice: 3199, ticketsPerMonth: 15000, humanAgentsReplaced: 5, avgHumanCostPerMonth: 28000, scenario: 'A patient mentions chest pain and medication dosage in the same message. PARWA High immediately detects the clinical keywords, pauses the conversation, and routes to a licensed clinician within seconds.', channels: [{ label: 'All Growth channels', icon: <Zap className="w-3.5 h-3.5" /> }, { label: '5 simultaneous calls', icon: <Phone className="w-3.5 h-3.5" /> }, { label: 'Video screen-sharing', icon: <Video className="w-3.5 h-3.5" /> }], integrations: ['Epic EHR (FHIR)', 'Scheduling', 'Insurance', 'Billing', 'Telehealth'], commonFeatures: commonFeaturesByVariant.high, uniqueFeatures: uniqueFeaturesByIndustry.healthcare.high, keyAdvantage: 'Full HIPAA/HITECH, clinical keyword detection, mental health escalation', roi: 'Replaces ~$28k/month in senior staff salaries', bestFor: 'Healthcare SMBs with 500+ daily tickets', coreCapability: 'HIPAA-compliant senior AI. 5 calls + video. Zero PHI in training.' },
  ],
};

// ─── Static Data ─────────────────────────────────────────────────────────────

const defaultPrimary = '#022C22';
const defaultAccent = '#10B981';
const defaultAccentRgb = '16,185,129';

const cancellationPoints = [
  { icon: CalendarClock, text: 'Cancel anytime — no long-term contracts' },
  { icon: CreditCard, text: 'No refunds once paid' },
  { icon: Info, text: 'Access continues until the end of your billing month' },
  { icon: XCircle, text: 'No free trials — start with confidence from day one' },
  { icon: X, text: 'Payment failure stops service immediately' },
];

const trustIndicators = [
  { icon: Bot, label: 'AI-Powered' },
  { icon: Zap, label: 'Instant Setup' },
  { icon: ShieldCheck, label: 'Enterprise Ready' },
  { icon: Sparkles, label: 'Continuous Learning' },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// ─── Page Component ─────────────────────────────────────────────────────────

export default function ModelsPage() {
  const { isAuthenticated } = useAuth();
  const [selectedIndustry, setSelectedIndustry] = useState<Industry | null>(null);
  const [isAnnual, setIsAnnual] = useState(false);
  const pricingRef = useRef<HTMLDivElement>(null);
  const [demoModalOpen, setDemoModalOpen] = useState(false);
  const [demoVariant, setDemoVariant] = useState<string>('');

  // Quantity state: { starter: 0, growth: 0, high: 0 }
  const [quantities, setQuantities] = useState<Record<VariantId, number>>({
    starter: 0,
    growth: 0,
    high: 0,
  });

  // ROI auto-population from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('parwa_roi_result');
      if (stored) {
        const roi = JSON.parse(stored);
        if (roi && roi.recommendedPlan) {
          const planMap: Record<string, VariantId> = {
            starter: 'starter',
            growth: 'growth',
            high: 'high',
          };
          const planId = planMap[roi.recommendedPlan?.toLowerCase()];
          if (planId) {
            setQuantities(prev => ({ ...prev, [planId]: 1 }));
          }
        }
      }
    } catch {
      // Silently fail — no ROI data available
    }
  }, []);

  const handleIndustryClick = (indId: Industry) => {
    const isActive = selectedIndustry === indId;
    setSelectedIndustry(isActive ? null : indId);
    // Reset quantities when switching industry
    if (!isActive) {
      setQuantities({ starter: 0, growth: 0, high: 0 });
      // Re-read ROI data for auto-population
      try {
        const stored = localStorage.getItem('parwa_roi_result');
        if (stored) {
          const roi = JSON.parse(stored);
          if (roi && roi.recommendedPlan) {
            const planMap: Record<string, VariantId> = {
              starter: 'starter',
              growth: 'growth',
              high: 'high',
            };
            const planId = planMap[roi.recommendedPlan?.toLowerCase()];
            if (planId) {
              setQuantities(prev => ({ ...prev, [planId]: 1 }));
            }
          }
        }
      } catch { /* ignore */ }
      setTimeout(() => {
        pricingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);
    }
  };

  const handleQuantityChange = (variantId: VariantId, newQty: number) => {
    setQuantities(prev => ({ ...prev, [variantId]: Math.max(0, Math.min(newQty, 10)) }));
  };

  const handleDemoClick = (variantName: string) => {
    setDemoVariant(variantName);
    setDemoModalOpen(true);
  };

  const activeIndustry = selectedIndustry ? industries.find(i => i.id === selectedIndustry)! : null;
  const primary = activeIndustry?.primary || defaultPrimary;
  const accent = activeIndustry?.accent || defaultAccent;
  const accentRgb = activeIndustry?.accentRgb || defaultAccentRgb;
  const currentVariants = selectedIndustry ? variantData[selectedIndustry] : null;

  // Computed totals
  const totalMonthly = currentVariants?.reduce((sum, v) => {
    const price = isAnnual ? v.annualPrice : v.monthlyPrice;
    return sum + price * (quantities[v.id] || 0);
  }, 0) || 0;

  const totalTickets = currentVariants?.reduce((sum, v) => {
    return sum + v.ticketsPerMonth * (quantities[v.id] || 0);
  }, 0) || 0;

  const totalHumanCostReplaced = currentVariants?.reduce((sum, v) => {
    return sum + v.avgHumanCostPerMonth * (quantities[v.id] || 0);
  }, 0) || 0;

  const totalAnnualSavings = currentVariants?.reduce((sum, v) => {
    return sum + (v.monthlyPrice - v.annualPrice) * (quantities[v.id] || 0);
  }, 0) || 0;

  const totalAgentsHired = Object.values(quantities).reduce((a, b) => a + b, 0);
  const hasSelection = totalAgentsHired > 0;

  return (
    <div
      className="min-h-screen flex flex-col transition-all duration-700"
      style={{ background: `linear-gradient(180deg, ${primary} 0%, ${hexToRgba(primary, 0.85)} 50%, ${primary} 100%)` }}
    >
      <NavigationBar />
      <main className="flex-grow relative">
        {/* Background blobs */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full blur-[150px] transition-colors duration-700" style={{ backgroundColor: `rgba(${accentRgb},0.08)` }} />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full blur-[120px] transition-colors duration-700" style={{ backgroundColor: `rgba(${accentRgb},0.06)` }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full blur-[200px] transition-colors duration-700" style={{ backgroundColor: `rgba(${accentRgb},0.04)` }} />
          {Array.from({ length: 15 }).map((_, i) => {
            const row = Math.floor(i / 5); const col = i % 5;
            return <div key={i} className="absolute w-1 h-1 rounded-full" style={{ left: `${(col + 0.5) * 20}%`, top: `${(row + 0.5) * 20}%`, backgroundColor: accent, animation: `jarvisDotPulse 3s ease-in-out infinite ${(i * 0.3) % 4}s`, opacity: 0 }} />;
          })}
        </div>

        {/* ══════════ HERO ══════════ */}
        <section className="relative py-16 sm:py-20 md:py-28">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border mb-6 backdrop-blur-sm transition-colors duration-700" style={{ backgroundColor: `rgba(${accentRgb},0.1)`, borderColor: `rgba(${accentRgb},0.3)` }}>
              <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: accent }} />
              <span className="text-sm font-medium transition-colors duration-700" style={{ color: accent }}>AI-Powered Support Agents</span>
            </div>
            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-white mb-4 sm:mb-6">
              Meet the <span className="bg-clip-text text-transparent transition-all duration-700" style={{ backgroundImage: `linear-gradient(to right, rgba(${accentRgb},0.9), ${accent}, rgba(${accentRgb},0.8))` }}>PARWA</span> AI Family
            </h1>
            <p className="text-base sm:text-lg max-w-2xl mx-auto px-4 transition-colors duration-700" style={{ color: 'rgba(255,255,255,0.5)' }}>
              {selectedIndustry
                ? activeIndustry!.heroText
                : 'Three intelligent AI agents, each designed for a different stage of your business growth. Choose your industry to see tailored solutions.'}
            </p>
            {/* Trust indicators */}
            <div className="flex flex-wrap items-center justify-center gap-3 sm:gap-4 mt-8">
              {trustIndicators.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full border backdrop-blur-sm transition-colors duration-500" style={{ backgroundColor: `rgba(${accentRgb},0.1)`, borderColor: `rgba(${accentRgb},0.3)`, color: accent }}>
                    <Icon className="w-3.5 h-3.5" style={{ color: accent }} />
                    <span className="text-xs sm:text-sm font-medium" style={{ color: 'rgba(255,255,255,0.7)' }}>{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════ INDUSTRY SELECTOR ══════════ */}
        <section className="relative pb-8 sm:pb-12">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-center text-lg sm:text-xl font-semibold text-white mb-6 sm:mb-8">Select Your Industry</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
              {industries.map((ind) => {
                const isActive = selectedIndustry === ind.id;
                return (
                  <button key={ind.id} onClick={() => { handleIndustryClick(ind.id); }}
                    className="relative rounded-2xl p-6 sm:p-8 text-left transition-all duration-500 hover:-translate-y-1 group cursor-pointer"
                    style={{
                      background: isActive ? `linear-gradient(135deg, rgba(${ind.accentRgb},0.15) 0%, rgba(${ind.accentRgb},0.05) 100%)` : 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
                      border: isActive ? `2px solid rgba(${ind.accentRgb},0.6)` : '2px solid rgba(255,255,255,0.1)',
                      boxShadow: isActive ? `0 20px 50px rgba(${ind.accentRgb},0.15)` : '0 20px 50px rgba(0,0,0,0.2)',
                      backdropFilter: 'blur(20px)',
                    }}>
                    <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-24 h-1 rounded-full transition-all duration-500 group-hover:w-3/4" style={{ backgroundColor: ind.accent, opacity: isActive ? 1 : 0 }} />
                    <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-all duration-500 group-hover:scale-110" style={{ backgroundColor: `rgba(${ind.accentRgb},${isActive ? 0.2 : 0.1})`, border: `1px solid rgba(${ind.accentRgb},${isActive ? 0.3 : 0.15})`, color: ind.accent }}>
                      {ind.icon}
                    </div>
                    <h3 className="text-lg sm:text-xl font-bold text-white mb-1">{ind.label}</h3>
                    <p className="text-sm" style={{ color: 'rgba(255,255,255,0.4)' }}>{ind.description}</p>
                    <div className="flex gap-1.5 mt-3">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ind.primary }} />
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ind.accent }} />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        {/* ══════════ PRICING CONTENT ══════════ */}
        <div ref={pricingRef} className="scroll-mt-4" />
        {selectedIndustry && currentVariants && (
          <>
            {/* ── Annual Toggle ── */}
            <section className="relative pb-8 sm:pb-10">
              <div className="flex justify-center">
                <div className="inline-flex items-center gap-3 px-5 py-2.5 rounded-full border backdrop-blur-sm" style={{ backgroundColor: `rgba(${accentRgb},0.08)`, borderColor: `rgba(${accentRgb},0.25)` }}>
                  <span className={`text-sm font-medium transition-colors duration-300 ${!isAnnual ? 'text-white' : 'text-white/40'}`}>Monthly</span>
                  <button onClick={() => setIsAnnual(!isAnnual)} className="relative w-12 h-7 rounded-full transition-colors duration-300" style={{ background: isAnnual ? `linear-gradient(to right, ${accent}, rgba(${accentRgb},0.8))` : 'rgba(255,255,255,0.15)' }} aria-label="Toggle annual billing" role="switch" aria-checked={isAnnual}>
                    <div className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 ${isAnnual ? 'translate-x-5' : 'translate-x-0'}`} />
                  </button>
                  <span className={`text-sm font-medium transition-colors duration-300 ${isAnnual ? 'text-white' : 'text-white/40'}`}>Annual</span>
                  {isAnnual && (
                    <span className="ml-1 px-2.5 py-0.5 rounded-full border text-xs font-bold" style={{ backgroundColor: `rgba(${accentRgb},0.15)`, borderColor: `rgba(${accentRgb},0.3)`, color: accent }}>Save 20%</span>
                  )}
                </div>
              </div>
            </section>

            {/* ── 3 Pricing Cards ── */}
            <section className="relative pb-12 sm:pb-16">
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-8 sm:mb-10">
                  <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                    <span className="bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, rgba(${accentRgb},0.9), ${accent})` }}>
                      {activeIndustry!.label}
                    </span>{' '}Pricing & Plans
                  </h2>
                  <p className="text-sm sm:text-base" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {isAuthenticated
                      ? 'Select the variants you want to hire — adjust quantities below'
                      : 'Choose the right PARWA tier for your ' + activeIndustry!.label.toLowerCase() + ' business'}
                  </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
                  {currentVariants.map((variant, index) => {
                    const isRecommended = variant.badge === 'Recommended';
                    const price = isAnnual ? variant.annualPrice : variant.monthlyPrice;
                    const annualSavings = variant.monthlyPrice - variant.annualPrice;
                    const qty = quantities[variant.id] || 0;
                    const subtotal = price * qty;
                    const isActive = qty > 0;
                    const savingsVsHuman = variant.avgHumanCostPerMonth - price;

                    return (
                      <div key={variant.id} className={`relative rounded-2xl border-2 p-6 sm:p-8 transition-all duration-500 backdrop-blur-sm group ${isActive ? 'hover:-translate-y-2' : 'hover:-translate-y-1'}`}
                        style={{
                          border: isActive
                            ? `2px solid ${accent}`
                            : isRecommended
                              ? `2px solid rgba(${accentRgb},0.4)`
                              : '2px solid rgba(255,255,255,0.1)',
                          background: isActive
                            ? `linear-gradient(135deg, rgba(${accentRgb},0.12) 0%, rgba(${accentRgb},0.04) 100%)`
                            : isRecommended
                              ? `linear-gradient(135deg, rgba(${accentRgb},0.06) 0%, rgba(255,255,255,0.02) 100%)`
                              : 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
                          boxShadow: isActive
                            ? `0 25px 60px rgba(0,0,0,0.3), 0 0 100px rgba(${accentRgb},0.12)`
                            : isRecommended
                              ? `0 25px 60px rgba(0,0,0,0.3), 0 0 80px rgba(${accentRgb},0.06)`
                              : '0 25px 50px rgba(0,0,0,0.2)',
                          transitionDelay: `${index * 100}ms`,
                        }}>
                        {/* Glow */}
                        <div className="absolute -top-16 -right-16 w-32 h-32 rounded-full blur-[60px] pointer-events-none transition-opacity duration-500" style={{ backgroundColor: `rgba(${accentRgb},${isActive ? 0.15 : 0.05})`, opacity: isActive ? 1 : 0 }} />

                        {/* Recommended Badge */}
                        {isRecommended && (
                          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
                            <span className="inline-flex items-center gap-1 px-4 py-1.5 text-xs font-bold bg-gradient-to-r from-amber-400 to-yellow-400 text-gray-900 rounded-full shadow-lg shadow-amber-400/30">
                              <Star className="w-3 h-3" fill="currentColor" /> Recommended
                            </span>
                          </div>
                        )}

                        {/* Hired Badge */}
                        {isActive && (
                          <div className="absolute -top-3.5 right-4 z-10">
                            <span className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-bold rounded-full" style={{ backgroundColor: `rgba(${accentRgb},0.2)`, color: accent, border: `1px solid rgba(${accentRgb},0.3)` }}>
                              <Check className="w-3 h-3" /> Hired x{qty}
                            </span>
                          </div>
                        )}

                        {/* Name */}
                        <div className="mb-4 mt-1">
                          <h3 className="text-2xl sm:text-3xl font-extrabold text-white mb-1 tracking-tight">{variant.name}</h3>
                          <p className="text-sm font-medium" style={{ color: accent }}>{variant.tagline}</p>
                        </div>

                        {/* Price */}
                        <div className="mb-5 pb-5 border-b" style={{ borderColor: 'rgba(255,255,255,0.1)' }}>
                          <div className="flex items-baseline gap-1">
                            <span className="text-4xl sm:text-5xl font-black" style={{ color: isActive ? accent : 'white' }}>${price.toLocaleString()}</span>
                            <span className="text-sm font-medium" style={{ color: 'rgba(255,255,255,0.3)' }}>/month</span>
                          </div>
                          {isAnnual && (
                            <p className="text-xs mt-1.5" style={{ color: accent }}>Billed annually — save ${annualSavings}/mo</p>
                          )}
                        </div>

                        {/* ── Cost Replacement Box (Master Stroke) ── */}
                        <div className="mb-4 px-3 py-3 rounded-lg" style={{ backgroundColor: `rgba(${accentRgb},0.1)`, border: `1px solid rgba(${accentRgb},0.2)` }}>
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Users className="w-4 h-4" style={{ color: accent }} />
                              <span className="text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.7)' }}>Replaces</span>
                            </div>
                            <span className="text-xs font-bold" style={{ color: accent }}>{variant.humanAgentsReplaced} human agents</span>
                          </div>
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <DollarSign className="w-4 h-4" style={{ color: accent }} />
                              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>Human team cost</span>
                            </div>
                            <span className="text-xs font-bold text-red-400 line-through">${variant.avgHumanCostPerMonth.toLocaleString()}/mo</span>
                          </div>
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Zap className="w-4 h-4" style={{ color: accent }} />
                              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>PARWA cost</span>
                            </div>
                            <span className="text-sm font-black" style={{ color: accent }}>${price.toLocaleString()}/mo</span>
                          </div>
                          <div className="h-px my-2" style={{ backgroundColor: `rgba(${accentRgb},0.2)` }} />
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold" style={{ color: 'rgba(255,255,255,0.8)' }}>You save every month</span>
                            <span className="text-sm font-black" style={{ color: '#34D399' }}>${savingsVsHuman.toLocaleString()}</span>
                          </div>
                          {qty > 1 && (
                            <div className="mt-2 pt-2 border-t" style={{ borderColor: `rgba(${accentRgb},0.15)` }}>
                              <div className="flex items-center justify-between">
                                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.5)' }}>x{qty} agents subtotal</span>
                                <span className="text-sm font-bold" style={{ color: accent }}>${subtotal.toLocaleString()}/mo</span>
                              </div>
                              <div className="flex items-center justify-between mt-1">
                                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>vs {variant.humanAgentsReplaced * qty} humans</span>
                                <span className="text-xs font-bold text-red-400 line-through">${(variant.avgHumanCostPerMonth * qty).toLocaleString()}/mo</span>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Core limitation / capability */}
                        {variant.coreLimitation && (
                          <div className="flex items-start gap-2 mb-4 px-3 py-2 rounded-lg" style={{ backgroundColor: `rgba(${accentRgb},0.08)` }}>
                            <Shield className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: accent }} />
                            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)' }}><strong style={{ color: accent }}>Core limitation:</strong> {variant.coreLimitation}</p>
                          </div>
                        )}
                        {variant.coreCapability && (
                          <div className="flex items-start gap-2 mb-4 px-3 py-2 rounded-lg" style={{ backgroundColor: `rgba(${accentRgb},0.08)` }}>
                            <Zap className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: accent }} />
                            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)' }}><strong style={{ color: accent }}>Core capability:</strong> {variant.coreCapability}</p>
                          </div>
                        )}

                        {/* Scenario — Real Story */}
                        <div className="mb-4 relative overflow-hidden rounded-xl" style={{ backgroundColor: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                          <div className="absolute top-0 left-0 w-1 h-full rounded-l-xl" style={{ background: `linear-gradient(180deg, ${accent}, rgba(${accentRgb},0.3))` }} />
                          <div className="pl-4 pr-3 py-3">
                            <p className="text-[11px] uppercase tracking-widest font-bold mb-1.5" style={{ color: accent }}>Real Scenario</p>
                            <p className="text-xs italic leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>&ldquo;{variant.scenario}&rdquo;</p>
                          </div>
                        </div>

                        {/* ── Common Features ── */}
                        <div className="mb-4">
                          <p className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'rgba(255,255,255,0.3)' }}>All Plans Include</p>
                          <ul className="space-y-2.5">
                            {variant.commonFeatures.map((feature, i) => (
                              <li key={i} className="flex items-start gap-3">
                                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: `rgba(${accentRgb},0.15)` }}>
                                  <Check className="w-3 h-3" style={{ color: accent }} strokeWidth={3} />
                                </div>
                                <span className="text-sm" style={{ color: 'rgba(255,255,255,0.7)' }}>{feature}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* ── Industry-Specific Unique Features ── */}
                        <div className="mb-4">
                          <div className="flex items-center gap-2 mb-3">
                            <Sparkles className="w-4 h-4" style={{ color: accent }} />
                            <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: accent }}>{activeIndustry!.label}-Specific</p>
                          </div>
                          <ul className="space-y-2.5">
                            {variant.uniqueFeatures.map((feature, i) => (
                              <li key={i} className="flex items-start gap-3">
                                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: `rgba(${accentRgb},0.2)` }}>
                                  <Sparkles className="w-3 h-3" style={{ color: accent }} />
                                </div>
                                <span className="text-sm font-medium" style={{ color: 'rgba(255,255,255,0.85)' }}>{feature}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Key Advantage */}
                        {variant.keyAdvantage && (
                          <div className="mb-3 px-3 py-2.5 rounded-lg" style={{ backgroundColor: `rgba(${accentRgb},0.08)`, border: `1px solid rgba(${accentRgb},0.15)` }}>
                            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.7)' }}>{variant.keyAdvantage}</p>
                          </div>
                        )}

                        {/* ROI + Best For */}
                        <div className="mb-4 px-3 py-2.5 rounded-lg" style={{ backgroundColor: `rgba(${accentRgb},0.1)`, border: `1px solid rgba(${accentRgb},0.2)` }}>
                          <div className="flex items-center gap-2 mb-1">
                            <TrendingUp className="w-4 h-4 flex-shrink-0" style={{ color: accent }} />
                            <span className="text-sm font-medium" style={{ color: accent }}>{variant.roi}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Ticket className="w-3 h-3" style={{ color: `rgba(${accentRgb},0.6)` }} />
                            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Best for: {variant.bestFor}</p>
                          </div>
                        </div>

                        {/* ── Quantity Selector (-1 / +) ── */}
                        <div className="mb-3">
                          <div className="flex items-center justify-between px-1 mb-2">
                            <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(255,255,255,0.4)' }}>
                              {isAuthenticated ? 'Hire Quantity' : 'Quantity'}
                            </span>
                            {qty > 0 && (
                              <span className="text-xs font-bold" style={{ color: accent }}>
                                ${subtotal.toLocaleString()}/mo total
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <button
                              onClick={() => handleQuantityChange(variant.id, qty - 1)}
                              disabled={qty <= 0}
                              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 active:scale-90 ${
                                qty > 0
                                  ? 'text-white/80 hover:text-white'
                                  : 'text-white/20 cursor-not-allowed'
                              }`}
                              style={{
                                background: qty > 0 ? `rgba(${accentRgb},0.2)` : 'rgba(255,255,255,0.05)',
                                border: qty > 0 ? `1px solid rgba(${accentRgb},0.3)` : '1px solid rgba(255,255,255,0.1)',
                              }}
                              aria-label="Decrease quantity"
                            >
                              <Minus className="w-4 h-4" />
                            </button>
                            <div
                              className="flex-1 h-10 rounded-xl flex items-center justify-center font-bold text-lg tabular-nums transition-all duration-200"
                              style={{
                                background: isActive
                                  ? `rgba(${accentRgb},0.15)`
                                  : 'rgba(255,255,255,0.05)',
                                border: isActive
                                  ? `1px solid rgba(${accentRgb},0.3)`
                                  : '1px solid rgba(255,255,255,0.1)',
                                color: isActive ? accent : 'rgba(255,255,255,0.5)',
                              }}
                            >
                              {qty}
                            </div>
                            <button
                              onClick={() => handleQuantityChange(variant.id, qty + 1)}
                              disabled={qty >= 10}
                              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 active:scale-90 ${
                                qty < 10
                                  ? 'text-white/80 hover:text-white'
                                  : 'text-white/20 cursor-not-allowed'
                              }`}
                              style={{
                                background: qty < 10 ? `rgba(${accentRgb},0.2)` : 'rgba(255,255,255,0.05)',
                                border: qty < 10 ? `1px solid rgba(${accentRgb},0.3)` : '1px solid rgba(255,255,255,0.1)',
                              }}
                              aria-label="Increase quantity"
                            >
                              <Plus className="w-4 h-4" />
                            </button>
                          </div>
                        </div>

                        {/* ══════════ EXPERIENCE BEFORE YOU HIRE ══════════ */}
                        <div className="mt-5 -mx-2 px-4 py-4 rounded-2xl relative overflow-hidden" style={{
                          background: `linear-gradient(135deg, rgba(${accentRgb},0.06) 0%, rgba(${accentRgb},0.02) 100%)`,
                          border: `1px dashed rgba(${accentRgb},0.25)`,
                        }}>
                          {/* Decorative corner accents */}
                          <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 rounded-tl-2xl" style={{ borderColor: accent }} />
                          <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 rounded-tr-2xl" style={{ borderColor: accent }} />
                          <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 rounded-bl-2xl" style={{ borderColor: accent }} />
                          <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 rounded-br-2xl" style={{ borderColor: accent }} />

                          {/* Section header */}
                          <div className="text-center mb-4">
                            <p className="text-[10px] uppercase tracking-[0.2em] font-black mb-1" style={{ color: accent }}>Experience Before You Hire</p>
                            <p className="text-[11px]" style={{ color: 'rgba(255,255,255,0.35)' }}>Don't take our word for it — try it yourself</p>
                          </div>

                          {/* Call Demo Button — THE star button */}
                          <button
                            onClick={() => handleDemoClick(variant.name)}
                            className="group/demo w-full relative flex items-center gap-3 py-3.5 px-4 rounded-xl text-sm font-bold transition-all duration-500 hover:-translate-y-1 hover:shadow-2xl overflow-hidden mb-2.5"
                            style={{
                              background: `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.7) 100%)`,
                              color: primary,
                              boxShadow: `0 4px 20px rgba(${accentRgb},0.25), 0 0 40px rgba(${accentRgb},0.08)`,
                            }}
                            title="This agent will call you — talk to it, test it, see how it handles your clients"
                          >
                            <div className="absolute inset-0 opacity-0 group-hover/demo:opacity-100 transition-opacity duration-500" style={{ background: `linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 60%)` }} />
                            <div className="absolute top-0 right-0 px-2.5 py-1 rounded-bl-xl rounded-tr-[9px]">
                              <span className="text-[9px] font-black uppercase tracking-wider" style={{ color: primary, opacity: 0.7 }}>$1</span>
                            </div>
                            <div className="relative flex items-center gap-3 w-full">
                              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: 'rgba(0,0,0,0.15)' }}>
                                <Phone className="w-5 h-5" />
                              </div>
                              <div className="text-left flex-1">
                                <span className="block text-sm font-black leading-tight">Book Instant Call Demo</span>
                                <span className="block text-[11px] font-medium mt-0.5" style={{ opacity: 0.8 }}>This agent will call you — talk to it, test it live</span>
                              </div>
                            </div>
                          </button>

                          {/* Chat Demo Button — FREE */}
                          <button
                            onClick={() => { /* Open chat — chat widget is always visible */ }}
                            className="group/chat w-full relative flex items-center gap-3 py-3 px-4 rounded-xl text-sm font-bold transition-all duration-300 hover:-translate-y-0.5 overflow-hidden"
                            style={{
                              background: 'rgba(255,255,255,0.04)',
                              border: `1px solid rgba(255,255,255,0.12)`,
                              color: 'rgba(255,255,255,0.9)',
                            }}
                            title="Free live chat — see how Parwa responds to real queries"
                          >
                            <div className="absolute inset-0 opacity-0 group-hover/chat:opacity-100 transition-opacity duration-300" style={{ background: 'rgba(255,255,255,0.06)' }} />
                            <div className="absolute top-0 right-0 px-2.5 py-1 rounded-bl-xl rounded-tr-[9px]" style={{ background: 'rgba(52,211,153,0.15)' }}>
                              <span className="text-[9px] font-black uppercase tracking-wider text-emerald-400">Free</span>
                            </div>
                            <div className="relative flex items-center gap-3 w-full">
                              <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: 'rgba(255,255,255,0.06)' }}>
                                <MessageSquare className="w-5 h-5" style={{ color: accent }} />
                              </div>
                              <div className="text-left flex-1">
                                <span className="block text-sm font-bold leading-tight">Try Live Chat — Free</span>
                                <span className="block text-[11px] font-medium mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>Chat now — see how Parwa handles your clients' queries</span>
                              </div>
                            </div>
                          </button>

                          <p className="text-center text-[10px] mt-3 italic" style={{ color: 'rgba(255,255,255,0.25)' }}>Both demos show exactly how Parwa works when hired by you</p>
                        </div>

                        {/* ── Main CTA ── */}
                        {isAuthenticated ? (
                          <div
                            className="relative flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500 no-underline overflow-hidden"
                            style={{
                              background: isActive
                                ? `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.8) 100%)`
                                : 'linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.04) 100%)',
                              color: isActive ? primary : 'rgba(255,255,255,0.5)',
                              border: isActive ? 'none' : '1px solid rgba(255,255,255,0.1)',
                              boxShadow: isActive ? `0 8px 24px rgba(${accentRgb},0.3)` : 'none',
                            }}
                          >
                            {isActive && <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, transparent 0%, rgba(255,255,255,0.1) 100%)' }} />}
                            <div className="relative flex items-center gap-2">
                              {isActive ? (
                                <>
                                  <Check className="w-4 h-4" />
                                  {qty} {qty === 1 ? 'Agent' : 'Agents'} Hired
                                </>
                              ) : (
                                'Select to Hire'
                              )}
                            </div>
                          </div>
                        ) : (
                          <Link href="/signup" className="group relative flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500 no-underline hover:-translate-y-0.5 overflow-hidden"
                            style={{ background: `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.85) 100%)`, color: primary, boxShadow: `0 8px 24px rgba(${accentRgb},0.3)` }}>
                            <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 100%)' }} />
                            <div className="relative flex items-center gap-2">Get Started <ArrowRight className="w-4 h-4" /></div>
                          </Link>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* ── Total Summary (when quantities > 0) ── */}
            {hasSelection && (
              <section className="relative pb-12 sm:pb-16">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                  <div className="rounded-2xl p-6 sm:p-8" style={{
                    background: `linear-gradient(135deg, rgba(${accentRgb},0.1) 0%, rgba(${accentRgb},0.03) 100%)`,
                    border: `1px solid rgba(${accentRgb},0.3)`,
                    boxShadow: `0 25px 60px rgba(0,0,0,0.3), 0 0 80px rgba(${accentRgb},0.08)`,
                  }}>
                    <h3 className="text-lg sm:text-xl font-bold text-white mb-5 flex items-center gap-2">
                      <BarChart3 className="w-5 h-5" style={{ color: accent }} />
                      Your {activeIndustry!.label} Hiring Summary
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                      {/* Agents */}
                      <div className="px-4 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                        <div className="flex items-center gap-2 mb-1">
                          <Bot className="w-4 h-4" style={{ color: accent }} />
                          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>AI Agents</span>
                        </div>
                        <span className="text-xl font-black text-white">{totalAgentsHired}</span>
                      </div>
                      {/* Tickets */}
                      <div className="px-4 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                        <div className="flex items-center gap-2 mb-1">
                          <Ticket className="w-4 h-4" style={{ color: accent }} />
                          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Tickets/mo</span>
                        </div>
                        <span className="text-xl font-black text-white">{totalTickets.toLocaleString()}</span>
                      </div>
                      {/* Monthly Cost */}
                      <div className="px-4 py-3 rounded-xl" style={{ background: `rgba(${accentRgb},0.08)`, border: `1px solid rgba(${accentRgb},0.2)` }}>
                        <div className="flex items-center gap-2 mb-1">
                          <DollarSign className="w-4 h-4" style={{ color: accent }} />
                          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>Monthly Cost</span>
                        </div>
                        <span className="text-xl font-black" style={{ color: accent }}>${totalMonthly.toLocaleString()}</span>
                      </div>
                      {/* Human Cost Replaced */}
                      <div className="px-4 py-3 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                        <div className="flex items-center gap-2 mb-1">
                          <Users className="w-4 h-4" style={{ color: '#34D399' }} />
                          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>vs Human Cost</span>
                        </div>
                        <span className="text-sm font-bold text-red-400 line-through">${totalHumanCostReplaced.toLocaleString()}</span>
                        <span className="block text-xs font-bold text-emerald-400">Save ${(totalHumanCostReplaced - totalMonthly).toLocaleString()}/mo</span>
                      </div>
                    </div>

                    {/* Breakdown */}
                    <div className="space-y-2 mb-5">
                      {currentVariants.filter(v => quantities[v.id] > 0).map(v => {
                        const price = isAnnual ? v.annualPrice : v.monthlyPrice;
                        return (
                          <div key={v.id} className="flex items-center justify-between px-4 py-2.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: accent }} />
                              <span className="text-sm font-medium text-white">{v.name}</span>
                              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `rgba(${accentRgb},0.15)`, color: accent }}>x{quantities[v.id]}</span>
                            </div>
                            <span className="text-sm font-bold" style={{ color: accent }}>${(price * quantities[v.id]).toLocaleString()}/mo</span>
                          </div>
                        );
                      })}
                    </div>

                    {isAnnual && totalAnnualSavings > 0 && (
                      <div className="p-3 rounded-lg mb-4" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)' }}>
                        <p className="text-xs sm:text-sm text-amber-300 font-medium">
                          <span className="text-amber-400 font-bold">2 months free</span> with annual plan — save{' '}
                          <span className="text-amber-400 font-bold">${totalAnnualSavings.toLocaleString()}/year</span>
                        </p>
                      </div>
                    )}

                    {/* CTA */}
                    {isAuthenticated ? (
                      <div className="flex gap-3">
                        <button
                          onClick={() => setDemoModalOpen(true)}
                          className="group/btn flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg overflow-hidden relative"
                          style={{ background: `linear-gradient(135deg, rgba(${accentRgb},0.2) 0%, rgba(${accentRgb},0.08) 100%)`, border: `1px solid rgba(${accentRgb},0.4)`, color: accent }}
                        >
                          <div className="absolute inset-0 opacity-0 group-hover/btn:opacity-100 transition-opacity duration-300" style={{ background: `linear-gradient(135deg, rgba(${accentRgb},0.3) 0%, rgba(${accentRgb},0.15) 100%)` }} />
                          <div className="relative flex items-center gap-2">
                            <Calendar className="w-4 h-4" />
                            Book Instant Demo — Just $1
                          </div>
                        </button>
                        <div
                          className="group/cfm flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold transition-all duration-300 overflow-hidden relative"
                          style={{ background: `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.85) 100%)`, color: primary, boxShadow: `0 8px 24px rgba(${accentRgb},0.3)` }}
                        >
                          <div className="absolute inset-0 opacity-0 group-hover/cfm:opacity-100 transition-opacity duration-300" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 100%)' }} />
                          <div className="relative flex items-center gap-2">
                            <Check className="w-4 h-4" />
                            Confirm ${totalMonthly.toLocaleString()}/mo
                          </div>
                        </div>
                      </div>
                    ) : (
                      <Link href="/signup" className="group relative flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-sm font-bold transition-all duration-500 no-underline hover:-translate-y-0.5 overflow-hidden"
                        style={{ background: `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.85) 100%)`, color: primary, boxShadow: `0 8px 24px rgba(${accentRgb},0.3)` }}>
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 100%)' }} />
                        <div className="relative flex items-center gap-2">Sign Up & Hire Now <ArrowRight className="w-4 h-4" /></div>
                      </Link>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* ── Anti-Arbitrage Comparison ── */}
            <section className="relative pb-12 sm:pb-16">
              <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-8 sm:mb-10">
                  <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                    The Real <span className="bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, rgba(${accentRgb},0.9), ${accent})` }}>Cost Comparison</span>
                  </h2>
                  <p className="text-sm sm:text-base" style={{ color: 'rgba(255,255,255,0.4)' }}>Why buying two Starters costs more than you think — and why Growth is the smarter choice.</p>
                </div>
                <AntiArbitrageMatrix />
              </div>
            </section>

            {/* ── Cancellation Policy ── */}
            <section className="relative pb-12 sm:pb-16">
              <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-8 sm:mb-10">
                  <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-white mb-2">
                    Cancellation <span className="bg-clip-text text-transparent" style={{ backgroundImage: `linear-gradient(to right, rgba(${accentRgb},0.9), ${accent})` }}>Policy</span>
                  </h2>
                  <p className="text-sm sm:text-base" style={{ color: 'rgba(255,255,255,0.4)' }}>Simple, fair, and transparent — just like our pricing.</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {cancellationPoints.map((point) => {
                    const Icon = point.icon;
                    return (
                      <div key={point.text} className="flex items-start gap-3 p-4 rounded-xl border bg-white/5 backdrop-blur-sm hover:border-white/20 transition-all duration-300" style={{ borderColor: `rgba(${accentRgb},0.2)` }}>
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `rgba(${accentRgb},0.1)` }}>
                          <Icon className="w-4.5 h-4.5" style={{ color: accent }} />
                        </div>
                        <p className="text-sm leading-relaxed" style={{ color: 'rgba(255,255,255,0.5)' }}>{point.text}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* ── Final CTA ── */}
            <section className="px-4 sm:px-6 lg:px-8 pb-16 sm:pb-24">
              <div className="max-w-3xl mx-auto text-center">
                <div className="rounded-2xl border p-8 sm:p-12" style={{ borderColor: `rgba(${accentRgb},0.2)`, backgroundColor: `rgba(${accentRgb},0.05)`, backdropFilter: 'blur(20px)' }}>
                  <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
                    Ready to automate your {activeIndustry!.label.toLowerCase()} support?
                  </h2>
                  <p className="text-sm sm:text-base mb-8 max-w-lg mx-auto leading-relaxed" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    Sign up and join thousands of businesses using PARWA to handle tickets faster, learn continuously, and scale effortlessly.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <button
                      onClick={() => setDemoModalOpen(true)}
                      className="group/final relative inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-bold transition-all duration-500 hover:-translate-y-0.5 hover:shadow-xl overflow-hidden"
                      style={{ background: `linear-gradient(135deg, rgba(${accentRgb},0.2) 0%, rgba(${accentRgb},0.06) 100%)`, border: `1px solid rgba(${accentRgb},0.35)`, color: accent, boxShadow: `0 4px 15px rgba(${accentRgb},0.1)` }}
                    >
                      <div className="absolute inset-0 opacity-0 group-hover/final:opacity-100 transition-opacity duration-300" style={{ background: `linear-gradient(135deg, rgba(${accentRgb},0.3) 0%, rgba(${accentRgb},0.15) 100%)` }} />
                      <div className="relative flex items-center gap-2">
                        <Calendar className="w-5 h-5" />
                        Book Instant Demo — $1
                      </div>
                    </button>
                    <Link href="/signup" className="group relative inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-bold transition-all duration-500 hover:-translate-y-0.5 no-underline overflow-hidden"
                      style={{ background: `linear-gradient(135deg, ${accent} 0%, rgba(${accentRgb},0.85) 100%)`, color: primary, boxShadow: `0 8px 30px rgba(${accentRgb},0.3)` }}>
                      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: 'linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 100%)' }} />
                      <div className="relative flex items-center gap-2">
                        {isAuthenticated ? 'Hire Now' : 'Get Started'} <ArrowRight className="w-5 h-5" />
                      </div>
                    </Link>
                  </div>
                </div>
              </div>
            </section>
          </>
        )}
      </main>
      <Footer />

      {/* ── Floating Widgets ── */}
      <ChatWidget
        industry={activeIndustry?.label}
        variant={currentVariants && quantities.growth > 0 ? 'Growth' : undefined}
      />
      <BookDemoModal
        isOpen={demoModalOpen}
        onClose={() => setDemoModalOpen(false)}
        preSelectedIndustry={activeIndustry?.label}
      />
    </div>
  );
}
