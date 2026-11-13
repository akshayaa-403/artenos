/** In development the FastAPI app runs separately on port 8000 (npm run api).
 *  On Vercel, /api/* is served by the Python function in api/index.py. */
const nextConfig = {
  async rewrites() {
    return [{
      source: "/api/:path*",
      destination: process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000/api/:path*" : "/api/",
    }];
  },
};
export default nextConfig;
