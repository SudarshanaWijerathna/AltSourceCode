// CopilotKit runtime telemetry is opt-in for this project (set it to "false" to share usage data).
process.env.COPILOTKIT_TELEMETRY_DISABLED ??= "true";

/** @type {import('next').NextConfig} */
const backend = process.env.MIRA_BACKEND_URL ?? "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Same-origin proxy to the FastAPI backend (booking, staff API). AG-UI goes via /api/copilotkit.
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${backend}/:path*` }];
  },
};

export default nextConfig;
