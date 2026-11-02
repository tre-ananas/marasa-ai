/**
 * Reconciles the local transcript with the backend's copy.
 *
 * One session is shared by every device on the network, so the server's
 * transcript is the source of truth. The local list is kept only so that a
 * half-streamed reply is not overwritten by a poll that arrives mid-turn.
 */

export interface ServerMessage {
  role: "user" | "assistant";
  content: string;
  ts?: string;
}

export interface LocalMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export function mergeMessages(local: LocalMessage[], server: ServerMessage[]): LocalMessage[] {
  if (server.length === 0) return local;

  const merged: LocalMessage[] = server.map((message, index) => {
    const previous = local[index];
    // Keep the id when the roles line up so React does not remount bubbles.
    const id = previous && previous.role === message.role ? previous.id : `srv-${index}-${message.ts ?? ""}`;
    return { id, role: message.role, content: message.content };
  });

  // Anything the server has not caught up with yet (a reply still streaming)
  // stays on the end of the list.
  if (local.length > server.length) {
    merged.push(...local.slice(server.length));
  }

  return merged;
}
