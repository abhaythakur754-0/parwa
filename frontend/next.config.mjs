/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  allowedDevOrigins: ["https://preview-chat-d6004c9f-0ad7-44f2-be53-375d6d382b20.space.z.ai", "*.space.z.ai"],
  turbopack: {
    root: ".",
  },
};

export default nextConfig;
