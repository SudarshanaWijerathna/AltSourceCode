// Copilot Runtime (TypeScript, open-source mode: no Intelligence, in-memory runner).
// The browser talks to /api/copilotkit; the runtime forwards runs to Mira's AG-UI endpoint.
import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler, InMemoryAgentRunner } from "@copilotkit/runtime/v2";

const backend = process.env.MIRA_BACKEND_URL ?? "http://localhost:8000";

const runtime = new CopilotRuntime({
  agents: { mira: new HttpAgent({ url: `${backend}/agent` }) },
  runner: new InMemoryAgentRunner(),
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const DELETE = handler;
