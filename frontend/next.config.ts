import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@phosphor-icons/react",
    ],
  },
};

export default nextConfig;
