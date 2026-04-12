/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  allowedDevOrigins: ["*.space.z.ai"],
};

export default nextConfig;
