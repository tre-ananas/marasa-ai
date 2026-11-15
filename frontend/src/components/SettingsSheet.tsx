import { useState } from "react";

import {
  signInWithOpenCode,
  signOut,
  testConnection,
  type Settings,
} from "../lib/api";

interface Props {
  settings: Settings;
  onClose: () => void;
  onSaved: (settings: Settings) => void;
  onSignedOut: () => void;
}

export default function SettingsSheet({
  settings,
  onClose,
  onSaved,
  onSignedOut,
}: Props) {
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const test = async () => {
    setBusy(true);
    setStatus(null);
    try {
      const result = await testConnection();
      setStatus(
        `Connected: ${result.model} answered in ${result.latency_s}s through OpenCode Go.`,
      );
    } catch (cause) {
      setStatus(cause instanceof Error ? cause.message : "The connection test failed.");
    } finally {
      setBusy(false);
    }
  };

  const signIn = async () => {
    setBusy(true);
    setStatus(null);
    try {
      await signInWithOpenCode({ api_key: apiKey });
      setApiKey("");
      onSaved({ ...settings, authenticated: true, model: settings.free_model });
    } catch (cause) {
      setStatus(cause instanceof Error ? cause.message : "OpenCode sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  const signOutAndClose = async () => {
    setBusy(true);
    try {
      await signOut();
      onSignedOut();
    } finally {
      setBusy(false);
    }
  };

  const model = settings.free_model;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/30 p-0 sm:items-center sm:p-6">
      <div className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-[var(--radius-card)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-lift)] sm:rounded-[var(--radius-card)]">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-[19px] font-semibold tracking-[-0.01em]">OpenCode Go</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--color-line)] px-3 py-1 text-[13px] text-[var(--color-muted)]"
          >
            Close
          </button>
        </div>

        <section className="mt-5">
          <h3 className="text-[13px] font-medium tracking-wide text-[var(--color-muted)] uppercase">
            {settings.authenticated ? "Signed in" : "Sign in each session"}
          </h3>
          <p className="mt-1 text-[13px] leading-relaxed text-[var(--color-muted)]">
            {settings.authenticated
              ? "Your OpenCode Go key is held only in memory for this browser session. It is never written to disk and all usage draws from your Go subscription allowance."
              : "Create a personal API key in the OpenCode Console and paste it here. Marasa keeps it only in memory for this browser session and always calls the OpenCode Go endpoint."}
          </p>

          {!settings.authenticated ? (
            <>
              <p className="mt-3 text-[13px] leading-relaxed text-[var(--color-muted)]">
                OpenCode Go currently documents API-key sign-in for third-party apps. Each browser
                session must use its own key so usage is attributed to the correct account.
              </p>
              <label className="mt-4 block text-[14px]">
                OpenCode Go API key
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="sk-ΓÇª"
                  autoComplete="off"
                  className="mt-1 w-full rounded-[14px] border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 outline-none focus:border-[var(--color-accent)]"
                />
              </label>
            </>
          ) : null}
        </section>

        <section className="mt-5">
          <h3 className="text-[13px] font-medium tracking-wide text-[var(--color-muted)] uppercase">
            Model
          </h3>
          <p className="mt-1 text-[13px] text-[var(--color-muted)]">
            Marasa uses one fixed model: {model}. Every request draws from your OpenCode Go
            subscription allowance.
          </p>
          <div className="mt-2 rounded-[14px] border border-[var(--color-line)] bg-[var(--color-canvas)] px-3 py-2 text-[14px]">
            {model}
          </div>
        </section>

        {status ? (
          <p className="mt-4 rounded-[14px] bg-[var(--color-accent-soft)] px-4 py-3 text-[14px]">
            {status}
          </p>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3">
          {!settings.authenticated ? (
            <button
              type="button"
              disabled={busy || apiKey.trim().length < 8}
              onClick={() => void signIn()}
              className="rounded-[var(--radius-control)] bg-[var(--color-accent)] px-5 py-2.5 text-[15px] font-medium text-white transition hover:brightness-110 disabled:opacity-50"
            >
              Sign in
            </button>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => void test()}
                className="rounded-[var(--radius-control)] border border-[var(--color-line)] px-5 py-2.5 text-[15px] font-medium transition hover:bg-[var(--color-canvas)] disabled:opacity-50"
              >
                Test connection
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void signOutAndClose()}
                className="rounded-[var(--radius-control)] px-5 py-2.5 text-[15px] font-medium text-[var(--color-muted)] transition hover:bg-[var(--color-canvas)] disabled:opacity-50"
              >
                Sign out
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
