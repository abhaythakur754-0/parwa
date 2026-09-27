import { redirect } from 'next/navigation';

/** /dashboard/monitoring — REMOVED (no real backend, waste of LLM tokens) */
export default function MonitoringPageRedirect() {
  redirect('/dashboard/tickets');
}
