export type Source = {
  title: string;
  url: string;
  snippet: string;
};

export type AgentStep = {
  step: string;
  label: string;
  status: "started" | "completed" | "failed" | "stopped";
  reason?: string;
  action?: string;
  count?: number;
  result?: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  agentSteps?: AgentStep[];
};

type StreamHandlers = {
  onToken: (token: string) => void;
  onStatus: (status: string | null) => void;
  onSource: (source: Source) => void;
  onAgent: (step: AgentStep) => void;
  onError: (message: string) => void;
};

const API_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function streamChat(
  userId: string,
  conversationId: string,
  message: string,
  history: ChatMessage[],
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",

    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },

    body: JSON.stringify({
      user_id: userId,
      conversation_id: conversationId,
      message,

      history: history.map(({ role, content }) => ({
        role,
        content,
      })),
    }),

    signal,
  });

  if (!response.ok) {
    let detail = "The chat service could not be reached.";

    try {
      const body = await response.text();

      if (body.trim()) {
        try {
          const parsed = JSON.parse(body);

          detail =
            parsed.detail ??
            parsed.message ??
            parsed.error ??
            body;
        } catch {
          detail = body;
        }
      }
    } catch {
      // Ignore response parsing failure.
    }

    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error(
      "The chat service returned no response stream.",
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buffer = "";

  function processEvent(rawEvent: string) {
    const lines = rawEvent.split(/\r?\n/);

    let data = "";

    for (const line of lines) {
      if (line.startsWith("data:")) {
        data += line.slice(5).trimStart();
      }
    }

    if (!data.trim()) {
      return;
    }

    let event: {
      type?: string;
      [key: string]: unknown;
    };

    try {
      event = JSON.parse(data);
    } catch {
      return;
    }

    const type = String(event.type ?? "");

    // ========================================================
    // CONTENT / TOKEN
    // ========================================================

    if (type === "content" || type === "token") {
      const token =
        type === "content"
          ? String(event.content ?? "")
          : String(event.data ?? "");

      if (token) {
        handlers.onToken(token);
      }

      return;
    }

    // ========================================================
    // AGENT STEP
    // ========================================================

    if (type === "agent") {
      const status =
        event.status === "failed"
          ? "failed"
          : event.status === "started"
            ? "started"
            : event.status === "stopped"
              ? "stopped"
              : "completed";

      handlers.onAgent({
        step: String(event.step ?? ""),
        label: String(event.label ?? ""),
        status,

        reason:
          event.reason !== undefined
            ? String(event.reason)
            : undefined,

        action:
          event.action !== undefined
            ? String(event.action)
            : undefined,

        count:
          typeof event.count === "number"
            ? event.count
            : undefined,

        result:
          event.result !== undefined
            ? String(event.result)
            : undefined,
      });

      return;
    }

    // ========================================================
    // STATUS
    // ========================================================

    if (type === "status") {
      const status = String(event.status ?? "");

      if (status === "searching") {
        handlers.onStatus("Searching the web...");
      } else if (status === "writing") {
        handlers.onStatus("Writing answer...");
      } else if (status === "memory") {
        handlers.onStatus("Checking memory...");
      } else {
        handlers.onStatus(null);
      }

      return;
    }

    // ========================================================
    // SOURCE
    // ========================================================

    if (type === "source") {
      const url = String(event.url ?? "");

      if (!url) {
        return;
      }

      handlers.onSource({
        title: String(event.title ?? url),
        url,
        snippet: String(event.snippet ?? ""),
      });

      return;
    }

    // ========================================================
    // ERROR
    // ========================================================

    if (type === "error") {
      handlers.onError(
        String(
          event.message ??
            event.data ??
            "Unknown server error.",
        ),
      );

      return;
    }

    // ========================================================
    // DONE
    // ========================================================

    if (type === "done") {
      handlers.onStatus(null);
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, {
          stream: !done,
        });
      }

      const normalized = buffer.replace(/\r\n/g, "\n");

      const events = normalized.split("\n\n");

      buffer = events.pop() ?? "";

      for (const rawEvent of events) {
        processEvent(rawEvent);
      }

      if (done) {
        break;
      }
    }

    if (buffer.trim()) {
      processEvent(buffer);
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Reader already released.
    }
  }
}