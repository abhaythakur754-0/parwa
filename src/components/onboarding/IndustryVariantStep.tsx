"use client";

import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Cloud, ShoppingCart, Truck, Building2, Zap, TrendingUp, Sparkles } from "lucide-react";
import { PRICES, VARIANT_LIMITS } from "@/lib/config";
import { useState } from "react";

const industries = [
  { id: "saas", name: "SaaS", icon: Cloud, description: "Software-as-a-Service companies", color: "from-blue-500 to-cyan-500" },
  { id: "ecommerce", name: "E-commerce", icon: ShoppingCart, description: "Online retail and stores", color: "from-orange-500 to-amber-500" },
  { id: "logistics", name: "Logistics", icon: Truck, description: "Shipping and supply chain", color: "from-purple-500 to-violet-500" },
  { id: "other", name: "Other", icon: Building2, description: "Other industries", color: "from-gray-500 to-slate-500" },
];

const variants = [
  {
    id: "mini",
    name: "Mini PARWA",
    icon: Zap,
    price: PRICES.mini_parwa.monthly,
    color: "from-amber-500 to-yellow-500",
    features: VARIANT_LIMITS.mini,
    highlights: ["FAQ matching", "Knowledge base search", "Basic ticket routing"],
  },
  {
    id: "parwa",
    name: "PARWA",
    icon: TrendingUp,
    price: PRICES.parwa.monthly,
    color: "from-emerald-500 to-teal-600",
    popular: true,
    features: VARIANT_LIMITS.parwa,
    highlights: ["RAG-powered responses", "External tool calls", "Advanced routing"],
  },
  {
    id: "parwa_high",
    name: "PARWA High",
    icon: Sparkles,
    price: PRICES.parwa_high.monthly,
    color: "from-purple-500 to-violet-500",
    features: VARIANT_LIMITS.parwa_high,
    highlights: ["Sentiment analysis", "Full pipeline access", "Priority support"],
  },
];

export function IndustryVariantStep() {
  const { industry, variant, setIndustry, setVariant } = useOnboardingStore();
  const [saving, setSaving] = useState(false);

  const handleIndustrySelect = (id: string) => {
    setIndustry(id);
  };

  const handleVariantSelect = async (id: string) => {
    setVariant(id);
    if (industry) {
      setSaving(true);
      try {
        await fetch("/api/onboarding/industry-variant", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ industry, variant: id }),
        });
      } catch {
        // Error handled silently
      } finally {
        setSaving(false);
      }
    }
  };

  return (
    <div className="space-y-8">
      {/* Industry Selection */}
      <div>
        <h2 className="text-xl font-semibold mb-1">Select your industry</h2>
        <p className="text-sm text-muted-foreground mb-4">
          This helps us recommend the right integrations for your workflow.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {industries.map((ind) => (
            <Card
              key={ind.id}
              className={`cursor-pointer transition-all hover:shadow-md ${
                industry === ind.id
                  ? "ring-2 ring-emerald-500 border-emerald-300 dark:border-emerald-700"
                  : "hover:border-emerald-200 dark:hover:border-emerald-800"
              }`}
              onClick={() => handleIndustrySelect(ind.id)}
            >
              <CardContent className="p-4 text-center">
                <div
                  className={`h-12 w-12 rounded-xl bg-gradient-to-br ${ind.color} flex items-center justify-center mx-auto mb-2`}
                >
                  <ind.icon className="h-6 w-6 text-white" />
                </div>
                <p className="font-medium text-sm">{ind.name}</p>
                <p className="text-xs text-muted-foreground mt-1">{ind.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Variant Selection */}
      <div>
        <h2 className="text-xl font-semibold mb-1">Choose your AI variant</h2>
        <p className="text-sm text-muted-foreground mb-4">
          You can add more variants later. Mix and match for optimal coverage.
        </p>
        <div className="grid sm:grid-cols-3 gap-4">
          {variants.map((v) => (
            <Card
              key={v.id}
              className={`relative cursor-pointer transition-all hover:shadow-md ${
                variant === v.id
                  ? "ring-2 ring-emerald-500 border-emerald-300 dark:border-emerald-700"
                  : "hover:border-emerald-200 dark:hover:border-emerald-800"
              }`}
              onClick={() => handleVariantSelect(v.id)}
            >
              {v.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-xs">
                    Most Popular
                  </Badge>
                </div>
              )}
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <div
                    className={`h-8 w-8 rounded-lg bg-gradient-to-br ${v.color} flex items-center justify-center`}
                  >
                    <v.icon className="h-4 w-4 text-white" />
                  </div>
                  <div>
                    <p className="font-semibold text-sm">{v.name}</p>
                  </div>
                </div>
                <div className="mb-3">
                  <span className="text-2xl font-bold">${(v.price / 100).toFixed(2)}</span>
                  <span className="text-xs text-muted-foreground">/mo</span>
                </div>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    {v.features.tickets.toLocaleString()} tickets/mo
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    {v.features.ai_steps} AI steps
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    {v.features.concurrent} concurrent AI
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-border/50">
                  {v.highlights.map((h) => (
                    <p key={h} className="text-xs text-muted-foreground">• {h}</p>
                  ))}
                </div>
                {saving && variant === v.id && (
                  <p className="text-xs text-emerald-600 mt-2 animate-pulse">Saving...</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
