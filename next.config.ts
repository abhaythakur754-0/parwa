import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingIncludes: {
    '/api/chat': ['./backend/app/data/jarvis_knowledge/*.json'],
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
  /* config options here */
  // Keep production builds type-safe; CI also runs the standalone type-check.
  reactStrictMode: false,
};

export default nextConfig;
