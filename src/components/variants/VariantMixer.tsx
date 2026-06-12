"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PRICES, VARIANT_LIMITS } from "@/lib/config";
import {
  Zap,
  TrendingUp,
  Sparkles,
  Plus,
  Minus,
  Loader2,
  AlertTriangle,
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

interface VariantData {
  id: string;
  variant_type: string;
  status: string;
  ticket_limit: number;
  tickets_used: number;
  ai_pipeline_steps: string[];
  concurrent_ai: number;
  created_at: string | null;
}

export function VariantMixer() {
  const [variants, setVariants] = useState<VariantData[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    loadVariants();
  }, []);

  const loadVariants = async () => {
    try {
      const res = await fetch("/api/variants/list");
      if (res.ok) {
        const data = await res.json();
        setVariants(data.variants || []);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (variantType: string) => {
    setAdding(variantType);
    try {
      const res = await fetch("/api/variants/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_type: variantType }),
      });
      if (res.ok) {
        await loadVariants();
      }
    } catch {
      // Error handled silently
    } finally {
      setAdding(null);
    }
  };

  const handleRemove = async (variantId: string) => {
    if (!confirm("This variant will be scheduled for removal at the next billing cycle. Continue?")) return;
    setRemoving(variantId);
    try {
      const res = await fetch("/api/variants/remove", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: variantId }),
      });
      if (res.ok) {
        await loadVariants();
      }
    } catch {
      // Error handled silently
    } finally {
      setRemoving(null);
    }
  };

  const totalCost = useMemo(
    () => variants.filter((v) => v.status !== "scheduled_removal").reduce((sum, v) => sum + (variantPrices[v.variant_type] || 0), 0),
    [variants]
  );

  const totalTickets = useMemo(
    () => variants.filter((v) => v.status !== "scheduled_removal").reduce((sum, v) => sum + v.ticket_limit, 0),
    [variants]
  );

  const activeVariantTypes = variants.filter((v) => v.status !== "scheduled_removal").map((v) => v.variant_type);
  const availableToAdd = (["mini", "parwa", "parwa_high"] as const).filter((type) => !activeVariantTypes.includes(type));

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-emerald-500" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Variant Mixer
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Active Variants */}
          {variants.map((variant) => {
            const Icon = variantIcons[variant.variant_type] || Zap;
            const limits = VARIANT_LIMITS[variant.variant_type as keyof typeof VARIANT_LIMITS];
            const usagePct = limits ? (variant.tickets_used / limits.tickets) * 100 : 0;
            const isScheduledRemoval = variant.status === "scheduled_removal";

            return (
              <div
                key={variant.id}
                className={`p-4 rounded-lg border ${
                  isScheduledRemoval
                    ? "border-amber-300 bg-amber-50/50 dark:border-amber-700 dark:bg-amber-950/20"
                    : "border-border bg-background"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-emerald-500" />
                    <span className="font-medium text-sm">{variantNames[variant.variant_type] || variant.variant_type}</span>
                    {isScheduledRemoval && (
                      <Badge variant="secondary" className="text-[10px] text-amber-600">
                        <AlertTriangle className="h-3 w-3 mr-0.5" />
                        Scheduled Removal
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold">
                      ${((variantPrices[variant.variant_type] || 0) / 100).toFixed(2)}/mo
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs text-destructive hover:text-destructive"
                      disabled={removing === variant.id}
                      onClick={() => handleRemove(variant.id)}
                    >
                      {removing === variant.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Minus className="h-3 w-3" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Ticket Usage Bar */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Tickets: {variant.tickets_used} / {variant.ticket_limit.toLocaleString()}</span>
                    <span>{usagePct.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        usagePct > 90
                          ? "bg-destructive"
                          : usagePct > 70
                          ? "bg-amber-500"
                          : "bg-gradient-to-r from-emerald-500 to-teal-500"
                      }`}
                      style={{ width: `${Math.min(usagePct, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Multi-variant Rules */}
                <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                  <span>AI Steps: {Array.isArray(variant.ai_pipeline_steps) ? variant.ai_pipeline_steps.length : variant.ai_pipeline_steps}</span>
                  <span>Concurrent: {variant.concurrent_ai}</span>
                </div>
              </div>
            );
          })}

          {/* Add Variant */}
          {availableToAdd.length > 0 && (
            <div className="flex gap-2 pt-2">
              {availableToAdd.map((type) => (
                <Button
                  key={type}
                  variant="outline"
                  size="sm"
                  className="text-xs flex-1"
                  disabled={adding === type}
                  onClick={() => handleAdd(type)}
                >
                  {adding === type ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <Plus className="h-3 w-3 mr-1" />
                  )}
                  Add {variantNames[type]}
                </Button>
              ))}
            </div>
          )}

          {/* Total */}
          <div className="p-3 bg-muted/50 rounded-lg">
            <div className="flex justify-between text-sm">
              <span className="font-medium">Total Monthly Cost</span>
              <span className="font-bold">${(totalCost / 100).toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>Total ticket capacity</span>
              <span>{totalTickets.toLocaleString()}/mo</span>
            </div>
          </div>

          {/* D13 Compliance Notice */}
          <p className="text-xs text-emerald-600 dark:text-emerald-400">
            Need more tickets? Add another variant to increase your capacity.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
