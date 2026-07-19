import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the file-tracing root to this app so a stray parent lockfile
  // (e.g. C:\Users\LENOVO\package-lock.json) doesn't confuse the build.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
