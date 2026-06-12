"use client";

import { useState, useMemo } from "react";
import { useOnboardingStore } from "@/store/onboarding-store";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { PRICES, ADD_ONS, OVERAGE_RATE, VARIANT_LIMITS } from "@/lib/config";
import {
  DollarSign,
  Zap,
  TrendingUp,
  Sparkles,
  Plus,
  Minus,
  Calculator,
  CheckCircle2,
  Mic,
  Code2,
} from "lucide-react";

const variantIcons: Record<string, typeof Zap> = {
  mini: Zap,
  parwa: TrendingUp,
  parwa_high: Sparkles,
};

const variantNames: Record<string, string> = {
  mini: "Mini PARWA",
  parwa: "PARWA",
  parwa_high: "PARWA High",
};

const variantPrices: Record<string, number> = {
  mini: PRICES.mini_parwa.monthly,
  parwa: PRICES.parwa.monthly,
  parwa_high: PRICES.parwa_high.monthly,
};

interface ActiveVariant {
  id: string;
  type: string;
  ticketAllocation: number;
}

export function CostBreakdownStep() {
  const { variant } = useOnboardingStore();
  const [activeVariants, setActiveVariants] = useState<ActiveVariant[]>(
    variant ? [{ id: "1", type: variant, ticketAllocation: VARIANT_LIMITS[variant as keyof typeof VARIANT_LIMITS]?.tickets || 500 }] : []
  );
  const [voiceAddOn, setVoiceAddOn] = useState(false);
  const [customApiAddOn, setCustomApiAddOn] = useState(false);
  const [projectedTickets, setProjectedTickets] = useState(1000);

  const totalMonthlyCost = useMemo(() => {
    let cost = activeVariants.reduce((sum, v) => sum + (variantPrices[v.type] || 0), 0);
    if (voiceAddOn) cost += ADD_ONS.voice.price;
    if (customApiAddOn) cost += ADD_ONS.custom_api.price;
    return cost;
  }, [activeVariants, voiceAddOn, customApiAddOn]);

  const totalTicketLimit = useMemo(
    () => activeVariants.reduce((sum, v) => sum + v.ticketAllocation, 0),
    [activeVariants]
  );

  const overageCost = useMemo(() => {
    const overage = Math.max(0, projectedTickets - totalTicketLimit);
    return overage * OVERAGE_RATE;
  }, [projectedTickets, totalTicketLimit]);

  const humanAgentCost = useMemo(() => {
    // Assume $3500/month per human agent handling ~500 tickets
    const agentsNeeded = Math.ceil(projectedTickets / 500);
    return agentsNeeded * 3500;
  }, [projectedTickets]);

  const savings = useMemo(() => {
    if (humanAgentCost === 0) return 0;
    return Math.round(((humanAgentCost - (totalMonthlyCost + overageCost)) / humanAgentCost) * 100);
  }, [humanAgentCost, totalMonthlyCost, overageCost]);

  const addVariant = (type: string) => {
    if (activeVariants.find((v) => v.type === type)) return;
    setActiveVariants((prev) => [
      ...prev,
      {
        id: Math.random().toString(36).substr(2, 9),
        type,
        ticketAllocation: VARIANT_LIMITS[type as keyof typeof VARIANT_LIMITS]?.tickets || 500,
      },
    ]);
  };

  const removeVariant = (id: string) => {
    setActiveVariants((prev) => prev.filter((v) => v.id !== id));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">Cost Breakdown</h2>
        <p className="text-sm text-muted-foreground">
          Mix and match variants for optimal cost and coverage.
        </p>
      </div>

      {/* Active Variants */}
      <div className="space-y-3">
        {activeVariants.map((v) => {
          const Icon = variantIcons[v.type] || Zap;
          const limits = VARIANT_LIMITS[v.type as keyof typeof VARIANT_LIMITS];
          const usagePct = limits ? (v.ticketAllocation / limits.tickets) * 100 : 0;

          return (
            <Card key={v.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-emerald-500" />
                    <span className="font-medium text-sm">{variantNames[v.type]}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold">${((variantPrices[v.type] || 0) / 100).toFixed(2)}/mo</span>
                    {activeVariants.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 text-destructive"
                        onClick={() => removeVariant(v.id)}
                      >
                        <Minus className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
                {limits && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Ticket allocation</span>
                      <span>{v.ticketAllocation.toLocaleString()} / {limits.tickets.toLocaleString()}</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all"
                        style={{ width: `${Math.min(usagePct, 100)}%` }}
                      />
                    </div>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span>AI Steps: {limits.ai_steps}</span>
                      <span>Concurrent: {limits.concurrent}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}

        {/* Add Variant */}
        {activeVariants.length < 3 && (
          <div className="flex gap-2">
            {(["mini", "parwa", "parwa_high"] as const).map((type) =>
              !activeVariants.find((v) => v.type === type) ? (
                <Button
                  key={type}
                  variant="outline"
                  size="sm"
                  className="text-xs flex-1"
                  onClick={() => addVariant(type)}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add {variantNames[type]}
                </Button>
              ) : null
            )}
          </div>
        )}

        {activeVariants.length > 1 && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400">
            Need more coverage? Add another variant to handle additional tickets.
          </p>
        )}
      </div>

      {/* Add-ons */}
      <Card>
        <CardContent className="p-4 space-y-4">
          <h3 className="font-medium text-sm">Add-ons</h3>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mic className="h-4 w-4 text-muted-foreground" />
              <div>
                <Label className="text-sm font-medium">Voice Add-on</Label>
                <p className="text-xs text-muted-foreground">${ADD_ONS.voice.price}/mo</p>
              </div>
            </div>
            <Switch checked={voiceAddOn} onCheckedChange={setVoiceAddOn} />
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Code2 className="h-4 w-4 text-muted-foreground" />
              <div>
                <Label className="text-sm font-medium">Custom API Add-on</Label>
                <p className="text-xs text-muted-foreground">${ADD_ONS.custom_api.price}/mo</p>
              </div>
            </div>
            <Switch checked={customApiAddOn} onCheckedChange={setCustomApiAddOn} />
          </div>
        </CardContent>
      </Card>

      {/* Overage Projection */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <h3 className="font-medium text-sm">Overage Projection</h3>
          <div className="flex items-center gap-3">
            <Label className="text-sm text-muted-foreground">Projected tickets/mo</Label>
            <input
              type="number"
              value={projectedTickets}
              onChange={(e) => setProjectedTickets(Number(e.target.value) || 0)}
              className="w-24 text-sm border rounded-md px-2 py-1 bg-background"
            />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Ticket limit</span>
            <span>{totalTicketLimit.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Overage ({OVERAGE_RATE}/ticket)</span>
            <span className={overageCost > 0 ? "text-amber-600" : "text-emerald-600"}>
              ${overageCost.toFixed(2)}/mo
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Total & Savings */}
      <Card className="border-emerald-200 dark:border-emerald-800 bg-gradient-to-br from-emerald-50/50 to-teal-50/50 dark:from-emerald-950/20 dark:to-teal-950/20">
        <CardContent className="p-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-medium">Total Monthly Cost</span>
              <span className="text-2xl font-bold">${((totalMonthlyCost + overageCost) / 100).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Variant cost</span>
              <span>${(totalMonthlyCost / 100).toFixed(2)}</span>
            </div>
            {voiceAddOn && (
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>Voice add-on</span>
                <span>${(ADD_ONS.voice.price / 100).toFixed(2)}</span>
              </div>
            )}
            {customApiAddOn && (
              <div className="flex justify-between text-sm text-muted-foreground">
                <span>Custom API add-on</span>
                <span>${(ADD_ONS.custom_api.price / 100).toFixed(2)}</span>
              </div>
            )}
            {overageCost > 0 && (
              <div className="flex justify-between text-sm text-amber-600">
                <span>Overage estimate</span>
                <span>${(overageCost / 100).toFixed(2)}</span>
              </div>
            )}
            <Separator />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calculator className="h-4 w-4 text-emerald-500" />
                <span className="text-sm">vs. Human agents</span>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground line-through">${(humanAgentCost / 100).toFixed(2)}/mo</p>
                <p className="text-sm font-semibold text-emerald-600">Save {savings}%</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Checkout */}
      <div className="flex justify-end">
        <Button className="bg-gradient-to-r from-emerald-500 to-teal-600 text-white">
          <DollarSign className="h-4 w-4 mr-2" />
          Proceed to Checkout
        </Button>
      </div>
    </div>
  );
}
