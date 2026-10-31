import type { NextConfig } from "next";

const config: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // The app currently does not import next/image. Disable optimization so the
  // runtime does not need the optional sharp/libvips native dependency.
  // The production dependency verifier blocks adding next/image without review.
  images: { unoptimized: true },
};

export default config;
