import { redirect } from 'next/navigation';

/**
 * Home Page
 * 
 * Redirects to the appropriate page based on user state.
 * - Not authenticated → Landing page (future)
 * - Authenticated, no details → Welcome details page
 * - Authenticated, details done → Dashboard
 */
export default function HomePage() {
  // For now, redirect to welcome details page
  // In production, this would check auth state and redirect accordingly
  redirect('/welcome/details');
}
