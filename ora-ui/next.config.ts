import type { NextConfig } from "next";
const withPWA = require("next-pwa")({
  dest: "public",
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === "development",
});

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8001/api/:path*',
      },
      // Fallback for direct v1 access if needed (e.g. models)
      {
        source: '/v1/:path*',
        destination: 'http://127.0.0.1:8001/v1/:path*',
      },
    ];
  },
};

module.exports = withPWA(nextConfig);
