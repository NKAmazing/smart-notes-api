from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="The note text to be analyzed.",
        examples=["Today I had a productive meeting with the team about Q2 goals."],
    )


class AnalyzeResponse(BaseModel):
    summary: str = Field(..., description="A concise summary of the note.")
    key_points: list[str] = Field(
        ..., description="A list of the most relevant key points extracted from the note."
    )
    tone: str = Field(
        ..., description="The detected emotional tone of the note (e.g. positive, neutral, negative)."
    )
    llm_provider: str = Field(
        ...,
        description='Backend that produced this analysis (e.g. "groq", "openai", "gemini").',
        examples=["groq"],
    )
