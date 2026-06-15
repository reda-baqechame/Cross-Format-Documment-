/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The canonical-model types are shared from a workspace package (transpiled here).
  transpilePackages: ["@docos/shared-types"],
};

export default nextConfig;
