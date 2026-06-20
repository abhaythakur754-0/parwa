/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/jarvis/stream',
        destination: 'http://localhost:8100/api/jarvis/stream',
      },
    ];
  },
};

module.exports = nextConfig;