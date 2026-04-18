import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  ...(process.env.BUILD_STANDALONE === "1" ? { output: "standalone" } : {}),
  outputFileTracingRoot: path.join(__dirname, "../../"),
};

export default nextConfig;
