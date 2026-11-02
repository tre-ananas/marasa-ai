# marasa-ai

> **Status:** MVP scaffold — the app runs end to end today (text conversation, OPI tracking, recap PDF).
> See [`PLAN.md`](./PLAN.md) for the implementation plan and milestone status.

# General Overview
`Marasa AI` derives its name from the Arabic root for practicing becoming accustomed to something. In this case, `Marasa AI` aims to help language enthusiasts practice fluency and build their vocabulary without paying for expensive tutors, grinding flashcards, and navigating the difficulties of timezones and vetting human resources. Ultimately, students using `Marasa AI` can expect to produce substantially higher volumes of output while simultaenously identifying gaps in their knowledge, permitting a more targetted approach to "input" sessions. **Note**: as an output-oriented tool, `Marasa AI` specifically benefits intermediate and advanced language learners; if a student does not have requisite knowledge to practice speaking, he or she will likely not engage with `Marasa AI` in a productive manner.

# Primary Functions & Workflow
1. The user has the ability to enter a specific set of topics or enter a vocab sheet (.pdf) that he or she would like to focus on. If the session begins with no user input, `Marasa` will start by asking what the user would like to speak about and use that input as the session topic. The user also selects whether input will be via text or via voice chat, as well as the language. Once again, if not selected, these options will be decided based on the initial user prompt.
2. The user then engages in a targeted discussion in which `Marasa` uses the provided topics and vocab words (as well as neighboring words) to try to reinforce proficiency and, should user aptitude be high enough, stretch the user's abilities. Throughout the conversation, `Marasa` will actively track the user's abilities according to teh ACTFL Oral Proficiency Interview (even if the conversation is written) and adjust register, vernacular, and general difficulty to meet or slightly exceed the user's abilities. As part of the conversation, `Marasa` may ask or respond to questions to encourage conversation, develop new ideas and topics, or gauge user abilities with certain constructs or words.
3. Throughout the session, `Marasa` will note words and grammatical concepts that the user does well on, as well as words and concepts the user could improve on or may find useful. `Marasa` will also track the user's OPI rating for the session. At the end of the session, `Marasa` will provide a session recap, summarizing what was discussed, an assessment of vocab and grammar, recommendations for future study and practice, and the session-level OPI score. OPI scoes will be more accurate with longer conversations and may fluctuate from session to session as topics change and users have "good" or "bad" days--all perfectly normal fluctuations in the journey of langauge learning!
4. After the session, the user can download the feedback as a .pdf file. *(MVP decision: email delivery is deferred — the downloaded PDF is the only durable artefact of a session.)*

# Cost
1. Ideally, we can use free tools and models to practice. If the bottleneck is the LLM's ability to properly converse, however, then we can consider having users provide access to their OpenCode account and route their usage through a more proficient model using their own OpenCode/OpenCode Go budget.

# Minimal Viable Product
1. Focus on producing a minimalistic, simple UI that cannot be misunderstood. Think Apple-style design.
2. Ship the features listed as "Primary Functions" above without adding anything unnecessary. We want something that works before we build nice-to-haves.

---
---

# Running Marasa AI

Everything is installed **inside the repository**, so a clone is self-contained: the Python environment lives in `backend/.venv` (created by `uv` from the committed `backend/uv.lock`), and the frontend dependencies live in `frontend/node_modules` (installed from the committed `frontend/package-lock.json`). Nothing is installed globally except `uv` itself and, if it is missing, Node.js.

## Prerequisites

