/** Minimal Server-Sent Events parsing (pure, testable). */

export interface SseEvent {
  event: string;
  data: string;
}

/**
 * Splits a raw SSE buffer into complete events.
 * Returns the events that are fully received plus the remaining buffer.
 */
export function drainSseBuffer(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = [];
  let rest = buffer;

  for (;;) {
    const boundary = rest.indexOf("\n\n");
    if (boundary === -1) break;

    const raw = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);

    let event = "message";
    let data = "";
    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (data) events.push({ event, data });
  }

  return { events, rest };
}

/** Parses one event's JSON payload. */
export function parseEventPayload<T>(event: SseEvent): T | null {
  try {
    return JSON.parse(event.data) as T;
  } catch {
    return null;
  }
}
