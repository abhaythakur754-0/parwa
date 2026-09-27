import { redirect } from 'next/navigation';

/**
 * /dashboard/cost-breakdown — REDIRECTED to /dashboard/billing
 * Cost Breakdown has been combined into the Billing page.
 */
export default function CostBreakdownRedirect() {
  redirect('/dashboard/billing');
}
