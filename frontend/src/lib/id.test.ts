import { describe, expect, it } from "vitest";

import { nextMessageId } from "./id";

describe("nextMessageId", () => {
  it("returns unique ids", () => {
    const ids = new Set(Array.from({ length: 50 }, () => nextMessageId()));
    expect(ids.size).toBe(50);
  });

  it("does not depend on crypto.randomUUID (unavailable on plain HTTP)", () => {
    const original = globalThis.crypto.randomUUID;
    // @ts-expect-error deliberately removing the API to mimic an insecure origin
    delete globalThis.crypto.randomUUID;
    try {
      expect(() => nextMessageId()).not.toThrow();
      expect(nextMessageId()).toBeTruthy();
    } finally {
      globalThis.crypto.randomUUID = original;
    }
  });
});
