import path from "path";

// X-Frame-Options is a production-only protection (anti-clickjacking).
// In development (sandbox preview panel) the site is embedded in an iframe,
// so the header must be skipped or browsers show "refused to connect".
const isProduction = process.env.NODE_ENV === "production";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  outputFileTracingIncludes: {
    "/api/chat": ["./backend/app/data/jarvis_knowledge/*.json"],
  },
  // FIX (live UI test 2026-10-29): stale links/bookmarks to bare paths
  // landed on 404 — the real pages live under /dashboard/*.
  async redirects() {
    return [
      { source: "/escalations", destination: "/dashboard/escalations", permanent: false },
      { source: "/settings", destination: "/dashboard/settings", permanent: false },
      { source: "/integrations", destination: "/dashboard/integrations", permanent: false },
      { source: "/billing", destination: "/dashboard/billing", permanent: false },
      { source: "/knowledge", destination: "/dashboard/knowledge", permanent: false },
      { source: "/tickets", destination: "/dashboard/tickets", permanent: false },
    ];
  },
  // TypeScript errors must fail the production build.
  reactStrictMode: false,
  allowedDevOrigins: ['127.0.0.1', 'localhost', '*.space-z.ai', 'space-z.ai'],
  turbopack: {
    root: path.dirname(new URL(import.meta.url).pathname),
  },


  // ── Security headers on all responses ──
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          ...(isProduction
            ? [
                {
                  key: "X-Frame-Options",
                  value: "DENY",
                },
              ]
            : []),
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
              "camera=(), microphone=(), geolocation=(), usb=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://checkout.razorpay.com https://api.razorpay.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https: *.googleusercontent.com *.razorpay.com *.amazonaws.com",
              "connect-src 'self' https://generativelanguage.googleapis.com https://api.cerebras.ai https://api.groq.com https://parwa-backend.onrender.com wss://parwa-backend.onrender.com https://oauth2.googleapis.com https://accounts.google.com https://api.razorpay.com https://checkout.razorpay.com",
              "frame-src https://accounts.google.com https://api.razorpay.com https://checkout.razorpay.com",
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

export default nextConfig;
