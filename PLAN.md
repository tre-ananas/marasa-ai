# Marasa AI — MVP Implementation Plan

Status: **in progress** · Updated: 2026-11-01
Scope source of truth: [`README.md`](./README.md) · Setup and model decisions live in the README too.

> **What changed since the first draft**
> 1. Email delivery removed — PDF download is the only export and the only durable artefact of a session.
> 2. Sessions are **ephemeral**: in-memory only, one active session at a time, no history screen, no cross-session memory.
> 3. Target languages fixed: Levantine colloquial Arabic, Spanish, Swedish (UI language: English).
> 4. Tones added as a start-screen menu (conversation partner, formal interview, OPI examiner, debate, storytelling).
> 5. No user overrides of Marasa's judgements in the MVP.
> 6. Packaging: `uv`-locked Python venv + `npm ci`-locked frontend, one-command `setup`/`dev`/`test` scripts.
> 7. Model strategy researched and fixed: free default → paid default → local Ollama, with no user research required.
> 8. The ACTFL OPI Familiarization Guide is now in the repo and drives `backend/app/tutor/rubric.py`.

---

## 1. MVP definition (what "done" means)

Marasa AI is an **output-oriented language practice partner**. The learner talks to Marasa (text or voice) about topics they choose or vocabulary they upload; Marasa adapts to their ACTFL Oral Proficiency Interview (OPI) level, tracks what they did well and where they struggled, and ends with a downloadable recap containing a session-level OPI score.

The MVP is complete when a single learner, running locally, can:

1. Start a session by describing what they want to talk about (and optionally attaching a vocab-sheet PDF or a previous recap PDF), with language, tone and input mode auto-inferred unless overridden.
2. Hold a sustained conversation with Marasa in the target language, with Marasa weaving in the target vocabulary and adjusting difficulty to the learner's OPI level.
3. End the session and receive a recap: summary, vocabulary/grammar assessment, recommendations, and an OPI score with evidence.
4. Download that recap as a PDF — the only way to keep it.

Everything else is out of scope (§13).

### 1.1 Traceability to the README

| README requirement | MVP implementation | Milestone | Status |
| --- | --- | --- | --- |
| §1 Topics, or a vocab sheet (.pdf); with no input, Marasa asks what to talk about; select text/voice and language; otherwise inferred from the first prompt | Start screen with one free-text field, optional PDF attach, Text/Voice segmented control, language select with **Auto**, tone menu; a setup pass infers language/mode/topic/starting level | M2, M3 | scaffolded |
| §2 Targeted discussion using topics + vocab (and neighbouring words); track ability per ACTFL OPI; adjust register, vernacular, difficulty to meet or slightly exceed ability | Tutor prompt with the OPI rubric, topic list, vocab list (incl. generated synonyms/collocations); difficulty targets the learner's current sublevel ±1; turns capped at 2–4 sentences with at most one question | M2, M4 | scaffolded |
| §3 Track words/grammar done well and to improve; track session OPI; recap with summary, assessment, recommendations, OPI score | Observations captured per turn; end-of-session assessment scored against the rubric; Recap screen + PDF | M4, M5 | scaffolded |
| §4 Download the feedback as a .pdf | Playwright renders the recap HTML to PDF (Edge channel on Windows, no download) | M5 | done |
| Cost: free first, then the user's own OpenCode/OpenCode Go budget | Provider abstraction: local OpenCode server (free tier) + OpenCode Console/Go (user's key) + local Ollama; key never reaches the browser | M1, M1.5 | ollama done, console/local pending |
| MVP: minimalistic, obvious UI, Apple-style; ship Primary Functions only | Three screens (Start → Session → Recap); one visual system; nothing beyond the table above | M6, M7 | scaffolded |

---

## 2. Decisions (locked)

