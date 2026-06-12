"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Zap,
  ArrowRight,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Bot,
  Shield,
  BarChart3,
  Globe,
  HeadphonesIcon,
  CheckCircle2,
  Sparkles,
  TrendingUp,
  Layers,
  Send,
  MessageSquare,
} from "lucide-react";

const heroSlides = [
  {
    tagline: "Chat with Jarvis. Control from Dashboard. Zero training needed.",
    headline: "Control Everything with Just a Chat",
    subtitle:
      "Just type what you need. Jarvis understands and does it instantly. Like texting a super-smart employee who never sleeps.",
    chatMessages: [
      { role: "user", text: "Handle these 15 refund requests ✨" },
      { role: "bot", text: "Done! $4,280 refunded. 3.5hrs saved.", status: "Sent instantly" },
    ],
  },
  {
    tagline: "Automate. Escalate. Delight your customers.",
    headline: "AI That Actually Understands Your Business",
    subtitle:
      "From refund processing to order tracking, PARWA handles complex support tasks across 30+ integrations with zero hallucination.",
    chatMessages: [
      { role: "user", text: "Check order #4821 shipping status" },
      { role: "bot", text: "Out for delivery via FedEx. ETA: 2pm today.", status: "Tracked live" },
    ],
  },
  {
    tagline: "Route tickets smartly. Never miss a deadline.",
    headline: "Smart Routing Saves 70% on Support Costs",
    subtitle:
      "PARWA's multi-variant AI routes tickets by complexity — simple queries to Mini, complex ones to High. You only pay for what you use.",
    chatMessages: [
      { role: "user", text: "Route today's 200 tickets by priority" },
      { role: "bot", text: "Done! 142 auto-resolved, 38 to PARWA, 20 to High.", status: "Routed in 1.2s" },
    ],
  },
];

const features = [
  {
    icon: Bot,
    title: "AI-Powered Support",
    description: "Intelligent ticket routing, FAQ matching, and RAG-powered responses that learn from your knowledge base.",
  },
  {
    icon: Layers,
    title: "3 AI Variants",
    description: "From Mini PARWA for startups to PARWA High for enterprises. Scale as you grow with multi-variant support.",
  },
  {
    icon: Globe,
    title: "30+ Integrations",
    description: "Connect HubSpot, Shopify, Salesforce, Slack, and more. All auth types supported with encrypted key management.",
  },
  {
    icon: Shield,
    title: "Enterprise Security",
    description: "AES-256-GCM encrypted API keys, audit trails, circuit breakers, and automatic key rotation detection.",
  },
  {
    icon: BarChart3,
    title: "Real-time Analytics",
    description: "Track AI accuracy, ticket routing, integration health, and cost savings with comprehensive dashboards.",
  },
  {
    icon: HeadphonesIcon,
    title: "24/7 Automation",
    description: "Your AI support agent never sleeps. Handle tickets around the clock with intelligent escalation rules.",
  },
];

const variantComparison = [
  { feature: "Tickets/month", mini: "500", parwa: "2,000", high: "10,000" },
  { feature: "AI Pipeline Steps", mini: "3", parwa: "6", high: "9" },
  { feature: "Concurrent AI", mini: "2", parwa: "3", high: "5" },
  { feature: "Knowledge Base", mini: true, parwa: true, high: true },
  { feature: "FAQ Search", mini: true, parwa: true, high: true },
  { feature: "RAG Responses", mini: false, parwa: true, high: true },
  { feature: "External Tool Calls", mini: false, parwa: true, high: true },
  { feature: "Sentiment Analysis", mini: false, parwa: false, high: true },
  { feature: "Multi-variant Mixing", mini: true, parwa: true, high: true },
];

