"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  Sparkles,
  Zap,
  Shield,
  ArrowRight,
  CheckCircle2,
  BarChart3,
  Globe,
  HeadphonesIcon,
  Layers,
  TrendingUp,
} from "lucide-react";

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
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-md border-b border-border/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">PARWA</span>
          </div>
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Features
            </a>
            <a href="#pricing" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Pricing
            </a>
            <a href="#integrations" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Integrations
            </a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Login
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="sm" className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/50 via-transparent to-teal-50/30 dark:from-emerald-950/20 dark:to-teal-950/10" />
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-emerald-400/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-teal-400/10 rounded-full blur-3xl" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-28 lg:py-36">
          <div className="text-center max-w-4xl mx-auto">
            <Badge variant="secondary" className="mb-6 px-4 py-1.5 text-sm font-medium">
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
              AI-Powered Customer Support Platform
            </Badge>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
              Transform Support with{" "}
              <span className="bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
                Intelligent AI
              </span>
            </h1>
            <p className="text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10">
              PARWA handles customer support tickets with AI-powered routing, knowledge base search,
              and 30+ integrations. Save up to 70% compared to hiring human agents.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/signup">
                <Button size="lg" className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white px-8 h-12 text-base">
                  Start Free Trial
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/login">
                <Button size="lg" variant="outline" className="px-8 h-12 text-base">
                  Sign In
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-border/50 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { value: "30+", label: "Integrations" },
              { value: "70%", label: "Cost Savings" },
              { value: "<2s", label: "Response Time" },
              { value: "99.9%", label: "Uptime SLA" },
            ].map((stat) => (
              <div key={stat.label}>
                <div className="text-3xl font-bold bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
                  {stat.value}
                </div>
                <div className="text-sm text-muted-foreground mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything you need for{" "}
              <span className="bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
                AI-first support
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              From intelligent ticket routing to knowledge base search, PARWA covers every aspect of modern customer support.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <Card key={feature.title} className="group hover:shadow-lg transition-all duration-300 border-border/50 hover:border-emerald-200 dark:hover:border-emerald-800">
                <CardContent className="p-6">
                  <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-900/30 dark:to-teal-900/30 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <feature.icon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing / Variant Comparison */}
      <section id="pricing" className="py-20 sm:py-28 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Choose your{" "}
              <span className="bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
                AI variant
              </span>
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Mix and match variants to optimize cost and coverage. Add more anytime.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 mb-12">
            {/* Mini PARWA */}
            <Card className="relative overflow-hidden border-border/50">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Zap className="h-5 w-5 text-amber-500" />
                  <h3 className="text-lg font-semibold">Mini PARWA</h3>
                </div>
                <div className="mb-4">
                  <span className="text-4xl font-bold">$999</span>
                  <span className="text-muted-foreground">/mo</span>
                </div>
                <p className="text-sm text-muted-foreground mb-6">Perfect for startups and small teams getting started with AI support.</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 500 tickets/month</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 3 AI pipeline steps</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 2 concurrent AI</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> FAQ & KB search</li>
                </ul>
              </CardContent>
            </Card>

            {/* PARWA */}
            <Card className="relative overflow-hidden border-emerald-300 dark:border-emerald-700 shadow-lg">
              <div className="absolute top-0 right-0 bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-xs px-3 py-1 rounded-bl-lg font-medium">
                Most Popular
              </div>
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <TrendingUp className="h-5 w-5 text-emerald-500" />
                  <h3 className="text-lg font-semibold">PARWA</h3>
                </div>
                <div className="mb-4">
                  <span className="text-4xl font-bold">$2,499</span>
                  <span className="text-muted-foreground">/mo</span>
                </div>
                <p className="text-sm text-muted-foreground mb-6">For growing businesses that need powerful AI support with full integrations.</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 2,000 tickets/month</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 6 AI pipeline steps</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 3 concurrent AI</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> RAG + External tools</li>
                </ul>
              </CardContent>
            </Card>

            {/* PARWA High */}
            <Card className="relative overflow-hidden border-border/50">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Sparkles className="h-5 w-5 text-purple-500" />
                  <h3 className="text-lg font-semibold">PARWA High</h3>
                </div>
                <div className="mb-4">
                  <span className="text-4xl font-bold">$4,999</span>
                  <span className="text-muted-foreground">/mo</span>
                </div>
                <p className="text-sm text-muted-foreground mb-6">Enterprise-grade AI support with maximum capacity and advanced features.</p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 10,000 tickets/month</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 9 AI pipeline steps</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> 5 concurrent AI</li>
                  <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Sentiment analysis</li>
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* ROI Calculator Teaser */}
          <Card className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border-emerald-200 dark:border-emerald-800">
            <CardContent className="p-8 text-center">
              <h3 className="text-xl font-semibold mb-2">Calculate your savings</h3>
              <p className="text-muted-foreground mb-4">
                A human agent costs ~$3,500/mo. PARWA handles 2,000+ tickets for $2,499/mo — that&apos;s a 70%+ saving.
              </p>
              <Link href="/signup">
                <Button className="bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-600 hover:to-teal-700 text-white">
                  Start Saving Today
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Integrations Preview */}
      <section id="integrations" className="py-20 sm:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              30+{" "}
              <span className="bg-gradient-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
                integrations
              </span>{" "}
              and counting
            </h2>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
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
              <Badge
                key={name}
                variant="secondary"
                className="px-4 py-2 text-sm hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors cursor-default"
              >
                {name}
              </Badge>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 bg-gradient-to-r from-emerald-500 to-teal-600">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to transform your support?
          </h2>
          <p className="text-lg text-emerald-100 mb-8">
            Get started in minutes with our guided onboarding wizard. No credit card required.
          </p>
          <Link href="/signup">
            <Button size="lg" className="bg-white text-emerald-700 hover:bg-emerald-50 px-8 h-12 text-base font-semibold">
              Get Started Free
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <span className="font-semibold">PARWA</span>
            </div>
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} PARWA. AI-powered customer support.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
