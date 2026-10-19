import type { NextConfig } from "next";

const rawBackendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
const backendUrl = /^https?:\/\//.test(rawBackendUrl)
  ? rawBackendUrl
  : `https://${rawBackendUrl}`;

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
