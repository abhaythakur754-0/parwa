/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  allowedDevOrigins: ["*.space.z.ai"],
  turbopack: {
    root: "/home/z/my-project/parwa",
  },
};

export default nextConfig;