| Decision | Choice | Consequence |
| --- | --- | --- |
| Deployment | **Local single-user web app** | No accounts, no hosting, no key-exposure risk. Backend binds `127.0.0.1` only. |
| Stack | **FastAPI (Python) + React/Vite/Tailwind** | Python 3.12 pinned by uv; Node 20+ for the frontend. |
| Packaging | **`uv.lock` + `package-lock.json`**, one-command scripts | A clone is self-contained: `backend/.venv` and `frontend/node_modules` are created by `setup`, nothing global except uv/Node. |
| LLM access | **Provider abstraction, four paths** | `mock` (offline, default), `ollama` (local), `console` (Console/Go API), `local` (OpenCode V2 server). |
| Models | **Free default → paid default → local**, no research required | `glm-5.3-flash-free` → `qwen3.8-flash` → `qwen3:8b` (Ollama). See §7. |
| PDF generation | **HTML → PDF via headless Chromium (Playwright)** | Reuses the recap UI, correct Unicode for Arabic, no font bundling; Edge channel avoids a 300 MB download. |
| Export | **PDF download only** | Email deferred; simplifies M5 and removes SMTP secrets. |
| Session memory | **Ephemeral, in-memory, one active session** | Nothing on disk; the PDF is the only record. A new session is a new agent with no memory. |
| Language | Levantine colloquial Arabic, Spanish, Swedish | UI language English only. STT locale per language. |
| Tone | Menu: conversation partner, formal interview, OPI examiner, debate, storytelling | Tone is part of the system prompt and changes elicitation strategy. |
| Overrides | **None in the MVP** | Marasa's judgements are final; the recap is the record. |
| Network | **LAN sharing** (`scripts/serve.ps1`) | The app is served on `0.0.0.0` so a phone can use it; one session is shared by all devices and clients poll it every 2.5 s to stay in sync. No auth — trusted-network only. Voice needs HTTPS, so it stays localhost-only |
| Rubric source | *OPI Familiarization Guide 2020* → `backend/app/tutor/rubric.py` | Paraphrased descriptors with attribution; PDF is gitignored (not redistributable). |
| Email | **Removed** | — |

---

## 3. Architecture

```
┌────────────── React (Vite + TS + Tailwind) ──────────────┐
│ Start · Session · Recap                                     │
│ Web Speech API (STT) · SSE reader                          │
└───────────────┬──────────────────────────────────────────┘
                │  /api/*  (JSON + SSE)
┌───────────────▼──── FastAPI (uvicorn, 127.0.0.1:8000) ────┐
│ api.py    sessions · turns(SSE) · recap.pdf                │
│ session.py  in-memory store (one active session)           │
│ tutor/   prompts · rubric · notes-parser · languages · tones│
│ providers/ mock · ollama · console(M1) · local(M1.5)       │
│ export/  html → pdf (Playwright) + recap template          │
└───────────────┬──────────────────────────────────────────┘
                │  https://opencode.ai/inference/*        (user's key)
                │  http://127.0.0.1:<port>/api/*          (opencode serve)
                │  http://127.0.0.1:11434/api/chat       (ollama)
```

### 3.1 Repository layout (as built)

```
marasa-ai/
├─ README.md            setup, models, languages/tones, licensing
├─ PLAN.md              this document
├─ .env.example         configuration template
├─ .gitignore           .venv, node_modules, data/, .env, OPI PDF
├─ backend/
│  ├─ pyproject.toml    dependencies + dev group
│  ├─ uv.lock           exact resolved versions
│  ├─ .python-version   3.12
│  ├─ .venv/            created by `uv sync` (not committed)
│  ├─ app/
│  │  ├─ main.py        app factory, CORS (dev), serves frontend/dist
│  │  ├─ api.py         HTTP routes
│  │  ├─ config.py      settings from env
│  │  ├─ session.py     in-memory session model + store
│  │  ├─ providers/     base · mock · ollama · (console M1) · (local M1.5)
│  │  ├─ tutor/         prompts · rubric · notes · languages · tones
│  │  └─ export/        pdf.py + templates/recap.html.j2
│  └─ tests/            api + tutor unit tests
├─ frontend/
│  ├─ package.json, package-lock.json
│  ├─ vite.config.ts    dev proxy /api → 127.0.0.1:8000
│  └─ src/              App · components/{Start,Session}Screen · lib/{api,sse,speech}
└─ scripts/             setup · dev · test  (.ps1 and .sh)
```

### 3.2 Provider interface

One interface, four implementations. Everything above the provider layer is provider-agnostic.

```python
class Provider(Protocol):
    name: str
    async def list_models(self) -> list[ModelInfo]: ...
    def stream(self, request: TurnRequest) -> AsyncIterator[StreamChunk]: ...
```

`TurnRequest` carries `session_id`, `system`, `messages`, `model`, `temperature`, `max_tokens`.
`StreamChunk` carries `delta` text plus optional `Usage` (`input_tokens`, `output_tokens`, `cost_usd`, `allowance_usd`, `billing_source`).

