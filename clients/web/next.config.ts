import type { NextConfig } from "next";

const DEFAULT_CORE_ORIGIN = "http://127.0.0.1:8001";
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

function resolveCoreOrigin() {
  const rawOrigin = process.env.YONERAI_CORE_API_ORIGIN || DEFAULT_CORE_ORIGIN;
  const parsed = new URL(rawOrigin);

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("YONERAI_CORE_API_ORIGIN must use http or https.");
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("YONERAI_CORE_API_ORIGIN must not include credentials, query strings, or fragments.");
  }
  if (!LOOPBACK_HOSTS.has(parsed.hostname)) {
    throw new Error("YONERAI_CORE_API_ORIGIN must point to localhost or a loopback IP address.");
  }

  return parsed.origin;
}

const nextConfig: NextConfig = {
  async rewrites() {
    const coreOrigin = resolveCoreOrigin();

    return [
      {
        source: '/api/:path*',
        destination: `${coreOrigin}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