| Requirement | Version | Notes |
| --- | --- | --- |
| Python | 3.12+ | `uv` downloads a pinned CPython 3.12 automatically if the system Python is missing or too old |
| [uv](https://docs.astral.sh/uv/) | any recent | Python package/project manager; installs and locks the backend environment |
| Node.js | 20+ | only needed to build the React frontend |

## Setup

**Windows (PowerShell)**

```powershell
git clone <your-fork-url> marasa-ai
cd marasa-ai
.\scripts\setup.ps1
```

**macOS / Linux**

```bash
git clone <your-fork-url> marasa-ai
cd marasa-ai
chmod +x scripts/*.sh
./scripts/setup.sh
```

`setup` does the following:

1. verifies Python 3.12+ and installs `uv` if it is missing;
2. `uv sync` — creates `backend/.venv` and installs the exact locked versions;
3. installs `frontend/node_modules` with `npm ci` (exact locked versions);
4. copies `.env.example` to `.env` (never overwritten if it already exists);
5. runs the test suites as a smoke check.

PDF rendering uses the **Microsoft Edge already installed on Windows**, so no browser download is needed. On macOS/Linux, or to force the bundled Chromium, run `setup.ps1 -WithChromium` (or `uv run playwright install chromium` in `backend/`).

## Run

```powershell
.\scripts\dev.ps1      # Windows
./scripts/dev.sh       # macOS / Linux
```

Then open **http://127.0.0.1:5173**. The backend runs on http://127.0.0.1:8000 (`/api/health` shows which provider is active).

The script picks the **first free port** for each service (8000 → 8001 → …, 5173 → 5174 → …), so a server left running from an earlier session never blocks you, and it prints the URLs it actually used. Backend and frontend logs are written to `data/logs/`.

For a single-process deployment, build the frontend (`npm run build` in `frontend/`) and start only the backend — FastAPI then serves `frontend/dist` directly.

### Use it from your phone (or another device)

`scripts/serve.ps1` builds the frontend and serves everything — UI and API — from **one port**, bound to every network interface:

```powershell
.\scripts\serve.ps1
```

It prints the URL to open on your phone, for example `http://10.0.0.48:8000`. Any device on the same Wi-Fi can open it, and **all devices share one session**: start a conversation on the computer, pick it up on the phone, and the transcript stays in sync (each client polls the shared session every 2.5 seconds). Because a session is shared, the start screen offers **Resume session** when one is already running.

What works over the LAN:

| | |
| --- | --- |
| Text conversation | ✅ on every device |
| Shared session, live transcript | ✅ |
| Recap PDF | ✅ (downloaded by whichever device ends the session) |
| Language keyboard | ✅ the composer is tagged with the target language (`ar`, `es`, `sv`), so a phone switches to the right keyboard — including Arabic, right-to-left |
| **Voice input** | ❌ over plain HTTP — browsers only allow microphone access in a secure context (HTTPS or localhost). Text is the point of using the phone, so this is a reasonable trade; see below if you want voice on the LAN |

Notes:

- **Windows firewall.** The first time, Windows may ask to allow connections through the firewall. If it does not, allow `python.exe` (the backend) on the Private network profile. There are already allow rules for `python.exe` and `node.exe` on this machine.
- **No authentication.** Anyone on your network can use the app and read the session. That is acceptable on a trusted home Wi-Fi; do not expose the port to the internet. Sessions are ephemeral, so nothing is kept once Marasa stops.
- **Voice on the LAN** would need HTTPS: you would have to put a reverse proxy with a certificate in front of the app, and a self-signed certificate is awkward to trust on a phone. Not worth it for the MVP.
- **Plain HTTP is an insecure origin**, so browser APIs that require a secure context are unavailable there: microphone access (voice input) and `crypto.randomUUID()`. Marasa does not use `crypto.randomUUID()` — message ids come from a counter — so everything else works over plain HTTP. See `frontend/src/lib/id.ts`.
- After an update, refresh the page on each device: the shell is served with `Cache-Control: no-cache` so the browser picks up the new bundle, but a phone that is left open keeps the old one until it reloads.

For development with the same network exposure (Vite dev server instead of the built bundle):

```powershell
.\scripts\dev.ps1 -Expose
```

### Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| "No free port found near 8000" | every port in the range is taken | stop the stray server, or pass `-BackendPort 8100` |
| Changes to backend code do not take effect | the file watcher missed the edit | restart the dev script (Ctrl+C, then run it again) |
| `recap.pdf` returns 500 | Playwright cannot start its browser | check `data/logs/backend.error.log`; on Windows the renderer forces the proactor event loop, so this is normally handled |
| Every reply is identical | the `mock` provider is active (offline, scripted) | set `MARASA_PROVIDER=ollama` (see [Models](#models)) or start a provider |
| "connection refused" from Ollama | the Ollama server is not running | run `ollama serve`, or `.\scripts\setup-ollama.ps1` |

## Configuration

Everything is configured through `.env` (see [`.env.example`](./.env.example)):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MARASA_PROVIDER` | `mock` | `mock` (offline), `console` (OpenCode Console/Go), `local` (OpenCode V2 server), `ollama` (local model) |
| `MARASA_MODEL` | *(empty)* | model id; empty means "use the provider's default" |
| `MARASA_OPENCODE_API_KEY` | — | your own OpenCode Console / Go API key (never leaves the backend) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | local Ollama server |
| `MARASA_OLLAMA_MODEL` | `qwen3:8b` | recommended local model |
| `MARASA_OLLAMA_NUM_CTX` | `8192` | context window for the local model |
| `MARASA_PDF_ENGINE` | `edge` | `edge` or `chromium` |
| `MARASA_HOST` / `MARASA_PORT` | `127.0.0.1` / `8000` | backend bind address (localhost only, by design) |

The API key is read from the environment on the server and is **never** returned to the browser.

---
---

# Models

The rule for Marasa: **free by default, one obvious paid upgrade, and a local option for people who want nothing leaving their machine.** Users should never have to research models to use the product.

### What works today

| Path | Status | Cost | Privacy |
| --- | --- | --- | --- |
| **Local model (Ollama)** — `qwen3:8b` | ✅ **wired up and verified** | free | everything stays on your machine |
| OpenCode Console / Go — `qwen3.8-flash` | 🚧 milestone M1 (adapter not written yet) | your Go allowance / balance | hosted by OpenCode |
| OpenCode local server — `glm-5.3-flash-free` | 🚧 milestone M1.5 (needs OpenCode ≥ 2.x) | free | hosted by OpenCode, 30-day retention |
| `mock` provider | ✅ available | free | offline, scripted — for tests and UI work only |

Until M1 and M1.5 land, the app talks for real through Ollama. The Console/Go path only needs an API key from [opencode.ai/console](https://opencode.ai/console) plus the adapter; the free OpenCode models additionally need the V2 CLI (the desktop app already ships one).

## Default free model — `glm-5.3-flash-free`

Reached through the OpenCode path (free-tier chat models are only served to signed-in OpenCode clients; OpenCode's Go endpoint and the local OpenCode server both expose them).

| Property | Value |
| --- | --- |
| Cost | free, unlimited on the Go plan; does not consume the paid allowance |
| Privacy | **zero retention, not used for training** |
| Context | 1M tokens |
| Best for | Spanish and Swedish practice; solid general conversation and instruction following |

Free-model alternatives, in the order we would fall back to them:

| Model | Privacy | When to prefer it |
| --- | --- | --- |
| `deepseek-v4.1-flash-free` | zero retention, no training | stronger reasoning per token; good second choice |
| `mimo-v2.6-flash-free` | data may be used to improve the model | only if you accept the training terms |
| `beam-free` | no training, 30-day retention | unavailable in many regions (including Syria and Iraq) |
| `nemotron-3-ultra-free` | NVIDIA trial endpoints, session data logged | avoid for anything private |
| `big-pickle`, `flint-40b-free`, `iceman-contributor-free` | data may be used to improve the model | "limited time" stealth models — treat as experimental |

> **Caveat for Levantine Arabic:** no free-tier model is strong in colloquial Levantine. Expect stilted MSA-ish output. For Arabic, use the paid default below or a local Arabic-tuned model.

## Default paid model — `qwen3.8-flash`

Used when the free model is not configured, when the free model is unavailable, or when the learner opts in from the settings sheet.

| Property | Value |
| --- | --- |
| Cost | ~$0.15 / 1M input tokens, ~$0.47 / 1M output tokens (per-request billing is reported in the session strip) |
| Why | Best multilingual value for our three target languages (Arabic, Spanish, Swedish); Apache-2.0 weights; long context |
| Endpoint | Anthropic Messages (Console also exposes it via the OpenAI-compatible path) |

Paid alternatives worth exposing in the settings sheet:

| Model | Price (in/out per 1M) | When to prefer it |
| --- | --- | --- |
| `qwen3.8-max` | $2.00 / $6.00 | Best Arabic quality on OpenCode; use it for Levantine practice |
| `minimax-m3` | $0.30 / $1.20 | strong general chat, good with strict output formats |
| `glm-5.3-flash` | $0.15 / $0.50 | cheapest credible non-free tier |
| `claude-haiku-5-5` | $0.10 / $0.50 | very cheap; good instruction following |
| `kimi-k3.1-pro` | $2.00 / $10.00 | expensive; best for complex argument/discourse work |

On the **OpenCode Go** plan these prices are the allowance rate: each model draws from a monthly dollar allowance (for example `qwen3.8-flash` has a $30/month allowance on Go), and the free models above are unlimited and cost nothing.

## Local models (Ollama) — private and free

For people who do not want any conversation leaving their machine, Marasa talks to a local Ollama server. **This path is implemented and verified** — it needs no key and no account.

```powershell
.\scripts\setup-ollama.ps1          # installs Ollama, pulls qwen3:8b, verifies a completion
```

or by hand:

```bash
ollama pull qwen3:8b
```

then point Marasa at it in `.env`:

```dotenv
MARASA_PROVIDER=ollama
MARASA_MODEL=                 # empty = use the provider's default model
MARASA_OLLAMA_MODEL=qwen3:8b
MARASA_OLLAMA_NUM_CTX=8192    # Ollama defaults to 4K, too small for the tutor prompt
```

**Recommended default: `qwen3:8b`** (~5.2 GB download)

- Apache-2.0 licence, 119 languages, good Arabic/Spanish/Swedish coverage, 32K+ context, strong at following the structured note format Marasa needs.
- The adapter turns Qwen3's "thinking" mode off (its output would be discarded anyway) and raises the context window to 8K.

Local model picks by need:

| Need | Model | Size (Q4) | Why |
| --- | --- | --- | --- |
| Default, all three languages | `qwen3:8b` | ~5 GB | Apache-2.0, best all-round multilingual value |
| Better Arabic | `qwen3:14b` | ~9 GB | same family, noticeably better Arabic |
| Best Levantine dialect | `falcon-h1-arabic:7b` | ~5 GB | Arabic-native, covers regional dialects, permissive licence |
| Best Arabic quality (big) | `fanar-2` (27B) | ~16–17 GB | MSA + Gulf/Levantine/Egyptian dialect coverage, Apache-2.0 |
| Egyptian dialect | `nile-chat:12b` | ~12 GB | dialect-specific fine-tune |
| Personal-use Arabic | `aya-expanse:8b` | ~5 GB | excellent Arabic, but **CC-BY-NC-4.0** (non-commercial) and only 8K context on Ollama |
| Avoid for Arabic | `mistral*`, `llama3.1:8b`, `gemma3:4b` | — | markedly weaker Arabic |

**Hardware note.** On a 6 GB VRAM card (e.g. a Quadro P3200), `qwen3:8b` does not fit entirely in VRAM; Ollama offloads the rest to system RAM, which is fine on a 64 GB machine but slower than a fully GPU-resident model. If replies feel sluggish, `qwen3:4b` (~2.5 GB) fits in VRAM and stays fast at the cost of quality. Practical floor: 8B Q4 needs ~6 GB RAM/VRAM and runs acceptably on CPU; 14B wants 12 GB+; 27B wants 24–32 GB.

## Model selection rules in the product

1. The app starts on the free default; no key required, no research required.
2. When a paid key is configured, the app offers the paid default as a one-click upgrade and shows the running cost of the session.
3. A local model is opt-in, with `qwen3:8b` pre-selected.
4. If the provider fails (401/403/429/model unavailable), the app says exactly what happened and offers the fallback model — it never silently degrades.
5. A model bake-off over a fixed prompt set is part of the MVP hardening (milestone M7) so these defaults stay evidence-based.

---
---

# Languages, tones and session behaviour

**Target languages (MVP):** Levantine colloquial Arabic (`ar-lev`), Spanish (`es`), Swedish (`sv`). `Auto` infers the language from the learner's first message. The interface language is English only.

**Tones (menu):** Conversation partner (default), Formal interview, OPI examiner, Debate partner, Storytelling partner. The tone changes Marasa's register, the kind of questions she asks, and how she elicits a sample of speech (the OPI examiner tone follows the ACTFL warm-up → level checks → probes → wind-down arc).

**Sessions are ephemeral by design.** Transcripts, observations and the OPI estimate live in memory only and are gone when Marasa closes; nothing is written to disk. To keep a session, download the recap PDF. A new session is a new agent with no memory of the last one — the only way to carry context forward is to feed a previous recap PDF back in as input, so Marasa knows what to focus on. Extending memory and session lifetime is deliberately deferred.

**One session at a time.** While a session is open, the start screen shows *"A session is still open"* with two choices: **Resume session** (pick up exactly where you left off, even after a page reload — the transcript is still in memory) or **Discard it**. Starting a new conversation while one is open asks before throwing the old one away, and continues into the new one automatically if you agree.

**No overrides in the MVP.** The learner cannot correct Marasa's level estimate or its vocabulary/grammar judgements. Marasa's recap is the record of the session.

# Project layout

```
marasa-ai/
├─ backend/            FastAPI app
│  ├─ pyproject.toml   dependencies (locked by uv.lock)
│  ├─ .venv/           created by `uv sync` (not committed)
│  ├─ app/
│  │  ├─ api.py        HTTP routes (sessions, turns/SSE, recap PDF)
│  │  ├─ session.py    in-memory session store (one active session)
│  │  ├─ providers/    mock · ollama · console (M1) · local OpenCode (M1.5)
│  │  ├─ tutor/        prompt, OPI rubric, note parser, languages, tones
│  │  └─ export/       HTML → PDF (Playwright) + recap template
│  └─ tests/
├─ frontend/           React + Vite + Tailwind
│  ├─ package-lock.json
│  └─ src/             Start · Session · Recap screens
├─ scripts/            setup · dev · test (PowerShell and bash)
├─ PLAN.md             implementation plan
└─ OPI-Familiarization-Guide-2020-1.pdf   (local only — see licensing note)
```

# Testing

```powershell
.\scripts\test.ps1      # pytest + vitest
```

Backend tests cover the note parser (including malformed model output), the OPI level ladder, the session lifecycle (a second session is refused until the first is discarded), and the streaming endpoint. Frontend tests cover the SSE parser. The default `mock` provider makes the whole suite deterministic and offline.

# Licensing note

The **ACTFL Oral Proficiency Interview Familiarization Guide 2020** (© 2020) and the **ACTFL Proficiency Guidelines 2012 – Speaking** are proprietary. ACTFL permits their use for non-profit, educational purposes only, reproduced in their entirety and with credit. Accordingly:

- the guide is **gitignored** and is not redistributed by this repository;
- `backend/app/tutor/rubric.py` contains **paraphrased** summaries with attribution, not verbatim text;
- every recap PDF labels the score as an estimate produced by an automated practice partner, not an official ACTFL OPI rating (official ratings can only be issued by ACTFL-certified testers).

Before publishing this repository publicly, keep the guide local and review the redistribution terms.
