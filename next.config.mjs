/** One server in production: `next build` exports static pages to out/, and
 *  FastAPI (api/index.py) serves them next to /api. In development Next runs
 *  its own server and forwards /api to FastAPI on port 8000 (npm run api). */
const dev = process.env.NODE_ENV === "development";

const nextConfig = dev
  ? { async rewrites() { return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]; } }
  : { output: "export", trailingSlash: true };

export default nextConfig;
