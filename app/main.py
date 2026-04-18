from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from app.routers import notes

# Carga variables desde .env (raíz del proyecto y/o app/.env)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / "app" / ".env")
load_dotenv(_project_root / ".env")

app = FastAPI(
    title="Smart Notes API",
    description=(
        "An intelligent API that analyzes plain-text notes and returns structured insights "
        "such as summaries, key points, and tone detection. "
        "AI integration will be added in a future iteration."
    ),
    version="0.1.0",
    contact={
        "name": "Smart Notes Team",
    },
    license_info={
        "name": "MIT",
    },
)

app.include_router(notes.router)


@app.get("/", tags=["Health"], summary="Health check")
def root() -> dict:
    return {"status": "ok", "message": "Smart Notes API is running."}
