"use client";
// Lets a component (traveller picker, tour card) send a message to Mira as if the traveller typed it.
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback } from "react";

export function useSendMessage() {
  const { agent } = useAgent();
  const { copilotkit } = useCopilotKit();
  const send = useCallback(
    async (text: string) => {
      if (agent.isRunning) return;
      agent.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
      await copilotkit.runAgent({ agent });
    },
    [agent, copilotkit],
  );
  return { send, busy: agent.isRunning };
}
