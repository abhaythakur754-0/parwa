import { redirect } from 'next/navigation';

/**
 * /dashboard — REDIRECTED to /dashboard/tickets
 *
 * Dashboard and Tickets have been combined into ONE page.
 * Everything (Welcome Card, ROI, Variants, Tickets) lives on /dashboard/tickets.
 */
export default function DashboardRedirect() {
  redirect('/dashboard/tickets');
}
