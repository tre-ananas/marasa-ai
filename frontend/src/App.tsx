import { useCallback, useEffect, useState } from "react";

import StartScreen from "./components/StartScreen";
import SessionScreen from "./components/SessionScreen";
import {
  ApiError,
  createSession,
  discardActiveSession,
  discardSession,
  getActiveSession,
  getSettings,
  type ActiveSession,
  type Settings,
} from "./lib/api";

interface StartInput {
  prompt: string;
  language: string;
  tone: string;
  mode: "text" | "voice";
}

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [session, setSession] = useState<ActiveSession["session"] | null>(null);
  const [active, setActive] = useState<ActiveSession | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);
  const [pendingStart, setPendingStart] = useState<StartInput | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "Could not reach the Marasa backend."),
      );
    // A session survives in the backend while the app is open, so a page
    // reload must not lose it.
    getActiveSession()
      .then(setActive)
      .catch(() => undefined);
  }, []);

  const start = useCallback(async (input: StartInput) => {
    setBusy(true);
    setError(null);
    try {
      setSession(await createSession(input));
      setActive(null);
      setConflict(null);
      setPendingStart(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        // Another session is still running. Ask before throwing it away —
        // the learner may want to keep its recap.
        setConflict(cause.message);
        setPendingStart(input);
        setActive(await getActiveSession().catch(() => null));
      } else {
        setError(cause instanceof Error ? cause.message : "Could not start the session.");
      }
    } finally {
      setBusy(false);
    }
  }, []);

  const discardAndStart = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await discardActiveSession();
      setActive(null);
      setConflict(null);
      const pending = pendingStart;
      setPendingStart(null);
      // Continue with the request that hit the conflict, so the learner does
      // not have to press "Start session" twice.
      if (pending) {
        setSession(await createSession(pending));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not discard the session.");
    } finally {
      setBusy(false);
    }
  }, [pendingStart]);

  const resume = useCallback(() => {
    if (!active) return;
    setSession(active.session);
    setConflict(null);
  }, [active]);

  const finish = useCallback(() => {
    // Leaving the session view keeps it alive so it can be resumed; the
    // start screen offers "Resume" or "Discard".
    setSession(null);
    void getActiveSession()
      .then(setActive)
      .catch(() => undefined);
  }, []);

  const startFresh = useCallback(async () => {
    if (session) {
      await discardSession(session.session_id).catch(() => undefined);
    }
    setSession(null);
    setActive(null);
  }, [session]);

  const sessionGone = useCallback(() => {
    // The session this device was in no longer exists (discarded elsewhere, or
    // the server restarted). Send the learner back to the start screen with an
    // explanation instead of silently doing nothing.
    setSession(null);
    setActive(null);
    setNotice(
      "That session is no longer running — it was discarded, or the server restarted. Start a new one below.",
    );
    setError(null);
    void getActiveSession()
      .then(setActive)
      .catch(() => undefined);
  }, []);

  if (!settings) {
    return (
      <main className="flex min-h-full items-center justify-center p-8">
        <p className="text-[15px] text-[var(--color-muted)]">{error ?? "Starting Marasa…"}</p>
      </main>
    );
  }

  if (!session) {
    return (
      <>
        <StartScreen
          settings={settings}
          busy={busy}
          error={error}
          notice={notice}
          activeSession={active}
          onStart={start}
          onResume={resume}
          onDiscardActive={discardAndStart}
        />
        {conflict ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-6">
            <div className="w-full max-w-sm rounded-[var(--radius-card)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-lift)]">
              <h2 className="text-[19px] font-semibold tracking-[-0.01em]">
                A session is already running
              </h2>
              <p className="mt-2 text-[14px] leading-relaxed text-[var(--color-muted)]">
                Download its recap PDF first if you want to keep it. Starting over erases the
                session and its notes.
              </p>
              <div className="mt-5 flex flex-col gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void discardAndStart()}
                  className="rounded-[var(--radius-control)] bg-[var(--color-accent)] px-5 py-2.5 text-[15px] font-medium text-white transition hover:brightness-110 disabled:opacity-50"
                >
                  Discard it and start a new session
                </button>
                <button
                  type="button"
                  onClick={() => setConflict(null)}
                  className="rounded-[var(--radius-control)] border border-[var(--color-line)] px-5 py-2.5 text-[15px] font-medium transition hover:bg-[var(--color-canvas)]"
                >
                  Keep it
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <SessionScreen
      session={session}
      settings={settings}
      error={error}
      onExit={finish}
      onNewSession={() => void startFresh()}
      onSessionGone={sessionGone}
      onError={setError}
    />
  );
}
