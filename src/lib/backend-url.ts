/**
 * PARWA — Backend URL Helper
 *
 * Centralizes the backend URL for all API proxy routes.
 *
 * Priority:
 * 1. BACKEND_URL env var (set on Vercel to https://parwa-backend.onrender.com)
 * 2. NEXT_PUBLIC_API_URL (set in .env.production — but may point to frontend on some setups)
 * 3. Fallback: http://localhost:8000 (local development)
 *
 * IMPORTANT: NEXT_PUBLIC_API_URL is baked into client JS at build time.
 * For server-side proxy routes, we prefer BACKEND_URL which is a runtime env var.
 */

export function getBackendUrl(): string {
  // Runtime env var — can be changed without rebuilding
  if (process.env.BACKEND_URL) {
    return process.env.BACKEND_URL;
  }

  // If NEXT_PUBLIC_API_URL points to the frontend itself (parwa.ai, parwa.buzz),
  // don't use it for backend proxying — that would create infinite loops.
  const publicUrl = process.env.NEXT_PUBLIC_API_URL || '';
  const frontendHosts = ['parwa.ai', 'parwa.buzz', 'localhost:3000', 'vercel.app'];
  const isFrontendUrl = frontendHosts.some(
    (host) => publicUrl.includes(host)
  );

  if (publicUrl && !isFrontendUrl) {
    return publicUrl;
  }

  // Default: local backend
  return 'http://localhost:8000';
}
