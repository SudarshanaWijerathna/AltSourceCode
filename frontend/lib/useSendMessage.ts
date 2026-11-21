"use client";
// Lets a component (traveller picker, tour card) send a message to Mira as if the traveller typed it.
//
// Cards are rendered by CopilotKit's tool-call renderer and are not reliably re-rendered when a run
// ends, so a "disabled while Mira is running" flag captured at render time can stay stuck. Instead
// the run state is read at click time: if Mira is still replying, the message waits for that run to
// finish and is then sent. `busy` only covers this component's own pending click (no double sends).
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useState } from "react";

const WAIT_STEP_MS = 150;
const WAIT_MAX_MS = 60_000;

export function useSendMessage() {
  const { agent } = useAgent();
  const { copilotkit } = useCopilotKit();
  const [busy, setBusy] = useState(false);

  const send = useCallback(
    async (text: string) => {
      if (busy) return;
      setBusy(true);
      try {
        for (let waited = 0; agent.isRunning && waited < WAIT_MAX_MS; waited += WAIT_STEP_MS) {
          await new Promise((r) => setTimeout(r, WAIT_STEP_MS));
        }
        agent.addMessage({ id: crypto.randomUUID(), role: "user", content: text });
        await copilotkit.runAgent({ agent });
      } finally {
        setBusy(false);
      }
    },
    [agent, copilotkit, busy],
  );
  return { send, busy };
}