| Provider | Status | Notes |
| --- | --- | --- |
| `mock` | done | Deterministic scripted replies with a valid notes block; backbone of tests and offline UI work |
| `ollama` | **done, verified end to end** | `POST /api/chat` streaming (NDJSON); free, private, no key. Raises `num_ctx` to 8K and disables Qwen3 "thinking" mode. Covered by `tests/test_providers.py` |
| `console` | M1 | OpenCode Console / Go inference API. Bearer auth, per-family endpoints (chat-completions, anthropic-messages, responses), `x-opencode-session` header + real user agent so usage bills the Go allowance correctly, cost/allowance capture, 401/403/429 error mapping |
| `local` | M1.5 | OpenCode **V2** server: `POST /api/session` → `POST /api/session/{id}/prompt` → consume `GET /api/event` (`session.text.delta`). This is the path that unlocks the free-tier chat models, which the Console API refuses for third-party clients (`403`) |

### 3.3 Session model (in-memory)

```python
Session(id, language_id, tone_id, mode, topics, vocab_terms,
        level, target_level, provider, model, status,
        created_at, ended_at,
        messages: list[Message], observations: list[Observation],
        next_steps: list[str], usage: dict)
```

- Exactly **one active session**. Starting another returns `409`; the UI asks the learner to discard the current one first.
- **The session is shared by every device on the network.** The store lives in the backend process, and each client polls `GET /api/sessions/{id}` every 2.5 s and merges the server's transcript (the source of truth) with its local list, so a phone and a computer stay in sync. A reply still streaming is kept locally until the server has the final text.
- The UI can always find the session the backend holds: `GET /api/sessions/active` (and `DELETE /api/sessions/active`) work without knowing the id, so a page reload cannot strand the learner in a conflict loop. The `409` body carries `active_session_id` as well.
- Closing the session view keeps the session alive so the start screen can offer **Resume** or **Discard**; "Start a new session" discards it.
- Nothing is written to disk. Closing Marasa erases everything.
- The recap PDF is the only durable artefact; a previous recap PDF can be fed back in as session input.

### 3.4 API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | App + provider readiness |
| `GET` | `/api/settings` | Provider, model, key-configured flag, languages, tones (never the key) |
| `GET` | `/api/models` | Models for the active provider |
| `POST` | `/api/sessions` | Create a session (topic, language, tone, mode) → resolved setup. `409` if one is already open (body carries `active_session_id`) |
| `GET` | `/api/sessions/active` | The session the backend still holds — lets the UI resume or discard after a reload |
| `DELETE` | `/api/sessions/active` | Discard the running session without knowing its id |
| `GET` | `/api/sessions/{id}` | Messages, observations, usage |
| `POST` | `/api/sessions/{id}/turns` | SSE: `delta`, `notes`, `usage`, `error` |
| `POST` | `/api/sessions/{id}/end` | Finalise the session, freeze the level estimate |
| `POST` | `/api/sessions/{id}/recap.pdf` | Render + return the PDF |
| `DELETE` | `/api/sessions/{id}` | Discard the session (erase from memory) |

### 3.5 Tutor prompt contract

System prompt = persona/tone + language policy + OPI level + difficulty target + topics/vocab + turn policy + strict output format.

```
<reply>

<marasa_notes>
{"vocab": [{"term": "", "meaning": "", "status": "strong|gap|useful", "evidence": ""}],
 "grammar": [{"concept": "", "status": "strong|gap", "note": ""}],
 "level_delta": {"grammar": 0, "vocab": 0, "discourse": 0},
 "next_step": ""}
</marasa_notes>
```

- Parsed server-side (`tutor/notes.py`), stripped from the reply; a malformed block **never** breaks the conversation (reply is kept, notes dropped).
- The frontend replaces the streamed text with the server's cleaned reply when the `notes` event arrives.
- `level_delta` is clamped to ±1 sublevel per turn and applied by the ladder in `tutor/rubric.py`.

### 3.6 OPI rubric

`tutor/rubric.py` holds the ordered ladder **NL → NM → NH → IL → IM → IH → AL → AM → AH → S**, each with a paraphrased summary, text type and accuracy expectation, derived from the *OPI Familiarization Guide 2020* (which reproduces the ACTFL Proficiency Guidelines 2012 – Speaking). The same table drives difficulty targeting and the final score, so the conversation and the score stay consistent. Sessions start at **IM** because the OPI protocol assumes an Intermediate-level conversation to begin with.

