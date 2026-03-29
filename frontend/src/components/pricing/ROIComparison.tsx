"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/utils/utils";
import { TrendingUp, Clock, DollarSign, Users, ArrowUpRight } from "lucide-react";

export interface ROIData {
  variantId: "mini" | "parwa" | "parwa_high";
  name: string;
  monthlyCost: number;
  timeSavedHours: number;
  costSavings: number;
  managerTimeSaved: number;
  roi: number;
}

export interface ROIComparisonProps {
  data?: ROIData[];
  currentCost?: number;
  currentTeamSize?: number;
  ticketVolume?: number;
  className?: string;
}

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  trend?: number;
  color?: string;
}

function MetricCard({ icon, label, value, unit, trend, color }: MetricCardProps) {
  return (
    <div className="p-4 rounded-lg bg-muted/50 space-y-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className="flex items-end gap-1">
        <span className={cn("text-2xl font-bold", color)}>{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
      {trend !== undefined && (
        <div className={cn("flex items-center gap-1 text-sm", trend >= 0 ? "text-green-600" : "text-red-600")}>
          <ArrowUpRight className={cn("h-4 w-4", trend < 0 && "rotate-180")} />
          {Math.abs(trend)}% vs manual
        </div>
      )}
    </div>
  );
}

const DEFAULT_ROI_DATA: ROIData[] = [
  {
    variantId: "mini",
    name: "Mini PARWA",
    monthlyCost: 999,
    timeSavedHours: 20,
    costSavings: 800,
    managerTimeSaved: 5,
    roi: 80,
  },
  {
    variantId: "parwa",
    name: "PARWA Junior",
    monthlyCost: 2499,
    timeSavedHours: 45,
    costSavings: 1800,
    managerTimeSaved: 12,
    roi: 72,
  },
  {
    variantId: "parwa_high",
    name: "PARWA High",
    monthlyCost: 3999,
    timeSavedHours: 80,
    costSavings: 3200,
    managerTimeSaved: 20,
    roi: 80,
  },
];

export function ROIComparison({
  data = DEFAULT_ROI_DATA,
  currentCost = 3000,
  currentTeamSize = 3,
  ticketVolume = 1000,
  className,
}: ROIComparisonProps) {
  const [selectedVariant, setSelectedVariant] = React.useState<string>("parwa");

  const selectedData = data.find((d) => d.variantId === selectedVariant) || data[1];

  // Calculate totals
  const totalTimeSaved = selectedData.timeSavedHours;
  const totalCostSavings = selectedData.costSavings;
  const managerHoursSaved = selectedData.managerTimeSaved;
  const roiPercentage = selectedData.roi;

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="text-center space-y-2">
        <h3 className="text-lg font-semibold flex items-center justify-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          ROI Comparison
        </h3>
        <p className="text-sm text-muted-foreground">
          See how much you can save with PARWA vs. manual support
        </p>
      </div>

      {/* Current State Input Display */}
      <Card className="bg-muted/30">
        <CardContent className="pt-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-xs text-muted-foreground">Current Cost</p>
              <p className="text-lg font-semibold">${currentCost.toLocaleString()}/mo</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Team Size</p>
              <p className="text-lg font-semibold">{currentTeamSize} agents</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Ticket Volume</p>
              <p className="text-lg font-semibold">{ticketVolume.toLocaleString()}/mo</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Variant Tabs */}
      <div className="flex rounded-lg border p-1 bg-muted/30">
        {data.map((variant) => (
          <button
            key={variant.variantId}
            type="button"
            onClick={() => setSelectedVariant(variant.variantId)}
            className={cn(
              "flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all",
              selectedVariant === variant.variantId
                ? "bg-background shadow-sm"
                : "hover:bg-muted"
            )}
          >
            {variant.name}
          </button>
        ))}
      </div>

      {/* Metrics Grid */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={<Clock className="h-4 w-4" />}
          label="Hours Saved/Month"
          value={totalTimeSaved}
          unit="hrs"
          trend={75}
          color="text-blue-600"
        />
        <MetricCard
          icon={<DollarSign className="h-4 w-4" />}
          label="Cost Savings"
          value={`$${totalCostSavings.toLocaleString()}`}
          unit="/mo"
          trend={60}
          color="text-green-600"
        />
        <MetricCard
          icon={<Users className="h-4 w-4" />}
          label="Manager Time Saved"
          value={managerHoursSaved}
          unit="hrs/wk"
          trend={40}
          color="text-purple-600"
        />
        <MetricCard
          icon={<TrendingUp className="h-4 w-4" />}
          label="ROI"
          value={roiPercentage}
          unit="%"
          color="text-primary"
        />
      </div>

      {/* Side-by-side Comparison Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Detailed Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 font-medium text-muted-foreground">
                    Metric
                  </th>
                  {data.map((variant) => (
                    <th
                      key={variant.variantId}
                      className={cn(
                        "text-right py-2 font-medium",
                        selectedVariant === variant.variantId
                          ? "text-primary"
                          : "text-muted-foreground"
                      )}
                    >
                      {variant.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-3 text-muted-foreground">Monthly Cost</td>
                  {data.map((variant) => (
                    <td
                      key={variant.variantId}
                      className={cn(
                        "text-right py-3 font-medium",
                        selectedVariant === variant.variantId && "text-primary"
                      )}
                    >
                      ${variant.monthlyCost}
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-3 text-muted-foreground">Hours Saved</td>
                  {data.map((variant) => (
                    <td
                      key={variant.variantId}
                      className={cn(
                        "text-right py-3 font-medium",
                        selectedVariant === variant.variantId && "text-primary"
                      )}
                    >
                      {variant.timeSavedHours} hrs
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-3 text-muted-foreground">Cost Savings</td>
                  {data.map((variant) => (
                    <td
                      key={variant.variantId}
                      className={cn(
                        "text-right py-3 font-medium",
                        selectedVariant === variant.variantId && "text-primary"
                      )}
                    >
                      ${variant.costSavings.toLocaleString()}
                    </td>
                  ))}
                </tr>
                <tr className="border-b">
                  <td className="py-3 text-muted-foreground">Manager Time Saved</td>
                  {data.map((variant) => (
                    <td
                      key={variant.variantId}
                      className={cn(
                        "text-right py-3 font-medium",
                        selectedVariant === variant.variantId && "text-primary"
                      )}
                    >
                      {variant.managerTimeSaved} hrs/wk
                    </td>
                  ))}
                </tr>
                <tr className="bg-muted/30">
                  <td className="py-3 font-semibold">ROI</td>
                  {data.map((variant) => (
                    <td
                      key={variant.variantId}
                      className={cn(
                        "text-right py-3 font-bold",
                        selectedVariant === variant.variantId
                          ? "text-primary"
                          : "text-green-600"
                      )}
                    >
                      {variant.roi}%
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Summary Card */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-center sm:text-left">
              <p className="text-sm text-muted-foreground">With {selectedData.name}</p>
              <p className="text-xl font-bold">
                You save ${totalCostSavings.toLocaleString()}/month
              </p>
              <p className="text-sm text-muted-foreground">
                and {totalTimeSaved} hours of work
              </p>
            </div>
            <div className="text-center">
              <div className="text-4xl font-bold text-primary">{roiPercentage}%</div>
              <p className="text-sm text-muted-foreground">Return on Investment</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ROIComparison;
