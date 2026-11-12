import type { NextConfig } from "next";

// Deployed standalone at "/" or embedded under a sub-path (e.g. /projects/spet on windesheim.co).
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const config: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  trailingSlash: true,
  images: { unoptimized: true },
};

export default config;
