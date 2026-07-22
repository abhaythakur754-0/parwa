import { redirect } from 'next/navigation';

/** /dashboard/calls — REMOVED (redundant with ticket channel field) */
export default function CallsPageRedirect() {
  redirect('/dashboard/tickets');
}
