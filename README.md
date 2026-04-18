# Smart Notes API

A **FastAPI** REST API that analyzes free-form note text and returns structured insights: **summary**, **key points**, **tone**, and which **LLM provider** handled the request.

Models are integrated in a **pluggable** way (Groq, OpenAI, Gemini) through a single business flow and **Pydantic** validation.

---

## Tech stack

| Component | Role |
|-----------|------|
| **Python 3.10+** (recommended; 3.9 may work with dependency warnings) | Language |
| **FastAPI** | HTTP framework, request/response validation, OpenAPI/Swagger |
| **Uvicorn** | ASGI server |
| **Pydantic v2** | `AnalyzeRequest` / `AnalyzeResponse` schemas |
| **python-dotenv** | Load variables from `.env` on startup |
| **openai** (official SDK) | **OpenAI** client and **OpenAI API–compatible** providers (e.g. **Groq** via `base_url`) |
| **google-genai** | **Google Gemini** client (developer API) |

---

## Project layout

```
smart-notes-api/
├── app/
│   ├── main.py                 # FastAPI app, .env loading
│   ├── exceptions.py           # AnalysisError (business errors → HTTP)
│   ├── routers/
│   │   └── notes.py            # POST /analyze
│   ├── schemas/
│   │   └── notes.py            # Pydantic request/response models
│   └── services/
│       ├── notes_service.py    # Wires analyze_note → analyze_text
│       └── llm_provider.py     # LLM providers, prompt, fallback
├── requirements.txt
├── LICENSE.md
└── README.md
```

---

## Quick setup

### 1. Virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 2. Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment variables

Copy `app/.env.example` to `app/.env` (or use a `.env` at the repo root) and fill in the keys you plan to use.

On startup, `app/main.py` loads, in order:

1. `app/.env`
2. `.env` at the project root

Variables not set in the shell are read from these files.

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Base URL: `http://127.0.0.1:8000`

---

## LLM providers and variables

Core behavior lives in `app/services/llm_provider.py`.

### Provider selection

| Variable | Values | Default |
|----------|--------|---------|
| `LLM_PROVIDER` | `groq`, `openai`, `gemini` | `groq` |
| `LLM_FALLBACK_ENABLED` | `true` / `false` (and equivalents `1`, `yes`, `on`) | `true` |

- **`LLM_PROVIDER`** sets which backend is tried **first**.
- If **`LLM_FALLBACK_ENABLED=true`**, after a failure (API error, quota, etc.) **other providers** are tried in a fixed order: **groq → openai → gemini**, but **only if an API key exists** for that provider. The **`llm_provider`** field in the response shows which one succeeded (useful when fallback ran).

### Keys and models per provider

| Provider | Variables | Default model (if not overridden) |
|----------|-----------|-----------------------------------|
| **Groq** | `GROQ_API_KEY`, optional `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| **OpenAI** | `OPENAI_API_KEY`, optional `OPENAI_MODEL` | `gpt-4o-mini` |
| **Gemini** | `GEMINI_API_KEY` or `GOOGLE_API_KEY`, optional `GEMINI_MODEL` | `gemini-2.0-flash` |

- **Groq**: key at [console.groq.com/keys](https://console.groq.com/keys). The client uses the OpenAI-compatible API with a fixed `base_url`: `https://api.groq.com/openai/v1` (you do not need to set it in `.env`).
- **OpenAI**: key at [platform.openai.com](https://platform.openai.com).
- **Gemini**: key at [Google AI Studio](https://aistudio.google.com/apikey); SDK: `google-genai`.

If no provider has a configured key, the API returns an error indicating missing configuration.

---

## How the LLM client works (technical overview)

1. **`analyze_text(text)`** (`llm_provider.py`) picks a provider from `LLM_PROVIDER` and applies optional fallback.
2. **OpenAI and Groq** share the same path: the official **`OpenAI`** SDK client; Groq only differs by `api_key` and `base_url`.
3. **Gemini** uses the **`google.genai`** client (`genai.Client`), `generate_content` with `response_mime_type="application/json"` and `system_instruction` using the same system text as the others.
4. The model is asked for **JSON-only** output with fixed fields (see prompt below). Where supported, **`response_format: { "type": "json_object" }`** is used (OpenAI-compatible).
5. JSON is parsed, validated against an internal `_LLMJsonOutput` model (`summary`, `key_points`, `tone`), then **`AnalyzeResponse`** is built by adding **`llm_provider`** with the id of the backend that responded.

Provider errors are wrapped in **`AnalysisError`** (`app/exceptions.py`) with `status_code` and `message`; the router maps them to **`HTTPException`** for HTTP clients.

---

## System prompt (provider)

The prompt is defined as **`SYSTEM_PROMPT`** in `llm_provider.py`. It asks for a **single JSON object** with no markdown, containing:

- `summary` (string)
- `key_points` (array of strings)
- `tone` (string)

To change analysis behavior, edit that block (and if you change the JSON shape, update the Pydantic schemas accordingly).

---

## Schemas (Pydantic)

Defined in `app/schemas/notes.py` (used in Swagger/ReDoc and validation):

| Model | Role |
|-------|------|
| **`AnalyzeRequest`** | Input: `text` (string, minimum 1 character). |
| **`AnalyzeResponse`** | Output: `summary`, `key_points`, `tone`, **`llm_provider`** (backend id: e.g. `groq`, `openai`, `gemini`). |

The router is unchanged: it still returns `AnalyzeResponse` on `POST /analyze`.

---

## HTTP API

### `GET /`

Health check.

**Example response:**

```json
{
  "status": "ok",
  "message": "Smart Notes API is running."
}
```

### `POST /analyze`

**Body:**

```json
{
  "text": "Today's team meeting was productive; we set priorities for the quarter."
}
```

**Example response (current shape):**

```json
{
  "summary": "…",
  "key_points": ["…", "…"],
  "tone": "neutral",
  "llm_provider": "groq"
}
```

Common errors: `401` / `429` / `502` / `503` / `504` depending on authentication, limits, provider failures, or missing configuration. The body usually includes `detail` with a readable message.

---

## Interactive docs (OpenAPI)

| UI | URL |
|----|-----|
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| ReDoc | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

---

## Billing and limits (realistic expectations)

No provider guarantees unlimited free usage forever; policies change. In practice:

- **Groq**, **Google AI (Gemini)**, and **OpenAI** often offer **free or trial tiers** with **limits** (per minute, per day, per project).
- Messages like **rate limit** or **quota exceeded** usually mean you hit the free tier cap, need to wait, or the project requires **billing** to raise quotas (depends on provider and account).
- For **learning and integration**, paying is not required; for **real traffic or production**, check each console: **Billing**, **Quotas**, and **Usage**.

This repository does not handle payments—it only calls APIs with the keys you configure.

---

## License

The code is released under the **MIT License**. See **[LICENSE.md](./LICENSE.md)**.

---

## Possible next steps

- Authentication (your own API key, JWT, etc.)
- Persist notes in a database
- Automated tests (pytest) with mocked LLM responses
- Deployment (Docker, Railway, Fly.io, etc.)
