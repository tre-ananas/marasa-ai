# Marasa AI

Marasa AI is a device-local language-practice partner. It gives learners a
sustained conversation in Levantine Arabic, Spanish, or Swedish, adapts to
their proficiency level, records vocabulary and grammar observations, and
produces a downloadable recap at the end.

## Current model policy

Marasa uses **OpenCode Go only**, with one fixed model:

```text
minimax-m3
```

There is no local-model path, alternate-model fallback, or pay-as-you-go
Console fallback.

At the start of each browser session, the learner signs in with a personal
OpenCode Go API key from the [OpenCode Console](https://opencode.ai/console).
Marasa then calls `https://opencode.ai/inference/go`, so usage draws from that
account's Go subscription allowance.

OpenCode currently documents API-key authentication for third-party Go
clients; it does not document a browser OAuth flow for third-party apps.

### Credential security

- The API key is held **only in backend process memory**.
- It is not written to `settings.json`, `.env`, logs, or a database.
- It is never returned to browser JavaScript.
- The browser receives only a random opaque session token in an `HttpOnly`,
  `SameSite=Strict` cookie.
- Signing out or restarting Marasa discards the key.
- Learning sessions are bound to the signed-in browser and cannot be read by
  another browser session.
- The server binds to `127.0.0.1`; it is not exposed to the LAN or internet.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- An OpenCode Go subscription and personal API key

## Setup

Windows PowerShell:

```powershell
.\scripts\setup.ps1
```

macOS/Linux:

```bash
./scripts/setup.sh
```

## Development

```powershell
.\scripts\dev.ps1
```

Open <http://127.0.0.1:5173>. The backend runs on `127.0.0.1:8787` by default
and picks the next free port if needed.

## Run the built app

```powershell
.\scripts\serve.ps1
```

Open <http://127.0.0.1:8787>. The app and API are served together from one
loopback port. Other devices on the network cannot connect.

## Sign-in flow

1. Open the app.
2. Select **Sign in with OpenCode**.
3. Paste a personal OpenCode Go API key.
4. Marasa validates the key against the Go model catalogue.
5. The key remains in memory for this browser session only.
6. Start a language session and use **Sign out** when finished.

The active model and Go allowance consumed by the conversation are shown in
the session header. There is no alternate-model fallback.

## Configuration

Copy `.env.example` to `.env` only when overriding defaults is needed.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MARASA_PROVIDER` | `console` | Runtime provider; production always uses OpenCode Go |
| `MARASA_OPENCODE_ENDPOINT` | `go` | OpenCode Go inference endpoint |
| `MARASA_OPENCODE_API_KEY` | empty | Optional developer fallback only |
| `MARASA_MODEL` | empty | Optional default model override |
| `MARASA_PDF_ENGINE` | `edge` | PDF renderer: `edge` or `chromium` |
| `MARASA_HOST` | `127.0.0.1` | Loopback bind address |
| `MARASA_PORT` | `8787` | Backend port |

Normal users should leave `MARASA_OPENCODE_API_KEY` empty and sign in through
the UI.

## Tests

```powershell
.\scripts\test.ps1
```

The backend suite is deterministic and offline; OpenCode requests are mocked.

## Languages and session behavior

Target languages:

- Levantine colloquial Arabic (`ar-lev`)
- Spanish (`es`)
- Swedish (`sv`)

`Auto` infers the language from the learner's first message. The interface
language is English only.

Sessions and observations are ephemeral. The downloadable PDF recap is the only
durable session artifact.

## Repository layout

```text
backend/
  app/
    api.py                 HTTP routes and session pipeline
    auth.py                ephemeral OpenCode Go browser sessions
    config.py              runtime configuration
    session.py             in-memory learning-session store
    providers/             mock and OpenCode Go providers
    tutor/                 prompts, rubric, notes, languages, tones
  tests/
frontend/
  src/
    components/            start, session, and OpenCode sign-in UI
    lib/                   API client, SSE, merge, speech helpers
scripts/                   setup, development, test, and serve scripts
```

## License note

The repository contains references to the ACTFL OPI framework. Keep the
`OPI-Familiarization-Guide-2020-1.pdf` file local and do not redistribute it.
