import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
  turbopack: {},
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@phosphor-icons/react",
    ],
  },
};

export default nextConfig;

