import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every image is a plain <img> pointed at /public, sized and cropped by CSS.
  // Nothing goes through next/image, so the optimizer stays out of the way and
  // the rendered markup matches the TanStack Start build byte for byte.
  reactStrictMode: true,
};

export default nextConfig;