Every recap states that the score is an estimate, not an official ACTFL rating.

### 3.7 Context management

Keep the system prompt + first turn + the **last 20 messages** + a running digest; fold trimmed turns into a compact summary (one cheap call per 10 turns). Observations live in the session object, not in the prompt, so trimming loses nothing.

---

## 4. Feature design

### 4.1 Start
- One centred card: *"What would you like to talk about?"*; empty input in voice mode is allowed (Marasa opens the conversation).
- Segmented **Text | Voice**; language select (`Auto`, Spanish, Levantine Arabic, Swedish); tone select (five tones with one-line blurbs).
- If a session is still open, a card above the form offers **Resume session** / **Discard it**.
- "Attach vocab sheet (.pdf)" → parsed list shown as editable chips before the session starts.
- Starting a conversation while another is open raises an in-app dialog: *"A session is already running"* → discard it (and continue into the new one) or keep it. No native `window.confirm`.
- Honest footer: *"Sessions are not saved. Download the recap PDF to keep a record."*

### 4.2 Session
- Marasa left / learner right; topic, language, tone, active model and a live level chip in the header; "End session".
- Voice mode: mic button (Web Speech API), interim transcript, permission/unsupported fallbacks. Voice is unavailable over plain HTTP on a LAN address (secure-context rule) — the app says so rather than failing silently.
- The composer carries the target language's `lang` and `dir`, so a phone shows the right keyboard (Arabic right-to-left included).
- Observations are **not** shown mid-session; they appear in the recap.

### 4.3 Recap
Summary · Vocabulary (strengths / gaps / useful) · Grammar · OPI scorecard (level + per-domain confidence + evidence) · Next steps · **Download recap PDF** · Start a new session (discards the current one).

---

## 5. Milestones

| # | Milestone | Estimate | Status |
| --- | --- | --- | --- |
| M0 | Foundations: repo scaffold, uv venv + lock, Vite app, FastAPI skeleton, in-memory session store, mock provider, design tokens, setup/dev/test scripts | 1 day | **done** |
| M0.5 | Local Ollama provider: streaming adapter, `num_ctx`/thinking-mode tuning, `scripts/setup-ollama.ps1`, verified end to end with `qwen3:8b` | 0.5 day | **done, verified** |
| M1 | OpenCode Console/Go provider: model list, streaming, cost/allowance telemetry, error mapping, settings sheet with "Test connection" | 1–1.5 days | next |
| M1.5 | Local OpenCode V2 provider: discover/spawn `opencode serve`, session + prompt + event stream, free-tier model access | 0.5–1 day | pending |
| M2 | Session core: setup inference (language/topic/level), turn pipeline, SSE client, live level tracking | 2 days | scaffolded |
| M3 | Vocab ingestion: PDF text extraction, LLM normalisation + neighbouring words, editable chips; also accept a previous recap PDF to seed focus and starting level | 1–1.5 days | pending |
| M4 | OPI tracking + assessment + recap: rubric-driven adaptation with hysteresis, end-of-session assessment, recap screen, recommendations | 2 days | scaffolded |
| M5 | PDF export: Jinja recap template, Playwright render, download button | 1.5 days | **done (scaffold)** |
| M6 | Voice mode: Web Speech recognition per language, interim results, graceful fallback, optional TTS | 1 day | pending |
| M7 | Polish + hardening: Apple-style pass, dark mode, empty/error states, context compaction, retry/backoff, model bake-off, README/docs | 2 days | pending |

**Total remaining: ~9–11 working days.**

---

## 6. Packaging and onboarding (done)

Goal: *clone → one command → running app*, with every dependency pinned and project-local.

| Piece | Choice | Why |
| --- | --- | --- |
| Python env | `uv` + `backend/uv.lock` + `backend/.venv` | Reproducible resolution, fast installs, one file to commit, `.venv` is disposable |
| Python version | `.python-version` = 3.12 | Best wheel coverage for pydantic/playwright; uv fetches CPython automatically |
| Frontend deps | `npm ci` + `frontend/package-lock.json` | Exact versions, reproducible, no global installs |
| Entry points | `scripts/setup.ps1`, `scripts/dev.ps1`, `scripts/test.ps1` (+ `.sh` for macOS/Linux) | One command per job; scripts verify prerequisites and print next steps |
| Secrets | `.env` (gitignored) with `.env.example` | Key never enters the repo or the browser |
| Runtime data | none — sessions are in memory | Matches the ephemeral-session decision |

