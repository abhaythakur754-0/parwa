import { redirect } from 'next/navigation';

/**
 * /pricing → redirect to /models
 * The ModelsPage is the authoritative pricing page with industry-specific variants.
 */
export default function PricingRedirect() {
  redirect('/models');
}
