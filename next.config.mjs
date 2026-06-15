/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  // Note: 'eslint' key is not supported in Next.js 16+; use next lint CLI instead

  reactStrictMode: false,
  allowedDevOrigins: ['127.0.0.1', 'localhost'],

  // ── Source maps for debugging production TDZ errors ────────────────
  productionBrowserSourceMaps: true,

  // ── @paddle/paddle-js is NOT imported via npm anymore ─────────────
  // We load Paddle.js entirely from CDN (script tag). The npm package
  // has TDZ issues with all bundlers. See src/lib/paddle.ts for details.
  // transpilePackages is intentionally EMPTY — do not add paddle-js here.

  // ── Optimize ESM package imports to reduce bundle size ──────────────
  // lucide-react is imported in 80+ files; optimizePackageImports
  // tree-shakes unused icons and reduces the shared chunk size.
  experimental: {
    optimizePackageImports: ['lucide-react', 'react-hot-toast'],
  },

  // ── Turbopack config (Next.js 16 default) ──
  // @paddle/paddle-js is excluded from the bundle entirely — we load via CDN.
  turbopack: {
    resolveAlias: {
      '@paddle/paddle-js': { browser: './src/lib/paddle-empty.js' },
    },
  },

  // ── Webpack config ──
  // @paddle/paddle-js is completely excluded from the bundle.
  // We load it from CDN instead. The externals rule below ensures
  // that even if something tries to import it, webpack won't bundle it.
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        child_process: false,
      };

      // Completely exclude @paddle/paddle-js from the client bundle.
      // If any import somehow references it, resolve to empty module.
      if (!config.resolve.alias) config.resolve.alias = {};
      config.resolve.alias['@paddle/paddle-js'] = false;
    }
    return config;
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
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com https://cdn.paddle.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https: *.googleusercontent.com",
              "connect-src 'self' https://generativelanguage.googleapis.com https://api.cerebras.ai https://api.groq.com https://parwa-backend.onrender.com wss://parwa-backend.onrender.com https://oauth2.googleapis.com https://accounts.google.com https://*.paddle.com https://sandbox-api.paddle.com",
              "frame-src https://accounts.google.com https://*.paddle.com",
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
