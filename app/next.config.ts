import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1"],
  async redirects() {
    return [
      // Redirect old app.eggnest.co paths to unified domain
      {
        source: "/:path*",
        has: [{ type: "host", value: "app.eggnest.co" }],
        destination: "https://eggnest.co/simulator/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