Setup script behaviour: check Python → install uv if missing → `uv sync` → check/install Node → `npm ci` → create `.env` if absent → run both test suites → print next steps.

---

## 7. Model strategy (researched)

### 7.1 Free models available through OpenCode

Free-tier chat models are served to signed-in OpenCode clients; the Console inference API returns `403` for them from third-party clients, so they are reached via the local OpenCode server path (M1.5) or the Go endpoint.

| Model | Privacy | Verdict |
| --- | --- | --- |
| `glm-5.3-flash-free` | zero retention, no training | **Default free model** — 1M context, strongest general instruction-following among the free tier |
| `deepseek-v4.1-flash-free` | zero retention, no training | Alternative free model |
| `beam-free` | no training, 30-day retention | Unavailable in many regions (incl. Syria, Iraq) |
| `mimo-v2.6-flash-free` | data may be used to improve the model | Only with consent |
| `nemotron-3-*-free` | NVIDIA trial endpoints, session data logged | Avoid for private content |
| `big-pickle`, `flint-40b-free`, `iceman-contributor-free` | data may be used to improve | "Limited time" stealth models; experimental |

**Default free model: `glm-5.3-flash-free`.** Caveat: no free-tier model handles colloquial Levantine well — Arabic practice should use the paid default or a local Arabic-tuned model.

### 7.2 Paid default

**Default paid model: `qwen3.8-flash`** (~$0.15 in / ~$0.47 out per 1M tokens; Go allowance $30/month on the Go plan). Qwen's Arabic/Spanish/Swedish coverage is the best value on the platform.

| Alternative | Price (in/out) | Use for |
| --- | --- | --- |
| `qwen3.8-max` | $2.00 / $6.00 | Best Arabic quality on OpenCode — recommended for Levantine practice |
| `minimax-m3` | $0.30 / $1.20 | Strong general chat, good with strict output formats |
| `glm-5.3-flash` | $0.15 / $0.50 | Cheapest credible non-free tier |
| `claude-haiku-5-5` | $0.10 / $0.50 | Very cheap, good instruction following |
| `kimi-k3.1-pro` | $2.00 / $10.00 | Complex argument/discourse work |

### 7.3 Local models (Ollama)

**Recommended default: `qwen3:8b`** (~5.2 GB, Apache-2.0, 119 languages, strong Arabic/Spanish/Swedish, 32K+ context).

| Need | Model | Size (Q4) | Why |
| --- | --- | --- | --- |
| Default | `qwen3:8b` | ~5 GB | Best all-round multilingual value |
| Better Arabic | `qwen3:14b` | ~9 GB | Noticeably better Arabic, same family |
| Best Levantine dialect | `falcon-h1-arabic:7b` | ~5 GB | Arabic-native, regional dialect coverage |
| Best Arabic quality | `fanar-2` (27B) | ~16–17 GB | MSA + Gulf/Levantine/Egyptian, Apache-2.0 |
| Egyptian dialect | `nile-chat:12b` | ~12 GB | Dialect-specific fine-tune |
| Personal use only | `aya-expanse:8b` | ~5 GB | Excellent Arabic but CC-BY-NC-4.0, 8K context on Ollama |
| Avoid for Arabic | `mistral*`, `llama3.1:8b`, `gemma3:4b` | — | Weak Arabic |

Practical floor: 8B Q4 ≈ 6 GB RAM/VRAM (CPU-only works, slowly); 14B wants 12 GB+; 27B wants 24–32 GB.

### 7.4 Product rules

1. Start on the free default; no key, no research.
2. With a key configured, the paid default is a one-click upgrade and session cost is displayed live.
3. Local model is opt-in with `qwen3:8b` pre-selected.
4. Provider failures (401/403/429/model unavailable) are reported explicitly with the fallback offered — never a silent downgrade.
5. A model bake-off over a fixed prompt set (M7) keeps these defaults evidence-based.

---

