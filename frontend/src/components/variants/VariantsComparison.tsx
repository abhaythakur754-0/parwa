"use client";

import * as React from "react";
import { cn } from "@/utils/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Check, X } from "lucide-react";

/**
 * Comparison feature row definition.
 */
export interface ComparisonFeature {
  /** Feature name */
  name: string;
  /** Feature category for grouping */
  category?: string;
  /** Mini PARWA value */
  mini: string | boolean;
  /** PARWA Junior value */
  junior: string | boolean;
  /** PARWA High value */
  high: string | boolean;
}

/**
 * Variants comparison table props.
 */
export interface VariantsComparisonProps {
  /** Additional CSS classes */
  className?: string;
  /** Whether to highlight recommended tier */
  highlightRecommended?: boolean;
  /** Callback when a variant is clicked */
  onVariantClick?: (variantId: string) => void;
}

/**
 * All comparison features for the variants table.
 */
const COMPARISON_FEATURES: ComparisonFeature[] = [
  // Pricing
  { name: "Monthly Price", category: "Pricing", mini: "$999", junior: "$2,499", high: "$3,999" },
  { name: "Annual Discount", category: "Pricing", mini: "10%", junior: "15%", high: "20%" },

  // AI Capabilities
  { name: "AI Tier", category: "AI", mini: "Light", junior: "Medium", high: "Heavy" },
  { name: "Learning from Feedback", category: "AI", mini: false, junior: true, high: true },
  { name: "Churn Prediction", category: "AI", mini: false, junior: false, high: true },

  // Concurrency
  { name: "Max Concurrent Calls", category: "Limits", mini: "2", junior: "5", high: "10" },
  { name: "Max Teams", category: "Limits", mini: "1", junior: "2", high: "5" },

  // Financial
  { name: "Refund Limit", category: "Financial", mini: "$50", junior: "$500", high: "$2000" },
  { name: "Can Execute Refunds", category: "Financial", mini: false, junior: false, high: true },
  { name: "Escalation Threshold", category: "Financial", mini: "70%", junior: "60%", high: "50%" },

  // Channels
  { name: "FAQ Support", category: "Channels", mini: true, junior: true, high: true },
  { name: "Email Support", category: "Channels", mini: true, junior: true, high: true },
  { name: "Chat Support", category: "Channels", mini: true, junior: true, high: true },
  { name: "SMS Support", category: "Channels", mini: true, junior: true, high: true },
  { name: "Voice Support", category: "Channels", mini: false, junior: true, high: true },
  { name: "Video Support", category: "Channels", mini: false, junior: true, high: true },

  // Features
  { name: "Analytics Dashboard", category: "Features", mini: false, junior: true, high: true },
  { name: "APPROVE/REVIEW/DENY", category: "Features", mini: false, junior: true, high: true },
  { name: "HIPAA Compliance", category: "Features", mini: false, junior: false, high: true },
  { name: "Priority Support", category: "Features", mini: false, junior: false, high: true },
];

/**
 * Render a cell value with check/x or text.
 */
function renderCellValue(value: string | boolean) {
  if (typeof value === "boolean") {
    return value ? (
      <Check className="h-4 w-4 text-green-500 mx-auto" aria-label="Included" />
    ) : (
      <X className="h-4 w-4 text-muted-foreground mx-auto" aria-label="Not included" />
    );
  }
  return <span className="font-medium">{value}</span>;
}

/**
 * Variants comparison table component.
 *
 * Displays a side-by-side comparison of all PARWA variants:
 * - Mini PARWA (Light tier)
 * - PARWA Junior (Medium tier) - highlighted as recommended
 * - PARWA High (Heavy tier)
 *
 * Features are grouped by category for easy comparison.
 *
 * @example
 * ```tsx
 * <VariantsComparison
 *   highlightRecommended={true}
 *   onVariantClick={(id) => handleSelect(id)}
 * />
 * ```
 */
export function VariantsComparison({
  className,
  highlightRecommended = true,
  onVariantClick,
}: VariantsComparisonProps) {
  // Group features by category
  const categories = React.useMemo(() => {
    const cats: Record<string, ComparisonFeature[]> = {};
    COMPARISON_FEATURES.forEach((feature) => {
      const category = feature.category || "General";
      if (!cats[category]) {
        cats[category] = [];
      }
      cats[category].push(feature);
    });
    return cats;
  }, []);

  return (
    <div className={cn("w-full overflow-auto", className)} data-testid="variants-comparison">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[200px] font-semibold">Feature</TableHead>
            <TableHead
              className={cn(
                "text-center cursor-pointer hover:bg-muted/50 transition-colors",
                onVariantClick && "cursor-pointer"
              )}
              onClick={() => onVariantClick?.("mini")}
            >
              <div className="flex flex-col items-center gap-1">
                <span className="font-semibold">Mini PARWA</span>
                <Badge variant="outline" className="text-xs">Light</Badge>
              </div>
            </TableHead>
            <TableHead
              className={cn(
                "text-center cursor-pointer hover:bg-muted/50 transition-colors",
                highlightRecommended && "bg-primary/5"
              )}
              onClick={() => onVariantClick?.("parwa")}
            >
              <div className="flex flex-col items-center gap-1">
                <span className="font-semibold">PARWA Junior</span>
                <Badge variant="secondary" className="text-xs">Medium</Badge>
                {highlightRecommended && (
                  <Badge variant="default" className="text-xs">Recommended</Badge>
                )}
              </div>
            </TableHead>
            <TableHead
              className="text-center cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => onVariantClick?.("parwa_high")}
            >
              <div className="flex flex-col items-center gap-1">
                <span className="font-semibold">PARWA High</span>
                <Badge variant="default" className="text-xs">Heavy</Badge>
              </div>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(categories).map(([category, features]) => (
            <React.Fragment key={category}>
              {/* Category header row */}
              <TableRow className="bg-muted/30 hover:bg-muted/30">
                <TableCell
                  colSpan={4}
                  className="font-semibold text-muted-foreground text-sm uppercase tracking-wide"
                >
                  {category}
                </TableCell>
              </TableRow>
              {/* Feature rows */}
              {features.map((feature) => (
                <TableRow key={feature.name}>
                  <TableCell className="font-medium">{feature.name}</TableCell>
                  <TableCell className="text-center">
                    {renderCellValue(feature.mini)}
                  </TableCell>
                  <TableCell
                    className={cn(
                      "text-center",
                      highlightRecommended && "bg-primary/5"
                    )}
                  >
                    {renderCellValue(feature.junior)}
                  </TableCell>
                  <TableCell className="text-center">
                    {renderCellValue(feature.high)}
                  </TableCell>
                </TableRow>
              ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/**
 * Get all comparison features.
 */
export function getComparisonFeatures() {
  return COMPARISON_FEATURES;
}

export default VariantsComparison;
