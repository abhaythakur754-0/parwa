/**
 * Pricing Components
 *
 * Day 6: Pricing Page Components
 *
 * Components:
 * - IndustrySelector: Select from 4 industries
 * - VariantCard: Display pricing variant with quantity selector
 * - QuantitySelector: [-] N [+] quantity control
 * - TotalSummary: Bill summary with checkout button
 */

export { IndustrySelector, industries } from './IndustrySelector';
export type { Industry, IndustryOption } from './IndustrySelector';

export { VariantCard } from './VariantCard';
export type { PricingVariant } from './VariantCard';

export { QuantitySelector } from './QuantitySelector';

export { TotalSummary } from './TotalSummary';
