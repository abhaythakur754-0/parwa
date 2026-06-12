"use client";

import { useState, useEffect, useMemo } from "react";
import { VARIANT_PRICES, VARIANT_LIMITS, VARIANT_DISPLAY_NAMES, type VariantTier } from "@/lib/pricing-config";
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
  mini_parwa: Zap,
  parwa: TrendingUp,
  parwa_high: Sparkles,
};

const variantNames: Record<string, string> = {
  mini: "Mini PARWA",
  mini_parwa: "Mini PARWA",
  parwa: "PARWA",
  parwa_high: "PARWA High",
};

/** Map from backend variant_type to pricing-config VariantTier key */
function toTier(v: string): VariantTier {
  if (v === 'mini' || v === 'mini_parwa' || v === 'starter') return 'starter';
  if (v === 'parwa_high' || v === 'high') return 'high';
  return 'growth';
}

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
    () => variants.filter((v) => v.status !== "scheduled_removal").reduce((sum, v) => sum + (VARIANT_PRICES[toTier(v.variant_type)] || 0), 0),
    [variants]
  );

  const totalTickets = useMemo(
    () => variants.filter((v) => v.status !== "scheduled_removal").reduce((sum, v) => sum + v.ticket_limit, 0),
    [variants]
  );

  const activeVariantTypes = variants.filter((v) => v.status !== "scheduled_removal").map((v) => v.variant_type);
  const availableToAdd = (["mini_parwa", "parwa", "parwa_high"] as const).filter((type) => !activeVariantTypes.includes(type));

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Active Variants */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
          <Zap className="w-4 h-4 text-orange-400" />
          <h3 className="text-sm font-semibold text-white">Variant Mixer</h3>
        </div>
        <div className="p-4 space-y-3">
          {variants.length === 0 && (
            <div className="text-center py-8">
              <Zap className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No active variants</p>
              <p className="text-xs text-zinc-600">Add a variant below to get started</p>
            </div>
          )}

          {variants.map((variant) => {
            const Icon = variantIcons[variant.variant_type] || Zap;
            const tier = toTier(variant.variant_type);
            const limits = VARIANT_LIMITS[tier];
            const usagePct = limits ? (variant.tickets_used / limits.monthlyTickets) * 100 : 0;
            const isScheduledRemoval = variant.status === "scheduled_removal";

            return (
              <div
                key={variant.id}
                className={`p-4 rounded-lg border ${
                  isScheduledRemoval
                    ? "border-amber-500/20 bg-amber-500/5"
                    : "border-white/[0.06] bg-white/[0.02]"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-orange-400" />
                    <span className="font-medium text-sm text-white">{variantNames[variant.variant_type] || variant.variant_type}</span>
                    {isScheduledRemoval && (
                      <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 uppercase tracking-wider">
                        <AlertTriangle className="h-3 w-3" />
                        Scheduled Removal
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-white">
                      ${VARIANT_PRICES[tier].toLocaleString()}/mo
                    </span>
                    <button
                      onClick={() => handleRemove(variant.id)}
                      disabled={removing === variant.id}
                      className="h-7 w-7 rounded-lg flex items-center justify-center text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                    >
                      {removing === variant.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Minus className="h-3 w-3" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Ticket Usage Bar */}
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs text-zinc-500">
                    <span>Tickets: {variant.tickets_used} / {variant.ticket_limit.toLocaleString()}</span>
                    <span>{usagePct.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-white/[0.04] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        usagePct > 90
                          ? "bg-red-500"
                          : usagePct > 70
                          ? "bg-amber-500"
                          : "bg-gradient-to-r from-orange-500 to-amber-400"
                      }`}
                      style={{ width: `${Math.min(usagePct, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Multi-variant Rules */}
                <div className="flex gap-4 mt-2 text-xs text-zinc-500">
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
                <button
                  key={type}
                  onClick={() => handleAdd(type)}
                  disabled={adding === type}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-white/[0.06] bg-white/[0.02] text-zinc-400 hover:text-white hover:border-orange-500/30 hover:bg-orange-500/5 transition-colors disabled:opacity-50"
                >
                  {adding === type ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Plus className="h-3 w-3" />
                  )}
                  Add {variantNames[type] || type}
                </button>
              ))}
            </div>
          )}

          {/* Total */}
          <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <div className="flex justify-between text-sm">
              <span className="font-medium text-zinc-400">Total Monthly Cost</span>
              <span className="font-bold text-white">${totalCost.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-xs text-zinc-500 mt-1">
              <span>Total ticket capacity</span>
              <span>{totalTickets.toLocaleString()}/mo</span>
            </div>
          </div>

          {/* D13 Compliance Notice */}
          <p className="text-xs text-orange-400/60">
            Need more tickets? Add another variant to increase your capacity.
          </p>
        </div>
      </div>
    </div>
  );
}
