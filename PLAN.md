# Marasa AI — Current Implementation Plan

## Product decisions

1. Marasa is an output-oriented language practice partner for Levantine
   colloquial Arabic, Spanish, and Swedish.
2. Sessions are ephemeral and in memory. The downloadable PDF recap is the only
   durable artifact.
3. Each browser session signs in with its own OpenCode Go API key.
4. The key is retained only in backend process memory and is never persisted or
   returned to browser JavaScript.
5. Every inference request uses `https://opencode.ai/inference/go`, drawing from
   the signed-in account's Go subscription allowance.
6. The only model is `minimax-m3`.
7. There is no local-model path, alternate-model fallback, or pay-as-you-go
   Console fallback.
8. The app binds to `127.0.0.1` and is not exposed to the LAN or internet.
9. OpenCode currently documents personal API-key authentication for third-party
   Go clients. A browser OAuth flow requires a documented public OAuth client
   contract and is not implemented.

## Architecture

```text
Browser on this device
  │ opaque HttpOnly session cookie
  ▼
FastAPI (uvicorn, 127.0.0.1:8787)
  ├─ api.py          routes, ownership checks, SSE turns
  ├─ auth.py         ephemeral OpenCode Go browser sessions
  ├─ session.py      in-memory learning sessions
  ├─ tutor/          prompts, rubric, notes, languages, tones
  └─ providers/
      ├─ mock.py             deterministic tests
      └─ opencode_console.py OpenCode Go inference
              │
              ▼
      https://opencode.ai/inference/go
```

## Security model

- The backend binds only to loopback.
- A random opaque token is stored in an `HttpOnly`, `SameSite=Strict` cookie.
- Only a SHA-256 digest of the token is used as the in-memory lookup key.
- The OpenCode API key exists only in the process-local auth store.
- The key is not written to `settings.json`, `.env`, logs, or a database.
- Every protected route requires the signed-in browser session.
- Every learning-session route checks that the signed-in browser owns the
  learning session.
- Sign-out removes the credential and cookie.
- Restarting the server removes all credentials and sessions.
- The model catalogue and connection test use the signed-in credential only.
- The old global API-key settings write path was removed.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Non-sensitive readiness information |
| `GET` | `/api/settings` | Sign-in state, model, languages, tones |
| `POST` | `/api/auth/opencode/sign-in` | Validate a Go key and create an ephemeral session |
| `POST` | `/api/auth/opencode/refresh` | Rotate the browser token |
| `POST` | `/api/auth/sign-out` | Remove the credential and cookie |
| `POST` | `/api/settings/test` | Test the signed-in Go credential |
| `GET` | `/api/models` | List models available to the signed-in Go account |
| `POST` | `/api/sessions` | Create an owned learning session |
| `GET` | `/api/sessions/active` | Read the signed-in browser's active session |
| `DELETE` | `/api/sessions/active` | Discard the active session |
| `GET` | `/api/sessions/{id}` | Read an owned session |
| `POST` | `/api/sessions/{id}/turns` | Stream a turn with SSE |
| `POST` | `/api/sessions/{id}/end` | End an owned session |
| `DELETE` | `/api/sessions/{id}` | Discard an owned session |
| `POST` | `/api/sessions/{id}/recap.pdf` | Render an owned session recap |

## Provider behavior

- Endpoint: `https://opencode.ai/inference/go`.
- Authentication: `Authorization: Bearer <session API key>`.
- Stable routing header: `x-opencode-session: <learning-session-id>`.
- Supports model-catalogue discovery and the OpenAI Chat Completions and
  Anthropic Messages wire formats.
- Parses token usage, cost, Go allowance, and billing source.
- Maps 401/403 to credential or entitlement problems, 429 to exhausted Go
  allowance, and 5xx to retryable upstream failures.
- The only model is `minimax-m3`. It is included in OpenCode Go.
- No alternate, local, or pay-as-you-go fallback is attempted.

## Completed work

- [x] OpenCode Go provider with model discovery and streaming.
- [x] Cost, allowance, and billing telemetry.
- [x] Per-browser OpenCode Go sign-in using a personal API key.
- [x] Memory-only credential storage.
- [x] HttpOnly browser session cookie.
- [x] Learning-session ownership checks.
- [x] Device-local loopback-only serving.
- [x] Settings UI for sign-in, sign-out, and connection testing.
- [x] Fixed MiniMax M3 model with no alternate fallback.
- [x] Backend tests for sign-in, secret non-disclosure, ownership, and turns.
- [x] Frontend production build.

## Remaining work

- [ ] Add browser-level tests for the sign-in and sign-out UI.
- [ ] Remove the remaining development model-selection plumbing if the fixed
  MiniMax M3 policy becomes permanent.
- [ ] Add request cancellation and upstream timeout handling.
- [ ] Add an optional local OS credential store only if persistence across
  browser restarts becomes a requirement; it must not be enabled by default.
- [ ] Replace the API-key flow automatically if OpenCode publishes a supported
  third-party OAuth client contract.
