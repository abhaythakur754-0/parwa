/**
 * PARWA — Backend URL Helper
 *
 * Centralizes the backend URL for all API proxy routes.
 *
 * Priority:
 * 1. BACKEND_URL env var (set on Vercel to override)
 * 2. Production default: https://parwa-backend.onrender.com
 * 3. NEXT_PUBLIC_API_URL if it's not a frontend URL
 * 4. Fallback: http://localhost:8000 (local development)
 *
 * IMPORTANT: NEXT_PUBLIC_API_URL is baked into client JS at build time.
 * For server-side proxy routes, we prefer BACKEND_URL which is a runtime env var.
 */

export function getBackendUrl(): string {
  // Runtime env var — can be changed without rebuilding
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL;
  }

  // In production on Vercel, default to the backend on Render
  if (process.env.VERCEL || process.env.NODE_ENV === 'production') {
    return 'https://parwa-backend.onrender.com';
  }

  // If NEXT_PUBLIC_API_URL points to the frontend itself (parwa.buzz, parwa.vercel.app),
  // don't use it for backend proxying — that would create infinite loops.
  const publicUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const frontendHosts = ['parwa.buzz', 'parwa.vercel.app', 'localhost:3000', 'vercel.app'];
  const isFrontendUrl = frontendHosts.some(
    (host) => publicUrl.includes(host)
  );

  if (publicUrl && !isFrontendUrl) {
    return publicUrl;
  }

  // Default: local backend
  return 'http://localhost:8000';
}
