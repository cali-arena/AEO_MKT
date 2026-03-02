import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Production builds do not use dev websocket (e.g. ws://localhost:8081); that is dev-only tooling. */
};

export default nextConfig;
