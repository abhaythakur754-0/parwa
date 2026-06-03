/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  allowedDevOrigins: ['127.0.0.1', 'localhost'],

  // ── Production API Proxy ──
  // Vercel → Render backend: rewrites /api/backend/* to the FastAPI server
  // This avoids CORS issues in production.
  // The NEXT_PUBLIC_API_URL env var points to the Render backend directly.
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    // Only add rewrites if not pointing to localhost (production)
    if (backendUrl.includes('localhost')) return [];
    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/ws',
        destination: `${backendUrl}/ws`,
      },
    ];
  },
  // Turbopack disabled — causes panics on Windows with large projects
  // Re-enable with: turbopack: {}, and run: next dev --turbopack
  // turbopack: {},

  // ── M-26 FIX: Security headers on all responses ──
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-XSS-Protection",
            value: "0", // Modern browsers handle XSS via CSP
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https: *.googleusercontent.com",
              "connect-src 'self' https://parwa-backend.onrender.com https://generativelanguage.googleapis.com https://api.cerebras.ai https://api.groq.com",
              "frame-src https://accounts.google.com",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
      // Cache-Control for auth endpoints — never cache
      {
        source: "/api/auth/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "no-store, no-cache, must-revalidate, proxy-revalidate",
          },
          {
            key: "Pragma",
            value: "no-cache",
          },
          {
            key: "Expires",
            value: "0",
          },
        ],
      },
    ];
  },
};

// ── Phase 6: Sentry webpack integration ──
// Wraps the Next.js config with Sentry's source map upload and
// build-time configuration. Gracefully falls back if @sentry/nextjs
// is not installed (e.g., during initial setup before npm install).
let exportedConfig = nextConfig;

try {
  const { withSentryConfig } = await import('@sentry/nextjs');

  const sentryWebpackPluginOptions = {
    silent: true,          // Suppresses source map upload logs
    hideSourceMaps: true,  // Prevents source maps from being publicly accessible
  };

  exportedConfig = withSentryConfig(nextConfig, sentryWebpackPluginOptions);
} catch {
  // @sentry/nextjs not installed yet — export config without Sentry wrapper
}

export default exportedConfig;