## 8. Risks and mitigations

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| 1 | Conversation quality is the product's core risk (README "Cost") | High | Provider abstraction; free → paid → local ladder; bake-off in M7; dialect-specific caveat documented |
| 2 | Free-tier models are unavailable to third-party clients (`403`) | Medium | Local OpenCode provider path (M1.5) |
| 3 | Levantine Arabic quality is poor on small/free models | High | Recommend `qwen3.8-max` or a local Arabic-tuned model for Arabic; the dialect instruction in the prompt is explicit |
| 4 | OPI rubric inaccuracy → misleading scores | High | Descriptors paraphrased from the official guide with attribution; evidence quotes in the recap; labelled an estimate |
| 5 | **ACTFL material is proprietary** | High | Guide is gitignored, not redistributed; rubric is paraphrased; recap states it is not an official rating; keep the repo private or review terms before publishing |
| 6 | Web Speech API support/accuracy varies | Medium | Chrome/Edge first-class; Firefox/Safari fall back to text; Arabic STT is the weakest case — text mode is the reliable path for Arabic |
| 7 | Python 3.14 wheel gaps on the host machine | Low | uv pins CPython 3.12 and downloads it automatically |
| 8 | Playwright browser download (~300 MB) on Windows | Low | Default to the installed Edge channel; `setup -WithChromium` opts in |
| 9 | Local OpenCode HTTP API is experimental and may change | Medium | Adapter isolated in one file; require OpenCode ≥ 2.x; Console path independent |
| 10 | Long sessions exceed context / cost | Medium | Compaction (§3.7), per-turn token accounting, live cost indicator |
| 11 | PDF text extraction quality (layouts, tables, scans) | Medium | Show the extracted list for editing; scanned PDFs explicitly unsupported |
| 12 | Key leakage | High | Server-side only; `/api/settings` never returns it; localhost bind; `.env` gitignored |
| 13 | Ephemeral sessions surprise users | Medium | Persistent in-app notice + footer; recap PDF prompts before closing |
| 14 | Local model too slow on a small GPU | Medium | 6 GB VRAM cards partially offload `qwen3:8b` to RAM; `qwen3:4b` fits fully in VRAM. `MARASA_OLLAMA_NUM_CTX` trades context for speed |
| 15 | Local model quality ceiling (dialect naturalness) | High | Documented in README: Arabic practice should use `qwen3.8-max` (Console) or a dialect-tuned local model |
| 16 | Playwright cannot start under `uvicorn --reload` on Windows | **resolved** | uvicorn switches to a selector event loop when `--reload` is on, and a selector loop cannot spawn subprocesses. The renderer now runs Playwright's sync API in a worker thread and installs the proactor policy for the duration. Regression test: `tests/test_export.py` |
| 17 | A model answers with the notes block only | **resolved** | The server falls back to the model's own `next_step`, then to a language-appropriate continuation, so the learner never sees an empty bubble. Test: `tests/test_api.py` |
| 18 | **The app was unusable from a phone** — `crypto.randomUUID()` is secure-context only, so it threw on `http://<lan-ip>:8000`: the input cleared, no request was sent, and nothing appeared | **resolved** | Message ids come from a counter (`frontend/src/lib/id.ts`), `send()` can no longer fail silently, errors are shown in the session view, and a vanished session returns the learner to the start screen with an explanation. Test: `frontend/src/lib/id.test.ts` |

---

## 9. Testing strategy

**Backend (pytest)** — note parser (valid/malformed/absent block), level ladder and clamping, session lifecycle (second session refused, discard, end), SSE endpoint, settings payload.
**Frontend (vitest)** — SSE buffer parsing, payload parsing.
**End-to-end (Playwright, `MARASA_PROVIDER=mock`)** — golden path: start → turns → end → recap → PDF download; voice path with a mocked `SpeechRecognition`; non-Latin language fixture for Unicode rendering.
**Manual matrix** — Chrome + Edge; text + voice; Arabic/Spanish/Swedish; 3-turn and 40-turn sessions; missing key, invalid key, quota exceeded, no browser installed, Ollama not running.

---

## 10. Definition of Done (MVP)

- [x] Clone → `scripts/setup.ps1` → running app, all dependencies project-local and locked.
- [x] Start screen with language, tone and mode selection; session lifecycle with one active session.
- [x] Streaming conversation with note parsing and level tracking.
- [x] Recap PDF download (Playwright + Edge).
- [ ] OpenCode Console/Go provider with cost telemetry (M1).
- [ ] Local OpenCode V2 provider for free-tier models (M1.5).
- [ ] PDF vocab-sheet ingestion, incl. previous-recap PDF as focus input (M3).
- [ ] End-of-session assessment with per-domain confidence and recommendations (M4).
- [ ] Voice mode with per-language recognition and fallbacks (M6).
- [ ] Apple-style polish pass, dark mode, context compaction, model bake-off (M7).
- [ ] No secret ever returned to the client; backend binds localhost only.

