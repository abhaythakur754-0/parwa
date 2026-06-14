'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  Sparkles, Zap, Shield, MessageSquare, BarChart3, Globe,
  ChevronRight, ArrowRight, Star, Check, Menu, X,
  Headphones, Bot, Clock, Users, TrendingUp, Lock
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const features = [
  {
    icon: Bot,
    title: 'AI-Powered Support',
    description: 'Intelligent chatbots that understand context, resolve tickets automatically, and learn from every interaction to improve over time.',
  },
  {
    icon: Zap,
    title: 'Multi-Variant Billing',
    description: 'Flexible Mini, Standard, and High plans with real-time usage tracking, overage protection, and smart cost calculators.',
  },
  {
    icon: Shield,
    title: 'Enterprise Security',
    description: 'AES-256-GCM encryption for credentials, circuit breakers for reliability, and complete audit trails for compliance.',
  },
  {
    icon: Globe,
    title: '35+ Integrations',
    description: 'Connect with Zendesk, Shopify, Slack, Salesforce, HubSpot, Stripe, and 30+ more tools across e-commerce, SaaS, and logistics.',
  },
  {
    icon: BarChart3,
    title: 'Smart Analytics',
    description: 'Real-time dashboards with usage metrics, cost projections, SLA tracking, and AI-powered recommendations for optimization.',
  },
  {
    icon: MessageSquare,
    title: 'Knowledge Base',
    description: 'Build and manage a powerful knowledge base with document uploads, FAQ management, and AI-powered search and suggestions.',
  },
];

const plans = [
  {
    name: 'Mini',
    price: 29,
    description: 'For small teams getting started',
    features: ['5,000 tickets/month', '3 integrations', 'Basic AI chatbot', 'Email support', '1 knowledge base'],
    popular: false,
    variant: 'mini' as const,
  },
  {
    name: 'Standard',
    price: 79,
    description: 'For growing businesses',
    features: ['25,000 tickets/month', '15 integrations', 'Advanced AI + training', 'Priority support', '5 knowledge bases', 'Custom workflows', 'SLA management'],
    popular: true,
    variant: 'parwa' as const,
  },
  {
    name: 'High',
    price: 199,
    description: 'For enterprise scale',
    features: ['100,000 tickets/month', '35+ integrations', 'Full AI suite + custom models', '24/7 dedicated support', 'Unlimited knowledge bases', 'Advanced analytics', 'Custom connectors', 'Audit trail & compliance'],
    popular: false,
    variant: 'high' as const,
  },
];

const stats = [
  { value: '10M+', label: 'Tickets Resolved' },
  { value: '99.9%', label: 'Uptime SLA' },
  { value: '35+', label: 'Integrations' },
  { value: '<2s', label: 'Avg Response Time' },
];