export default function LandingPage() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const goToSlide = (index: number) => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    setCurrentSlide(index);
    setTimeout(() => setIsTransitioning(false), 500);
  };

  const nextSlide = () => goToSlide((currentSlide + 1) % heroSlides.length);
  const prevSlide = () => goToSlide((currentSlide - 1 + heroSlides.length) % heroSlides.length);

  useEffect(() => {
    const timer = setInterval(nextSlide, 6000);
    return () => clearInterval(timer);
  }, [currentSlide]);

  const slide = heroSlides[currentSlide];

  return (
    <div className="min-h-screen bg-[#1a1410] text-white overflow-hidden">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#1a1410]/90 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-[#f97316] flex items-center justify-center">
              <Zap className="h-4.5 w-4.5 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight">PARWA</span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-white/70 hover:text-white transition-colors">
              Features
            </a>
            <a href="#models" className="text-sm text-white/70 hover:text-white transition-colors">
              Models
            </a>
            <a href="#roi" className="text-sm text-white/70 hover:text-white transition-colors">
              ROI Calculator
            </a>
            <a href="#integrations" className="text-sm text-white/70 hover:text-white transition-colors">
              Try Jarvis
            </a>
          </nav>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 text-sm text-white/60">
              <div className="flex -space-x-1">
                <div className="h-5 w-5 rounded-full bg-[#f97316]/80 border border-[#1a1410]" />
                <div className="h-5 w-5 rounded-full bg-[#f97316]/60 border border-[#1a1410]" />
                <div className="h-5 w-5 rounded-full bg-[#f97316]/40 border border-[#1a1410]" />
              </div>
              <span>2,400+ businesses trust us</span>
            </div>
            <Link href="/signup">
              <Button className="bg-[#f97316] hover:bg-[#ea580c] text-white rounded-lg px-5">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section with Carousel */}
      <section className="relative min-h-[calc(100vh-4rem)] flex items-center">
        {/* Background bokeh effects */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-[#f97316]/5 rounded-full blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-[#f97316]/8 rounded-full blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#f97316]/3 rounded-full blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 w-full">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: Chat Demo */}
            <div className="order-2 lg:order-1">
              <div className="bg-[#2a2018] rounded-2xl p-6 border border-white/10 shadow-2xl max-w-md mx-auto lg:mx-0">
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-8 w-8 rounded-full bg-[#f97316] flex items-center justify-center">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <span className="text-sm font-medium text-white/80">Jarvis AI</span>
                  <div className="ml-auto h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <div className="space-y-3">
                  {slide.chatMessages.map((msg, i) => (
                    <div key={i}>
                      <div
                        className={`rounded-xl px-4 py-3 text-sm ${
                          msg.role === "user"
                            ? "bg-[#3a2e22] text-white/80 ml-4"
                            : "bg-[#3a2e22] text-white/80 mr-4 border-l-2 border-[#f97316]"
                        }`}
                      >
                        {msg.text}
                      </div>
                      {msg.status && (
                        <div className="flex items-center gap-1.5 mt-1.5 ml-6">
                          <div className="h-3.5 w-3.5 rounded-full bg-[#f97316]/20 flex items-center justify-center">
                            <Send className="h-2 w-2 text-[#f97316]" />
                          </div>
                          <span className="text-xs text-white/40">{msg.status}</span>
                        </div>
                      )}
                    </div>
                  ))}
                  <div className="flex items-center gap-2 mt-2">
                    <div className="flex-1 h-9 bg-[#3a2e22] rounded-lg flex items-center px-3">
                      <span className="text-xs text-white/30">Type your request...</span>
                    </div>
                    <div className="h-9 w-9 rounded-lg bg-[#f97316] flex items-center justify-center">
                      <MessageSquare className="h-4 w-4 text-white" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Text & CTA */}
            <div className="order-1 lg:order-2 text-center lg:text-left">
              <p className="text-[#f97316] text-sm font-semibold tracking-wider uppercase mb-4">
                {slide.tagline}
              </p>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6 leading-tight">
                {slide.headline}
              </h1>
              <p className="text-lg text-white/60 max-w-xl mx-auto lg:mx-0 mb-8">
                {slide.subtitle}
              </p>
              <a
                href="#features"
                className="inline-flex items-center gap-2 text-[#f97316] hover:text-[#fb923c] font-medium transition-colors"
              >
                See How It Works
                <ArrowDown className="h-4 w-4" />
              </a>
            </div>
          </div>

          {/* Carousel Navigation */}
          <div className="flex items-center justify-center gap-4 mt-12">
            <button
              onClick={prevSlide}
              className="h-9 w-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="flex items-center gap-2">
              {heroSlides.map((_, i) => (
                <button
                  key={i}
                  onClick={() => goToSlide(i)}
                  className={`h-2 rounded-full transition-all duration-300 ${
                    i === currentSlide ? "w-6 bg-[#f97316]" : "w-2 bg-white/30"
                  }`}
                />
              ))}
            </div>
            <button
              onClick={nextSlide}
              className="h-9 w-9 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-white/5 bg-[#1a1410]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: "30+", label: "Integrations" },
              { value: "70%", label: "Cost Savings" },
              { value: "<2s", label: "Response Time" },
              { value: "99.9%", label: "Uptime SLA" },
            ].map((stat) => (
              <div key={stat.label}>
                <div className="text-3xl font-bold text-[#f97316]">{stat.value}</div>
                <div className="text-sm text-white/50 mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 sm:py-28 bg-[#1e1814]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything you need for{" "}
              <span className="text-[#f97316]">AI-first support</span>
            </h2>
            <p className="text-lg text-white/50 max-w-2xl mx-auto">
              From intelligent ticket routing to knowledge base search, PARWA covers every aspect of modern customer support.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="group p-6 rounded-xl bg-[#2a2018] border border-white/5 hover:border-[#f97316]/30 transition-all duration-300 hover:shadow-lg hover:shadow-[#f97316]/5"
              >
                <div className="h-12 w-12 rounded-xl bg-[#f97316]/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <feature.icon className="h-6 w-6 text-[#f97316]" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-white/50">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing / Models */}
      <section id="models" className="py-20 sm:py-28 bg-[#1a1410]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Choose your{" "}
              <span className="text-[#f97316]">AI model</span>
            </h2>
            <p className="text-lg text-white/50 max-w-2xl mx-auto">
              Mix and match variants to optimize cost and coverage. Add more anytime.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-12">
            {/* Mini PARWA */}
            <div className="relative overflow-hidden rounded-xl bg-[#2a2018] border border-white/5 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="h-5 w-5 text-amber-400" />
                <h3 className="text-lg font-semibold">Mini PARWA</h3>
              </div>
              <div className="mb-4">
                <span className="text-4xl font-bold">$999</span>
                <span className="text-white/50">/mo</span>
              </div>
              <p className="text-sm text-white/50 mb-6">Perfect for startups and small teams getting started with AI support.</p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 500 tickets/month</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 3 AI pipeline steps</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 2 concurrent AI</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> FAQ & KB search</li>
              </ul>
              <Link href="/signup" className="block mt-6">
                <Button variant="outline" className="w-full border-white/10 hover:border-[#f97316]/50 hover:bg-[#f97316]/10 text-white">
                  Get Mini
                </Button>
              </Link>
            </div>

            {/* PARWA - Most Popular */}
            <div className="relative overflow-hidden rounded-xl bg-[#2a2018] border-2 border-[#f97316] p-6 shadow-lg shadow-[#f97316]/10">
              <div className="absolute top-0 right-0 bg-[#f97316] text-white text-xs px-3 py-1 rounded-bl-lg font-medium">
                Most Popular
              </div>
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp className="h-5 w-5 text-[#f97316]" />
                <h3 className="text-lg font-semibold">PARWA</h3>
              </div>
              <div className="mb-4">
                <span className="text-4xl font-bold">$2,499</span>
                <span className="text-white/50">/mo</span>
              </div>
              <p className="text-sm text-white/50 mb-6">For growing businesses that need powerful AI support with full integrations.</p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 2,000 tickets/month</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 6 AI pipeline steps</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 3 concurrent AI</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> RAG + External tools</li>
              </ul>
              <Link href="/signup" className="block mt-6">
                <Button className="w-full bg-[#f97316] hover:bg-[#ea580c] text-white">
                  Get PARWA
                </Button>
              </Link>
            </div>

            {/* PARWA High */}
            <div className="relative overflow-hidden rounded-xl bg-[#2a2018] border border-white/5 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-5 w-5 text-purple-400" />
                <h3 className="text-lg font-semibold">PARWA High</h3>
              </div>
              <div className="mb-4">
                <span className="text-4xl font-bold">$4,999</span>
                <span className="text-white/50">/mo</span>
              </div>
              <p className="text-sm text-white/50 mb-6">Enterprise-grade AI support with maximum capacity and advanced features.</p>
              <ul className="space-y-2">
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 10,000 tickets/month</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 9 AI pipeline steps</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> 5 concurrent AI</li>
                <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-[#f97316]" /> Sentiment analysis</li>
              </ul>
              <Link href="/signup" className="block mt-6">
                <Button variant="outline" className="w-full border-white/10 hover:border-[#f97316]/50 hover:bg-[#f97316]/10 text-white">
                  Get High
                </Button>
              </Link>
            </div>
          </div>

          {/* ROI Calculator Teaser */}
          <div id="roi" className="rounded-xl bg-gradient-to-r from-[#2a2018] to-[#2a2018] border border-[#f97316]/20 p-8 text-center">
            <h3 className="text-xl font-semibold mb-2">Calculate your savings</h3>
            <p className="text-white/50 mb-4">
              A human agent costs ~$3,500/mo. PARWA handles 2,000+ tickets for $2,499/mo — that&apos;s a 70%+ saving.
            </p>
            <Link href="/signup">
              <Button className="bg-[#f97316] hover:bg-[#ea580c] text-white">
                Start Saving Today
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Integrations Preview */}
      <section id="integrations" className="py-20 sm:py-28 bg-[#1e1814]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              30+{" "}
              <span className="text-[#f97316]">integrations</span>{" "}
              and counting
            </h2>
            <p className="text-lg text-white/50 max-w-2xl mx-auto">
              Connect your favorite tools with encrypted key management. All 5 auth types supported.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-3 max-w-3xl mx-auto">
            {[
              "HubSpot", "Salesforce", "Shopify", "Zendesk", "Slack",
              "Stripe", "Jira", "GitHub", "Mailchimp", "Intercom",
              "WooCommerce", "Pipedrive", "Freshdesk", "ShipStation",
              "Klaviyo", "Notion", "Linear", "PayPal", "DHL", "FedEx",
              "Mixpanel", "Amplitude", "BigCommerce", "AfterShip",
              "EasyPost", "Gorgias", "Brevo", "Paddle", "UPS",
              "Google Analytics",
            ].map((name) => (
              <span
                key={name}
                className="px-4 py-2 text-sm rounded-lg bg-white/5 border border-white/10 text-white/70 hover:bg-[#f97316]/10 hover:border-[#f97316]/30 hover:text-white transition-colors cursor-default"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 bg-gradient-to-r from-[#f97316] to-[#ea580c]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to transform your support?
          </h2>
          <p className="text-lg text-white/80 mb-8">
            Get started in minutes with our guided onboarding wizard. No credit card required.
          </p>
          <Link href="/signup">
            <Button size="lg" className="bg-white text-[#f97316] hover:bg-white/90 px-8 h-12 text-base font-semibold">
              Get Started Free
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 bg-[#1a1410]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-[#f97316] flex items-center justify-center">
                <Zap className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="font-semibold">PARWA</span>
            </div>
            <p className="text-sm text-white/40">
              &copy; {new Date().getFullYear()} PARWA. AI-powered customer support.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
