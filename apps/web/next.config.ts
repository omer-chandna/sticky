import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  transpilePackages: ["@sticky/shared"],
  images: { unoptimized: true },
};

export default nextConfig;
