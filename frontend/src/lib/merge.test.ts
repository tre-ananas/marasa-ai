import { describe, expect, it } from "vitest";

import { mergeMessages, type LocalMessage } from "./merge";

const local: LocalMessage[] = [
  { id: "a", role: "user", content: "hola" },
  { id: "b", role: "assistant", content: "respu" },
];

describe("mergeMessages", () => {
  it("keeps local ids when the roles line up", () => {
    const merged = mergeMessages(local, [
      { role: "user", content: "hola" },
      { role: "assistant", content: "respuesta completa" },
    ]);
    expect(merged.map((message) => message.id)).toEqual(["a", "b"]);
    expect(merged[1].content).toBe("respuesta completa");
  });

  it("appends messages another device sent", () => {
    const merged = mergeMessages(local, [
      { role: "user", content: "hola" },
      { role: "assistant", content: "respuesta completa" },
      { role: "user", content: "desde el móvil", ts: "2026-11-02T10:00:00" },
    ]);
    expect(merged).toHaveLength(3);
    expect(merged[2].content).toBe("desde el móvil");
    expect(merged[2].id).toContain("srv-2");
  });

  it("keeps a reply that is still streaming", () => {
    const streaming: LocalMessage[] = [
      { id: "a", role: "user", content: "hola" },
      { id: "b", role: "assistant", content: "resp" },
    ];
    const merged = mergeMessages(streaming, [{ role: "user", content: "hola" }]);
    expect(merged).toHaveLength(2);
    expect(merged[1].content).toBe("resp");
  });

  it("returns the local list when the server has nothing yet", () => {
    expect(mergeMessages(local, [])).toBe(local);
  });
});
