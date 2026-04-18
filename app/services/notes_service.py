from pydantic import ValidationError

from app.exceptions import AnalysisError
from app.schemas.notes import AnalyzeRequest, AnalyzeResponse
from app.services.llm_provider import analyze_text

__all__ = ["AnalysisError", "analyze_note"]


def analyze_note(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyzes a note using the configured LLM provider(s).

    Raises AnalysisError on configuration issues, API failures, invalid JSON, or schema mismatch.
    """
    try:
        data = analyze_text(request.text)
        return AnalyzeResponse.model_validate(data)
    except ValidationError as e:
        raise AnalysisError(
            f"Analysis response validation failed: {e}",
            status_code=502,
        ) from e
