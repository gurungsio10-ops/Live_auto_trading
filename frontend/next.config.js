/** @type {import('next').NextConfig} */
const backend =
  (process.env.ATLAS_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Optional same-origin proxy for non-cookie FastAPI paths.
    // Auth login/logout stay on dedicated BFF routes so httpOnly cookies
    // are set correctly. Browser code should prefer /api/* BFF handlers.
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
