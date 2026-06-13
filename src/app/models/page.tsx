import { redirect } from 'next/navigation';

/**
 * /models → redirect to /pricing
 * The ModelsPage has been removed. Pricing is handled by /pricing page.
 */
export default function ModelsRedirect() {
  redirect('/pricing');
}
