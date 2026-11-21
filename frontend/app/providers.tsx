"use client";
import { CopilotKitProvider } from "@copilotkit/react-core/v2";

import { MiraRenderers } from "@/components/MiraRenderers";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      agentId="mira"
      useSingleEndpoint={false}
      // The AG-UI inspector is handy in demos but never shown to travellers unless asked for.
      enableInspector={process.env.NEXT_PUBLIC_COPILOTKIT_INSPECTOR === "true"}
    >
      <MiraRenderers />
      {children}
    </CopilotKitProvider>
  );
}
