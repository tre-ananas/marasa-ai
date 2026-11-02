import { drainSseBuffer, parseEventPayload } from "./sse";

export type Mode = "text" | "voice";

export interface LanguageOption {
  id: string;
  label: string;
  stt_locale: string;
}

export interface ToneOption {
  id: string;
  label: string;
  blurb: string;
}

export interface Settings {
  provider: string;
  model: string;
  key_configured: boolean;
  pdf_engine: string;
  languages: LanguageOption[];
  tones: ToneOption[];
}

export interface Session {
  session_id: string;
  language: string;
  language_label: string;
  tone: string;
  tone_label: string;
  mode: Mode;
  topics: string[];
  vocab_terms: string[];
  level: string;
  provider: string;
  model: string;
}

export interface Observation {
  kind: "vocab" | "grammar";
  term: string;
  status: "strong" | "gap" | "useful";
  meaning: string;
  note: string;
  evidence: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const API = "/api";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** Present when the backend reports a conflicting active session. */
    public readonly activeSessionId?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response
      .json()
      .then((payload: { detail?: string | { message?: string; active_session_id?: string } }) =>
        payload.detail,
      )
      .catch(() => response.statusText);

    if (typeof body === "string") {
      throw new ApiError(response.status, body);
    }
    throw new ApiError(
      response.status,
      body?.message ?? response.statusText,
      body?.active_session_id ?? undefined,
    );
  }
  return response.json() as Promise<T>;
}

export function getSettings(): Promise<Settings> {
  return request<Settings>("/settings");
}

export function createSession(payload: {
  prompt: string;
  language: string;
  tone: string;
  mode: Mode;
}): Promise<Session> {
  return request<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function endSession(sessionId: string): Promise<{ status: string; level: string }> {
  return request<{ status: string; level: string }>(`/sessions/${sessionId}/end`, {
    method: "POST",
  });
}

export function discardSession(sessionId: string): Promise<{ discarded: boolean }> {
  return request<{ discarded: boolean }>(`/sessions/${sessionId}`, { method: "DELETE" });
}

export interface SessionMessage {
  role: "user" | "assistant";
  content: string;
  ts?: string;
}

export function getSession(sessionId: string): Promise<{
  messages: SessionMessage[];
  observations: Observation[];
  usage: Record<string, number>;
}> {
  return request(`/sessions/${sessionId}`);
}

export interface ActiveSession {
  session: Session;
  messages: SessionMessage[];
  observations: Observation[];
  usage: Record<string, number>;
}

/** The session the backend is still holding, if any (null when there is none). */
export async function getActiveSession(): Promise<ActiveSession | null> {
  try {
    return await request<ActiveSession>("/sessions/active");
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 404) return null;
    throw cause;
  }
}

/** Discards whichever session is running, without needing its id. */
export function discardActiveSession(): Promise<{ discarded: boolean }> {
  return request("/sessions/active", { method: "DELETE" });
}

export async function downloadRecapPdf(sessionId: string): Promise<void> {
  const response = await fetch(`${API}/sessions/${sessionId}/recap.pdf`, { method: "POST" });
  if (!response.ok) {
    throw new ApiError(response.status, "Could not render the recap PDF.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `marasa-recap-${sessionId.slice(0, 8)}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export interface TurnHandlers {
  onDelta: (text: string) => void;
  onNotes?: (payload: {
    reply: string;
    vocab: unknown[];
    grammar: unknown[];
    level: string;
    next_step: string;
  }) => void;
  onUsage?: (usage: Record<string, unknown>) => void;
  onError?: (message: string) => void;
}

/** Streams one assistant turn. Uses SSE over a POST body. */
export async function streamTurn(
  sessionId: string,
  text: string,
  handlers: TurnHandlers,
): Promise<void> {
  const response = await fetch(`${API}/sessions/${sessionId}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok || !response.body) {
    throw new ApiError(response.status, "The conversation could not be continued.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const { events, rest } = drainSseBuffer(buffer);
    buffer = rest;

    for (const event of events) {
      const payload = parseEventPayload<Record<string, unknown>>(event);
      if (!payload) continue;

      if (event.event === "delta") {
        handlers.onDelta(String(payload.text ?? ""));
      } else if (event.event === "notes") {
        handlers.onNotes?.(payload as never);
      } else if (event.event === "usage") {
        handlers.onUsage?.(payload);
      } else if (event.event === "error") {
        handlers.onError?.(String(payload.message ?? "Unknown error"));
      }
    }
  }
}
