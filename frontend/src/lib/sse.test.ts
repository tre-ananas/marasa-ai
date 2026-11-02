import { describe, expect, it } from "vitest";

import { drainSseBuffer, parseEventPayload } from "./sse";

describe("drainSseBuffer", () => {
  it("returns no events for an incomplete buffer", () => {
    const { events, rest } = drainSseBuffer("event: delta\ndata: {\"text\"");
    expect(events).toHaveLength(0);
    expect(rest).toContain("event: delta");
  });

  it("splits complete events and keeps the remainder", () => {
    const buffer = 'event: delta\ndata: {"text":"hi"}\n\nevent: notes\ndata: {"level":"IM"}\n\nevent: us';
    const { events, rest } = drainSseBuffer(buffer);
    expect(events.map((event) => event.event)).toEqual(["delta", "notes"]);
    expect(events[0].data).toBe('{"text":"hi"}');
    expect(rest).toBe("event: us");
  });

  it("ignores events without data", () => {
    const { events } = drainSseBuffer("event: ping\n\n");
    expect(events).toHaveLength(0);
  });
});

describe("parseEventPayload", () => {
  it("parses JSON payloads", () => {
    expect(parseEventPayload({ event: "notes", data: '{"level":"IM"}' })).toEqual({ level: "IM" });
  });

  it("returns null for malformed JSON", () => {
    expect(parseEventPayload({ event: "notes", data: "{oops" })).toBeNull();
  });
});
