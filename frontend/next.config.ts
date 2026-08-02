import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" is for the self-hosted Docker build; Vercel has its own build
  // output and doesn't need (or want) it.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
