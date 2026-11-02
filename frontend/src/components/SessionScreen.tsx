import { useEffect, useRef, useState } from "react";

import {
  downloadRecapPdf,
  endSession,
  getSession,
  streamTurn,
  type ChatMessage,
  type Mode,
  type Observation,
  type Session,
  type Settings,
} from "../lib/api";
import { createRecognizer, isSpeechSupported, type RecognitionLike } from "../lib/speech";

interface Props {
  session: Session;
  settings: Settings;
  onExit: () => void;
  onNewSession: () => void;
  onError: (message: string | null) => void;
}

export default function SessionScreen({ session, settings, onExit, onNewSession, onError }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [ended, setEnded] = useState(false);
  const [level, setLevel] = useState(session.level);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [interim, setInterim] = useState("");
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const recognizerRef = useRef<RecognitionLike | null>(null);

  const sttLocale =
    settings.languages.find((language) => language.id === session.language)?.stt_locale ??
    "en-US";
  const voiceSupported = isSpeechSupported();

  useEffect(() => {
    getSession(session.session_id)
      .then((payload) => {
        setMessages(
          payload.messages.map((message, index) => ({
            id: `history-${index}-${message.ts ?? ""}`,
            role: message.role,
            content: message.content,
          })),
        );
        setObservations(payload.observations);
      })
      .catch(() => undefined);
  }, [session.session_id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streaming]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming || ended) return;

    setInput("");
    const userId = crypto.randomUUID();
    const assistantId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      { id: userId, role: "user", content: trimmed },
      { id: assistantId, role: "assistant", content: "" },
    ]);
    setStreaming(true);
    onError(null);

    let reply = "";
    try {
      await streamTurn(session.session_id, trimmed, {
        onDelta: (chunk) => {
          reply += chunk;
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId ? { ...message, content: reply } : message,
            ),
          );
        },
        onNotes: (payload) => {
          // The server strips the machine-readable notes block and sends the
          // clean reply; replace the streamed text with it.
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId ? { ...message, content: payload.reply } : message,
            ),
          );
          setLevel(payload.level);
          void getSession(session.session_id).then((full) => setObservations(full.observations));
        },
        onError: (message) => onError(message),
      });
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "The conversation stopped unexpectedly.");
    } finally {
      setStreaming(false);
    }
  };

  const toggleListening = () => {
    if (listening) {
      recognizerRef.current?.stop();
      setListening(false);
      return;
    }
    if (!voiceSupported) {
      setNotice("This browser does not support speech recognition. Typing works just as well.");
      return;
    }
    const recognizer = createRecognizer(sttLocale, {
      onPartial: (text) => setInterim(text),
      onFinal: (text) => {
        setInterim("");
        void send(text);
      },
      onError: (message) => {
        setNotice(message);
        setListening(false);
      },
      onEnd: () => setListening(false),
    });
    if (!recognizer) return;
    recognizerRef.current = recognizer;
    try {
      recognizer.start();
      setListening(true);
    } catch {
      setNotice("Could not start the microphone.");
    }
  };

  const finish = async () => {
    try {
      await endSession(session.session_id);
      const payload = await getSession(session.session_id);
      setObservations(payload.observations);
      setEnded(true);
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not finish the session.");
    }
  };

  const download = async () => {
    try {
      await downloadRecapPdf(session.session_id);
      setNotice("Recap downloaded. Closing Marasa now erases this session.");
    } catch (cause) {
      onError(cause instanceof Error ? cause.message : "Could not render the PDF.");
    }
  };

  const vocab = observations.filter((item) => item.kind === "vocab");
  const grammar = observations.filter((item) => item.kind === "grammar");

  return (
    <main className="mx-auto flex min-h-full w-full max-w-3xl flex-col px-5 py-8">
      <header className="mb-6 flex flex-wrap items-center gap-3 border-b border-[var(--color-line)] pb-4">
        <div className="min-w-0">
          <p className="truncate text-[15px] font-medium">
            {session.topics[0] ?? "Conversation"}
          </p>
          <p className="text-[13px] text-[var(--color-muted)]">
            {session.language_label} · {session.tone_label} · {session.model}
          </p>
        </div>
        <span className="rounded-[var(--radius-control)] bg-[var(--color-accent-soft)] px-3 py-1 text-[13px] font-medium">
          {level}
        </span>
        <button
          type="button"
          onClick={ended ? onExit : finish}
          className="ml-auto rounded-[var(--radius-control)] border border-[var(--color-line)] px-4 py-1.5 text-[14px] font-medium transition hover:bg-[var(--color-canvas)]"
        >
          {ended ? "Close" : "End session"}
        </button>
      </header>

      <section className="flex-1 space-y-5 pb-6">
        {messages.map((message) => (
          <div
            key={message.id}
            className={message.role === "user" ? "flex justify-end" : "flex justify-start"}
          >
            <div
              className={`max-w-[85%] rounded-[20px] px-4 py-3 text-[16px] leading-relaxed whitespace-pre-wrap ${
                message.role === "user"
                  ? "rounded-br-[6px] bg-[var(--color-accent)] text-white"
                  : "rounded-bl-[6px] bg-[var(--color-surface)] shadow-[var(--shadow-soft)]"
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}
        {streaming ? (
          <p className="text-[14px] text-[var(--color-muted)]">Marasa is typing…</p>
        ) : null}
        <div ref={bottomRef} />
      </section>

      {ended ? (
        <section className="rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-soft)]">
          <h2 className="text-[19px] font-semibold tracking-[-0.01em]">Session recap</h2>
          <p className="mt-1 text-[14px] text-[var(--color-muted)]">
            Estimated ACTFL OPI level: <strong className="text-[var(--color-ink)]">{level}</strong>
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="text-[13px] font-medium tracking-wide text-[var(--color-muted)] uppercase">
                Vocabulary
              </h3>
              <ul className="mt-2 space-y-1.5 text-[14px]">
                {vocab.length === 0 ? <li className="text-[var(--color-muted)]">None yet.</li> : null}
                {vocab.map((item) => (
                  <li key={`${item.kind}-${item.term}`}>
                    <span className="font-medium">{item.term}</span>
                    {item.meaning ? <span className="text-[var(--color-muted)]"> — {item.meaning}</span> : null}
                    <span className="ml-1 text-[12px] text-[var(--color-muted)]">({item.status})</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-[13px] font-medium tracking-wide text-[var(--color-muted)] uppercase">
                Grammar
              </h3>
              <ul className="mt-2 space-y-1.5 text-[14px]">
                {grammar.length === 0 ? <li className="text-[var(--color-muted)]">None yet.</li> : null}
                {grammar.map((item) => (
                  <li key={`${item.kind}-${item.term}`}>
                    <span className="font-medium">{item.term}</span>
                    {item.note ? <span className="text-[var(--color-muted)]"> — {item.note}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={download}
              className="rounded-[var(--radius-control)] bg-[var(--color-accent)] px-5 py-2 text-[15px] font-medium text-white transition hover:brightness-110"
            >
              Download recap PDF
            </button>
            <button
              type="button"
              onClick={onNewSession}
              className="rounded-[var(--radius-control)] border border-[var(--color-line)] px-5 py-2 text-[15px] font-medium transition hover:bg-[var(--color-canvas)]"
            >
              Start a new session
            </button>
          </div>
        </section>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
          className="sticky bottom-0 flex items-end gap-3 bg-[var(--color-canvas)] pt-2 pb-4"
        >
          {session.mode === "voice" ? (
            <button
              type="button"
              onClick={toggleListening}
              aria-label={listening ? "Stop listening" : "Start listening"}
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition ${
                listening
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                  : "border-[var(--color-line)] bg-[var(--color-surface)]"
              }`}
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
                <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
              </svg>
            </button>
          ) : null}

          <label htmlFor="composer" className="sr-only">
            Message
          </label>
          <textarea
            id="composer"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
            rows={1}
            placeholder={listening ? "Listening…" : "Write in the language you are learning…"}
            className="max-h-40 min-h-11 flex-1 resize-none rounded-[22px] border border-[var(--color-line)] bg-[var(--color-surface)] px-4 py-3 text-[16px] outline-none focus:border-[var(--color-accent)]"
          />

          <button
            type="submit"
            disabled={streaming || input.trim().length === 0}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent)] text-white transition hover:brightness-110 disabled:opacity-40"
            aria-label="Send"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
              <path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12 2-12 2z" />
            </svg>
          </button>
        </form>
      )}

      {interim ? <p className="text-[14px] text-[var(--color-muted)]">{interim}</p> : null}
      {notice ? (
        <p className="mt-2 rounded-[14px] bg-[var(--color-accent-soft)] px-4 py-3 text-[14px]">
          {notice}
        </p>
      ) : null}
    </main>
  );
}

export type { Mode };
