/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  reactStrictMode: false,
  allowedDevOrigins: ['127.0.0.1', 'localhost'],

  // ── Source maps for debugging production TDZ errors ────────────────
  productionBrowserSourceMaps: true,

  // ── Transpile ESM-only packages that cause TDZ errors ──────────────
  // @paddle/paddle-js is ESM-only and has internal circular references
  // that cause "Cannot access 'X' before initialization" in minified builds.
  // Transpiling it to CJS-compatible code avoids the TDZ issue.
  transpilePackages: ['@paddle/paddle-js'],

  // ── Optimize ESM package imports to reduce bundle size ──────────────
  // lucide-react is imported in 80+ files; optimizePackageImports
  // tree-shakes unused icons and reduces the shared chunk size.
  experimental: {
    optimizePackageImports: ['lucide-react', 'react-hot-toast'],
  },

  turbopack: {
    root: "/home/z/my-project",
  },

  // ── Webpack config ──
  // @paddle/paddle-js has internal TDZ issues with static imports.
  // The dynamic import() in src/lib/paddle.ts handles this at runtime,
  // but we also need webpack fallbacks for Node.js modules that
  // @paddle/paddle-js tries to import in the browser.
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
        child_process: false,
      };
    }
    return config;
  },

  // Webpack: add fallbacks for Node.js modules that some client-side
  // packages (like @paddle/paddle-js) reference during evaluation.
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        net: false,
        tls: false,
      };
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
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob: https: *.googleusercontent.com",
              "connect-src 'self' https://generativelanguage.googleapis.com https://api.cerebras.ai https://api.groq.com https://parwa-backend.onrender.com wss://parwa-backend.onrender.com https://oauth2.googleapis.com https://accounts.google.com",
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

export default nextConfig;
