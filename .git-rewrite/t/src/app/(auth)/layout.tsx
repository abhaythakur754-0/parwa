/**
 * Auth Layout
 *
 * Layout for all auth pages (login, signup, forgot-password, reset-password).
 * AuthProvider is already in the root layout — no need to double-wrap.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