---

## 11. Environment notes

- **Node 26.13.0** was installed via Scoop for this project (it was missing). Node 20+ is the only external requirement for the frontend.
- **Ollama 0.40.13** was installed via Scoop; `qwen3:8b` (5.2 GB) is pulled and verified. GPU: Quadro P3200, 6 GB VRAM (5.1 GB free) — the 8B model partially offloads to system RAM (64 GB), so expect ~6 s/turn once warm and ~25 s for the first turn while the model loads. `qwen3:4b` fits fully in VRAM if speed matters more than quality.
- **Python**: the host has 3.14.8, but the project pins **3.12** through uv (`backend/.python-version`), which uv downloads automatically — this avoids wheel gaps on 3.14.
- **Windows event loops**: uvicorn uses a selector event loop when `--reload` is enabled, which breaks Playwright's async API. The PDF renderer works around it (see §8 risk 16). Note also that the file watcher can miss edits made by external tools — restart the dev script when a change does not take effect.
- **OpenCode CLI mismatch (diagnosed)**: the desktop app bundles **OpenCode v2.1.4**, which migrated the shared database (`~/.local/share/opencode/opencode.db`) to the V2 schema (`session_v2`, `session_message`, `session_inbox`, migrations up to `20261010180456_project_time_archived`). The Scoop-installed CLI is **1.19.3** (V1) and looks for a legacy `session` table; finding a non-empty database without it, it refuses to start: *"Database is not empty and has no session table"*. It is **not** caused by using the app instead of the CLI — it is a version mismatch on a shared data directory. Fixes: install the V2 CLI alongside the desktop app, run the old CLI with `--standalone` (private server and database), or point it at a separate database with `OPENCODE_DB`. **The MVP's local provider must target OpenCode ≥ 2.x** (`opencode serve`, `/api/session`, `/api/event`).

---

## 12. Questions answered by the owner

| Question | Answer | Effect on the plan |
| --- | --- | --- |
| Target languages | Levantine colloquial Arabic, Spanish, Swedish; UI English only | §3.6 dialect instruction, §4.1 language list, STT locales |
| OPI rubric source | *OPI Familiarization Guide 2020* added to the repo | `tutor/rubric.py` paraphrases it; guide gitignored (§8 risk 5) |
| Email | Remove for the MVP; PDF download only | M5 simplified, no SMTP secrets |
| Transcript lifetime | Ephemeral; disappear when the tool closes; a new session is a new agent with no memory; a previous PDF can be re-submitted to focus the next session | §3.3 in-memory store, one active session, M3 accepts recap PDFs |
| User overrides | Not in the MVP | No override UI |
| Persona | Tone menu: formal interview, friend, etc. | Five tones in `tutor/tones.py` and the start screen |

---

## 13. Non-goals for the MVP

Cross-session memory · session history · email export · spaced-repetition/flashcard SRS · curriculum or course structure · multi-user accounts and hosted deployment · mobile apps · recording or uploading learner audio · neural TTS/STT beyond the browser APIs · payment/billing UI · plugins or extensions · analytics/telemetry · dictionary integrations beyond the model's own knowledge.

## 14. Next actions

1. **M1 — OpenCode Console/Go provider.** Unblocks real conversations on the paid default and unlocks the free-tier models through the Go endpoint; bring up cost/allowance telemetry at the same time.
2. **M1.5 — Local OpenCode V2 provider.** Needed for the free default `glm-5.3-flash-free`; also requires OpenCode ≥ 2.x on the host.
3. **M3 — PDF ingestion**, including reading a previous recap PDF to seed the next session's focus and starting level.
4. **M4 — final assessment** with per-domain confidence and recommendations (the recap currently shows observations and the live level).
5. **M7 — model bake-off** across `glm-5.3-flash-free`, `qwen3.8-flash`, `qwen3.8-max` and `qwen3:8b` on a fixed Arabic/Spanish/Swedish prompt set, to confirm (or replace) the defaults.
