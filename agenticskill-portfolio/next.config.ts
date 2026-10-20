import type { NextConfig } from "next";

// Static export for Cloudflare Pages. Pages are prerendered at build time from
// the repo's ../skills folder, so there is no server at runtime.
// Styles are plain global CSS (src/app/globals.css), handled by Next.js directly.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
