import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
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
