/**
 * Message ids for the transcript.
 *
 * `crypto.randomUUID()` is only available in secure contexts (HTTPS or
 * localhost), so it throws in insecure browser contexts.
 * These ids only have to be unique within one browser tab, so a counter is
 * enough.
 */

let counter = 0;

export function nextMessageId(): string {
  counter += 1;
  return `m${Date.now().toString(36)}-${counter.toString(36)}`;
}