const testimonials = [
  {
    name: 'Sarah Chen',
    role: 'Head of Support',
    company: 'ShopFlow',
    text: 'PARWA reduced our ticket resolution time by 65%. The AI actually understands context, not just keywords.',
    stars: 5,
  },
  {
    name: 'Marcus Rivera',
    role: 'CTO',
    company: 'LogiTech Pro',
    text: 'The multi-variant billing is genius. We only pay for what we use, and the cost calculator is spot-on.',
    stars: 5,
  },
  {
    name: 'Priya Sharma',
    role: 'VP Operations',
    company: 'CloudBase',
    text: 'Switching from Zendesk to PARWA was the best decision we made. The integration ecosystem is incredible.',
    stars: 5,
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-[#FAFAF8]">
      {/* ── Navigation ── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? 'bg-white/90 backdrop-blur-md shadow-sm border-b border-[#E5E7EB]'
            : 'bg-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] flex items-center justify-center shadow-md">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <span className="font-bold text-xl text-[#0A3D2E]">PARWA</span>
            </div>

            {/* Desktop Nav Links */}
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E] transition-colors">Features</a>
              <a href="#pricing" className="text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E] transition-colors">Pricing</a>
              <a href="#testimonials" className="text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E] transition-colors">Testimonials</a>
            </div>

            {/* Desktop CTA Buttons */}
            <div className="hidden md:flex items-center gap-3">
              <Button
                variant="ghost"
                onClick={() => router.push('/auth/login')}
                className="text-[#0A3D2E] hover:bg-[#0A3D2E]/5"
              >
                Sign In
              </Button>
              <Button
                onClick={() => router.push('/auth/register')}
                className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold shadow-md"
              >
                Get Started Free
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </div>

            {/* Mobile Menu Toggle */}
            <button
              className="md:hidden p-2 text-[#0A3D2E]"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden bg-white border-b border-[#E5E7EB] overflow-hidden"
            >
              <div className="px-4 py-4 space-y-3">
                <a href="#features" onClick={() => setMobileMenuOpen(false)} className="block text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E]">Features</a>
                <a href="#pricing" onClick={() => setMobileMenuOpen(false)} className="block text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E]">Pricing</a>
                <a href="#testimonials" onClick={() => setMobileMenuOpen(false)} className="block text-sm font-medium text-[#6B7280] hover:text-[#0A3D2E]">Testimonials</a>
                <div className="pt-2 border-t border-[#E5E7EB] space-y-2">
                  <Button variant="outline" onClick={() => router.push('/auth/login')} className="w-full border-[#0A3D2E] text-[#0A3D2E]">
                    Sign In
                  </Button>
                  <Button onClick={() => router.push('/auth/register')} className="w-full bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold">
                    Get Started Free
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* ── Hero Section ── */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-[#0A3D2E]/5 blur-3xl" />
          <div className="absolute top-1/2 -left-40 w-80 h-80 rounded-full bg-[#D4AF37]/10 blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#0A3D2E]/10 text-[#0A3D2E] text-sm font-medium mb-6">
              <Sparkles className="h-4 w-4" />
              AI-Powered Customer Support Platform
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#0A3D2E] tracking-tight leading-tight mb-6">
              Support That
              <span className="relative mx-3">
                <span className="relative z-10 text-[#D4AF37]">Never Sleeps</span>
                <span className="absolute bottom-1 left-0 right-0 h-3 bg-[#D4AF37]/20 -z-0 rounded" />
              </span>
              <br />
              Intelligence That Never Stops
            </h1>

            {/* Subheadline */}
            <p className="max-w-2xl mx-auto text-lg text-[#6B7280] mb-10 leading-relaxed">
              PARWA combines AI chatbots, smart billing, 35+ integrations, and enterprise-grade
              security into one platform. Resolve tickets 5x faster, cut costs by 60%,
              and delight every customer.
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <Button
                size="lg"
                onClick={() => router.push('/auth/register')}
                className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold px-8 py-3 text-base shadow-lg shadow-[#D4AF37]/25"
              >
                Start Free Trial
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="border-[#0A3D2E] text-[#0A3D2E] hover:bg-[#0A3D2E]/5 px-8 py-3 text-base"
              >
                Watch Demo
                <ChevronRight className="ml-1 h-5 w-5" />
              </Button>
            </div>

            {/* Stats Bar */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto">
              {stats.map((stat) => (
                <div key={stat.label} className="text-center">
                  <div className="text-2xl sm:text-3xl font-bold text-[#0A3D2E]">{stat.value}</div>
                  <div className="text-sm text-[#6B7280] mt-1">{stat.label}</div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Features Section ── */}
      <section id="features" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-[#0A3D2E] mb-4">
              Everything You Need to Scale Support
            </h2>
            <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">
              From AI chatbots to enterprise integrations, PARWA gives you the complete toolkit
              to deliver exceptional customer support at any scale.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, idx) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1, duration: 0.5 }}
                viewport={{ once: true }}
                className="p-6 rounded-xl border border-[#E5E7EB] hover:border-[#0A3D2E]/30 hover:shadow-lg transition-all duration-300 group bg-white"
              >
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <feature.icon className="h-6 w-6 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-[#0A3D2E] mb-2">{feature.title}</h3>
                <p className="text-[#6B7280] text-sm leading-relaxed">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="py-20 bg-gradient-to-b from-[#F0F5F3] to-[#FAFAF8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-[#0A3D2E] mb-4">
              Up and Running in Minutes
            </h2>
            <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">
              Three simple steps to transform your customer support experience.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            {[
              { step: '01', icon: Zap, title: 'Choose Your Plan', desc: 'Select Mini, Standard, or High based on your ticket volume and integration needs.' },
              { step: '02', icon: Globe, title: 'Connect Your Tools', desc: 'Integrate with your existing stack — Zendesk, Shopify, Slack, Salesforce, and 35+ more.' },
              { step: '03', icon: Bot, title: 'Let AI Handle It', desc: 'PARWA AI learns your workflows, resolves tickets automatically, and gets smarter every day.' },
            ].map((item, idx) => (
              <motion.div
                key={item.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.15, duration: 0.5 }}
                viewport={{ once: true }}
                className="text-center"
              >
                <div className="relative inline-flex items-center justify-center w-16 h-16 rounded-full bg-[#0A3D2E] text-white mb-5">
                  <item.icon className="h-7 w-7" />
                  <span className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-[#D4AF37] text-[#1A1A1A] text-xs font-bold flex items-center justify-center">
                    {item.step}
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-[#0A3D2E] mb-2">{item.title}</h3>
                <p className="text-[#6B7280] text-sm leading-relaxed">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing Section ── */}
      <section id="pricing" className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-[#0A3D2E] mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">
              Start free, scale as you grow. No hidden fees, no surprises.
              Every plan includes AI-powered support.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                viewport={{ once: true }}
                className={`relative rounded-2xl p-6 border-2 transition-all ${
                  plan.popular
                    ? 'border-[#D4AF37] shadow-xl shadow-[#D4AF37]/10 scale-[1.02]'
                    : 'border-[#E5E7EB] hover:border-[#0A3D2E]/30'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 bg-[#D4AF37] text-[#1A1A1A] text-xs font-bold rounded-full shadow">
                    Most Popular
                  </div>
                )}

                <div className="text-center mb-6">
                  <h3 className="text-lg font-semibold text-[#0A3D2E]">{plan.name}</h3>
                  <p className="text-sm text-[#6B7280] mt-1">{plan.description}</p>
                  <div className="mt-4">
                    <span className="text-4xl font-bold text-[#0A3D2E]">${plan.price}</span>
                    <span className="text-[#6B7280] text-sm">/month</span>
                  </div>
                </div>

                <ul className="space-y-3 mb-6">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="h-4 w-4 text-[#0A3D2E] mt-0.5 shrink-0" />
                      <span className="text-[#1A1A1A]">{f}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  onClick={() => router.push('/auth/register')}
                  className={`w-full font-semibold ${
                    plan.popular
                      ? 'bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] shadow-md'
                      : 'bg-[#0A3D2E] hover:bg-[#1B5E40] text-white'
                  }`}
                >
                  Get Started
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Testimonials ── */}
      <section id="testimonials" className="py-20 bg-gradient-to-b from-[#F0F5F3] to-[#FAFAF8]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-[#0A3D2E] mb-4">
              Loved by Support Teams Worldwide
            </h2>
            <p className="text-[#6B7280] text-lg max-w-2xl mx-auto">
              See how companies are transforming their customer support with PARWA.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {testimonials.map((t, idx) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1, duration: 0.5 }}
                viewport={{ once: true }}
                className="bg-white rounded-xl p-6 border border-[#E5E7EB] shadow-sm"
              >
                <div className="flex items-center gap-0.5 mb-4">
                  {Array.from({ length: t.stars }).map((_, i) => (
                    <Star key={i} className="h-4 w-4 text-[#D4AF37] fill-[#D4AF37]" />
                  ))}
                </div>
                <p className="text-[#1A1A1A] text-sm leading-relaxed mb-4">&ldquo;{t.text}&rdquo;</p>
                <div>
                  <div className="font-semibold text-sm text-[#0A3D2E]">{t.name}</div>
                  <div className="text-xs text-[#6B7280]">{t.role}, {t.company}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="py-20 bg-gradient-to-br from-[#0A3D2E] to-[#1B5E40] relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-0 right-0 w-64 h-64 rounded-full bg-[#D4AF37]/10 blur-3xl" />
          <div className="absolute bottom-0 left-0 w-80 h-80 rounded-full bg-white/5 blur-3xl" />
        </div>

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to Transform Your Support?
          </h2>
          <p className="text-white/70 text-lg mb-8 max-w-2xl mx-auto">
            Join thousands of companies using PARWA to deliver faster, smarter,
            and more personal customer support. Start free today.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              size="lg"
              onClick={() => router.push('/auth/register')}
              className="bg-[#D4AF37] hover:bg-[#E5C860] text-[#1A1A1A] font-semibold px-8 py-3 text-base shadow-lg shadow-[#D4AF37]/25"
            >
              Start Free Trial
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => router.push('/auth/login')}
              className="border-white/30 text-white hover:bg-white/10 px-8 py-3 text-base"
            >
              Sign In to Dashboard
            </Button>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-[#0A3D2E] text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-lg bg-[#D4AF37] flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-[#1A1A1A]" />
                </div>
                <span className="font-bold text-lg">PARWA</span>
              </div>
              <p className="text-white/60 text-sm leading-relaxed">
                AI-powered customer support platform that scales with your business.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Product</h4>
              <ul className="space-y-2 text-white/60 text-sm">
                <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Integrations</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Changelog</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Company</h4>
              <ul className="space-y-2 text-white/60 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-sm mb-3">Legal</h4>
              <ul className="space-y-2 text-white/60 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Security</a></li>
                <li><a href="#" className="hover:text-white transition-colors">GDPR</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-white/10 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-white/50 text-sm">&copy; 2026 PARWA. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <Lock className="h-4 w-4 text-white/40" />
              <span className="text-white/40 text-xs">SOC 2 Compliant &bull; GDPR Ready &bull; AES-256 Encrypted</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
