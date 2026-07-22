import { redirect } from 'next/navigation';

/** /dashboard/variants — REDIRECTED to /dashboard/tickets (combined) */
export default function VariantsPageRedirect() {
  redirect('/dashboard/tickets');
}
