/**
 * PARWA Variant Components
 *
 * Export all variant card components and utilities.
 */

// Base component
export { VariantCard } from "./VariantCard";
export type { VariantCardProps, VariantFeature } from "./VariantCard";

// Specific variant cards
export { MiniCard, getMiniConfig } from "./MiniCard";
export type { MiniCardProps } from "./MiniCard";

export { ParwaJuniorCard, getParwaJuniorConfig } from "./ParwaJuniorCard";
export type { ParwaJuniorCardProps } from "./ParwaJuniorCard";

export { ParwaHighCard, getParwaHighConfig } from "./ParwaHighCard";
export type { ParwaHighCardProps } from "./ParwaHighCard";

// Comparison component
export { VariantsComparison, getComparisonFeatures } from "./VariantsComparison";
export type { VariantsComparisonProps, ComparisonFeature } from "./VariantsComparison";
