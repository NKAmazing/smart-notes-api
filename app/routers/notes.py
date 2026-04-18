from fastapi import APIRouter, HTTPException

from app.schemas.notes import AnalyzeRequest, AnalyzeResponse
from app.services.notes_service import AnalysisError, analyze_note

router = APIRouter(prefix="/analyze", tags=["Notes"])


@router.post(
    "",
    response_model=AnalyzeResponse,
    summary="Analyze a note",
    description=(
        "Receives a plain-text note and returns a structured analysis including "
        "a summary, key points, and the detected tone of the text."
    ),
)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return analyze_note(request)
    except AnalysisError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
