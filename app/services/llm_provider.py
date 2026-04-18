"""
Multi-provider LLM integration for note analysis (OpenAI-compatible, Gemini).

Environment:
  LLM_PROVIDER          — groq | openai | gemini (default: groq)
  LLM_FALLBACK_ENABLED  — true/false (default: true): try other providers on failure

Keys (per provider):
  Groq:   GROQ_API_KEY, optional GROQ_MODEL
  OpenAI: OPENAI_API_KEY, optional OPENAI_MODEL
  Gemini: GEMINI_API_KEY or GOOGLE_API_KEY, optional GEMINI_MODEL

Gemini: get a key at https://aistudio.google.com/apikey — enable Generative Language API if prompted.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai import APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import BaseModel, Field, ValidationError

from app.exceptions import AnalysisError
from app.schemas.notes import AnalyzeResponse


class _LLMJsonOutput(BaseModel):
    """Shape of JSON returned by the model (before we add llm_provider)."""

    summary: str = Field(...)
    key_points: list[str] = Field(...)
    tone: str = Field(...)

SYSTEM_PROMPT = """You are a note analysis assistant. Given the user's note text, respond with ONLY a valid JSON object (no markdown, no commentary) with exactly these keys:
- "summary": a concise string summary of the note
- "key_points": an array of strings, each a distinct important point from the note
- "tone": a short string describing the emotional tone (e.g. positive, neutral, negative, urgent, reflective)

The JSON must be parseable by a standard JSON parser. Do not include trailing commas or comments."""

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Fallback order after the primary provider (each must have a configured key to be tried).
_FALLBACK_SEQUENCE = ("groq", "openai", "gemini")

ProviderFn = Callable[[str], dict[str, Any]]


def _json_from_llm_text(raw: str) -> dict[str, Any]:
    """Extract and parse JSON from model output, tolerating optional markdown fences."""
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise AnalysisError("LLM JSON must be an object.", status_code=502)
    return data


def _validate_llm_json(data: dict[str, Any]) -> dict[str, Any]:
    try:
        return _LLMJsonOutput.model_validate(data).model_dump()
    except ValidationError as e:
        raise AnalysisError(
            f"LLM output did not match the expected schema: {e}",
            status_code=502,
        ) from e


def _with_provider(llm_fields: dict[str, Any], provider_id: str) -> dict[str, Any]:
    """Build full API payload: LLM fields + llm_provider."""
    try:
        return AnalyzeResponse(
            **llm_fields,
            llm_provider=provider_id,
        ).model_dump()
    except ValidationError as e:
        raise AnalysisError(
            f"Analysis response validation failed: {e}",
            status_code=502,
        ) from e


def _openai_compatible_analyze(
    text: str,
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    provider_label: str,
) -> dict[str, Any]:
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    try:
        completion = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
    except AuthenticationError as e:
        raise AnalysisError(
            f"{provider_label} authentication failed. Check your API key.",
            401,
        ) from e
    except RateLimitError as e:
        raise AnalysisError(
            f"{provider_label} rate limit exceeded. Try again later.",
            429,
        ) from e
    except APITimeoutError as e:
        raise AnalysisError(f"{provider_label} request timed out.", 504) from e
    except APIError as e:
        raise AnalysisError(f"{provider_label} API error: {e}", 502) from e

    choices = completion.choices
    if not choices:
        raise AnalysisError(f"{provider_label} returned no completion choices.", 502)

    msg = choices[0].message
    content = msg.content if msg else None
    if not content or not content.strip():
        raise AnalysisError(f"{provider_label} returned an empty response.", 502)

    try:
        raw = _json_from_llm_text(content)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"LLM output was not valid JSON: {e}",
            status_code=502,
        ) from e

    return _validate_llm_json(raw)


def analyze_with_openai(text: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AnalysisError("OPENAI_API_KEY is not set.", 503)
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return _openai_compatible_analyze(
        text,
        api_key=api_key,
        base_url=None,
        model=model,
        provider_label="OpenAI",
    )


def analyze_with_groq(text: str) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise AnalysisError("GROQ_API_KEY is not set.", 503)
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    return _openai_compatible_analyze(
        text,
        api_key=api_key,
        base_url=GROQ_BASE_URL,
        model=model,
        provider_label="Groq",
    )


def analyze_with_gemini(text: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise AnalysisError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is not set. Get a key at https://aistudio.google.com/apikey",
            503,
        )

    model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=text,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
    except genai_errors.ClientError as e:
        code = getattr(e, "code", None)
        if code in (401, 403):
            raise AnalysisError(
                "Gemini authentication failed or API not enabled. Check GEMINI_API_KEY / GOOGLE_API_KEY.",
                401,
            ) from e
        if code == 429:
            raise AnalysisError("Gemini quota or rate limit exceeded. Try again later.", 429) from e
        raise AnalysisError(f"Gemini API error: {e}", 502) from e
    except genai_errors.ServerError as e:
        raise AnalysisError(f"Gemini API error: {e}", 502) from e
    except genai_errors.APIError as e:
        raise AnalysisError(f"Gemini API error: {e}", 502) from e

    raw_text = getattr(response, "text", None) or ""
    if not raw_text.strip():
        raise AnalysisError("Gemini returned an empty response.", 502)

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        try:
            data = _json_from_llm_text(raw_text)
        except json.JSONDecodeError as e:
            raise AnalysisError(
                f"Gemini output was not valid JSON: {e}",
                status_code=502,
            ) from e

    if not isinstance(data, dict):
        raise AnalysisError("Gemini JSON must be an object.", status_code=502)

    return _validate_llm_json(data)


_PROVIDERS: dict[str, ProviderFn] = {
    "openai": analyze_with_openai,
    "groq": analyze_with_groq,
    "gemini": analyze_with_gemini,
}


def _provider_available(name: str) -> bool:
    if name == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if name == "groq":
        return bool(os.getenv("GROQ_API_KEY"))
    if name == "gemini":
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return False


def _ordered_providers(primary: str) -> list[str]:
    primary = primary.strip().lower()
    if primary not in _PROVIDERS:
        raise AnalysisError(
            f"Unknown LLM_PROVIDER '{primary}'. Use: {', '.join(sorted(_PROVIDERS))}.",
            status_code=503,
        )
    rest = [p for p in _FALLBACK_SEQUENCE if p != primary]
    return [primary] + rest


def _fallback_enabled() -> bool:
    return os.getenv("LLM_FALLBACK_ENABLED", "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def analyze_text(text: str) -> dict[str, Any]:
    """
    Run note analysis with LLM_PROVIDER (default groq), optional multi-provider fallback.

    Returns a dict validated against AnalyzeResponse (summary, key_points, tone, llm_provider).
    """
    primary = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    candidates = _ordered_providers(primary)

    if not _fallback_enabled():
        if not _provider_available(primary):
            raise AnalysisError(
                f"Provider '{primary}' is not configured (missing API key).",
                503,
            )
        llm_only = _PROVIDERS[primary](text)
        return _with_provider(llm_only, primary)

    last_error: AnalysisError | None = None
    for name in candidates:
        if not _provider_available(name):
            continue
        try:
            llm_only = _PROVIDERS[name](text)
            return _with_provider(llm_only, name)
        except AnalysisError as e:
            last_error = e
            continue

    if last_error is not None:
        raise last_error

    raise AnalysisError(
        "No LLM provider is configured. Set keys for Groq, OpenAI, or Gemini (see module docstring).",
        503,
    )
