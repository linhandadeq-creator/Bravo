import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: {
    ignoreDuringBuilds: false,
  },
  // Proxy API calls through the Next server so the UI works from any host
  // (e.g. a phone on the LAN) without CORS or a hard-coded backend URL.
  async rewrites() {
    const target =
      process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${target}/api/:path*` }];
  },
};

export default nextConfig;
