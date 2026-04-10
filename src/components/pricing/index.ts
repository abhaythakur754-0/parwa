/**
 * Pricing Components
 *
 * Components:
 * - IndustrySelector: Select from 4 industries (E-commerce, SaaS, Logistics, Others)
 * - VariantCard: Glass morphism variant card with features, demo/chat/quantity
 * - QuantitySelector: [-] N [+] quantity control with premium styling
 * - TotalSummary: Premium glass bill summary with checkout button
 * - SmartBundleVisualizer: Interactive ticket volume + industry recommendation tool
 * - AntiArbitrageMatrix: 2× Starter vs 1× Growth comparison table
 *
 * Type Exports:
 * - Industry: 'ecommerce' | 'saas' | 'logistics' | 'others'
 * - PricingVariant: Variant data shape
 * - IndustryOption: Industry option data shape
 */

export { IndustrySelector, industries } from './IndustrySelector';
export type { Industry, IndustryOption } from './IndustrySelector';

export { VariantCard } from './VariantCard';
export type { PricingVariant } from './VariantCard';

export { QuantitySelector } from './QuantitySelector';

export { TotalSummary } from './TotalSummary';

export { SmartBundleVisualizer } from './SmartBundleVisualizer';

export { AntiArbitrageMatrix } from './AntiArbitrageMatrix';
