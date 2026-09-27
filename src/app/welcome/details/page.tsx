import { redirect } from 'next/navigation';

/** /welcome/details — DELETED. Redirects to /onboarding */
export default function DetailsRedirect() {
  redirect('/onboarding');
}
