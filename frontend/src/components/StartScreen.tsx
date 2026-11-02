import { useState } from "react";

import type { ActiveSession, Mode, Settings } from "../lib/api";

/** BCP-47 tags so a phone switches to the right keyboard (Arabic, Swedish, …). */
const KEYBOARD_LANG: Record<string, string> = {
  es: "es",
  sv: "sv",
  "ar-lev": "ar",
  auto: "en",
};

interface Props {
  settings: Settings;
  busy: boolean;
  error: string | null;
  activeSession: ActiveSession | null;
  onStart: (input: {
    prompt: string;
    language: string;
    tone: string;
    mode: Mode;
  }) => void;
  onResume: () => void;
  onDiscardActive: () => void;
}

export default function StartScreen({
  settings,
  busy,
  error,
  activeSession,
  onStart,
  onResume,
  onDiscardActive,
}: Props) {
  const [prompt, setPrompt] = useState("");
  const [language, setLanguage] = useState("auto");
  const [tone, setTone] = useState("conversation_partner");
  const [mode, setMode] = useState<Mode>("text");

  const canStart = !busy && (prompt.trim().length > 0 || mode === "voice");

  return (
    <main className="mx-auto flex min-h-full w-full max-w-2xl flex-col justify-center px-6 py-16">
      <header className="mb-10 text-center">
        <p className="mb-3 text-[13px] font-medium tracking-[0.18em] text-[var(--color-muted)] uppercase">
          Marasa
        </p>
        <h1 className="text-[34px] leading-[1.15] font-semibold tracking-[-0.02em] text-balance">
          What would you like to talk about?
        </h1>
        <p className="mx-auto mt-4 max-w-md text-[15px] leading-relaxed text-[var(--color-muted)]">
          Marasa practises with you in the language you are learning, adjusts to your level, and
          shows you what to work on next.
        </p>
      </header>

      {activeSession ? (
        <div className="mb-6 rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-soft)]">
          <h2 className="text-[17px] font-semibold tracking-[-0.01em]">A session is still open</h2>
          <p className="mt-1 text-[14px] leading-relaxed text-[var(--color-muted)]">
            {activeSession.session.topics[0] ?? "Conversation"} ·{" "}
            {activeSession.session.language_label} · {activeSession.messages.length} messages.
            Resume it, or discard it to start over.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onResume}
              className="rounded-[var(--radius-control)] bg-[var(--color-accent)] px-5 py-2 text-[15px] font-medium text-white transition hover:brightness-110"
            >
              Resume session
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onDiscardActive}
              className="rounded-[var(--radius-control)] border border-[var(--color-line)] px-5 py-2 text-[15px] font-medium transition hover:bg-[var(--color-canvas)] disabled:opacity-50"
            >
              Discard it
            </button>
          </div>
        </div>
      ) : null}

      <div className="rounded-[var(--radius-card)] border border-[var(--color-line)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-soft)]">
        <label htmlFor="prompt" className="sr-only">
          Topic
        </label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && canStart) {
              onStart({ prompt, language, tone, mode });
            }
          }}
          rows={3}
          lang={KEYBOARD_LANG[language] ?? "en"}
          dir={language === "ar-lev" ? "rtl" : "ltr"}
          placeholder="A topic you want to talk about, or a question you want to explore…"
          className="w-full resize-none border-0 bg-transparent text-[17px] leading-relaxed outline-none placeholder:text-[var(--color-muted)]"
        />

        <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-[var(--color-line)] pt-4">
          <div
            role="group"
            aria-label="Input mode"
            className="flex rounded-[var(--radius-control)] bg-[var(--color-canvas)] p-1"
          >
            {(["text", "voice"] as Mode[]).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setMode(option)}
                aria-pressed={mode === option}
                className={`rounded-[var(--radius-control)] px-4 py-1.5 text-[14px] font-medium transition ${
                  mode === option
                    ? "bg-[var(--color-surface)] text-[var(--color-ink)] shadow-[var(--shadow-soft)]"
                    : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
                }`}
              >
                {option === "text" ? "Text" : "Voice"}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 text-[14px] text-[var(--color-muted)]">
            Language
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              className="rounded-[var(--radius-control)] border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5 text-[14px] text-[var(--color-ink)] outline-none focus:border-[var(--color-accent)]"
            >
              {settings.languages.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-[14px] text-[var(--color-muted)]">
            Tone
            <select
              value={tone}
              onChange={(event) => setTone(event.target.value)}
              className="rounded-[var(--radius-control)] border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5 text-[14px] text-[var(--color-ink)] outline-none focus:border-[var(--color-accent)]"
            >
              {settings.tones.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            disabled={!canStart}
            onClick={() => onStart({ prompt, language, tone, mode })}
            className="ml-auto rounded-[var(--radius-control)] bg-[var(--color-accent)] px-5 py-2 text-[15px] font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Starting…" : "Start session"}
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-[14px] bg-[var(--color-accent-soft)] px-4 py-3 text-[14px] text-[var(--color-ink)]">
          {error}
        </p>
      ) : null}

      <p className="mt-6 text-center text-[13px] leading-relaxed text-[var(--color-muted)]">
        Sessions are not saved. Download the recap PDF to keep a record of your session.
      </p>
    </main>
  );
}
