# Smart Notes API

A FastAPI backend that analyzes plain-text notes and returns structured insights: summaries, key points, and tone detection.

> AI integration is coming in the next iteration. For now the `/analyze` endpoint returns mock data.

---

## Project Structure

```
smart-notes-api/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── routers/
│   │   └── notes.py         # POST /analyze endpoint
│   ├── schemas/
│   │   └── notes.py         # Pydantic request & response models
│   └── services/
│       └── notes_service.py # Business logic (mock for now)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the development server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

---

## API Endpoints

### `GET /`
Health check.

**Response:**
```json
{ "status": "ok", "message": "Smart Notes API is running." }
```

---

### `POST /analyze`
Analyzes a note and returns structured insights.

**Request body:**
```json
{
  "text": "Today I had a productive meeting with the team about Q2 goals."
}
```

**Response:**
```json
{
  "summary": "This note contains approximately 12 word(s) and covers a topic that will be summarized once AI integration is enabled.",
  "key_points": [
    "Key point extraction will be powered by an AI model in the next step.",
    "Input received with 12 word(s).",
    "Mock response — replace this service with an AI call to get real insights."
  ],
  "tone": "informative"
}
```

---

## Interactive Documentation

FastAPI generates automatic docs out of the box:

| Interface | URL |
|-----------|-----|
| Swagger UI | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| ReDoc | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

---

## Next Steps

- Integrate an AI model (e.g. OpenAI GPT) in `services/notes_service.py`
- Add authentication (API keys or OAuth2)
- Connect a database to persist notes
