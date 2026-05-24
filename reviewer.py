"""Core review logic. Calls Google Gemini with structured JSON output."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from google import genai
from google.genai import types

MODEL = os.environ.get("REVIEWER_MODEL", "gemini-2.5-flash")
PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "language": {"type": "string"},
        "summary": {"type": "string"},
        "scores": {
            "type": "object",
            "properties": {
                "readability": {"type": "integer"},
                "structure": {"type": "integer"},
                "maintainability": {"type": "integer"},
            },
            "required": ["readability", "structure", "maintainability"],
        },
        "improvements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "category": {"type": "string"},
                    "issue": {"type": "string"},
                    "location": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["priority", "category", "issue", "location", "suggestion"],
            },
        },
        "positive": {"type": "string"},
        "ready_for_human_review": {"type": "boolean"},
        "blockers": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "language",
        "summary",
        "scores",
        "improvements",
        "positive",
        "ready_for_human_review",
        "blockers",
    ],
}


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def review_code(code: str, language_hint: str | None = None) -> dict:
    """Returns the structured JSON review as a dict.

    Uses Gemini's `response_schema` to guarantee well-formed JSON — the model is constrained
    to the schema at decode time rather than asked nicely in the prompt. This is the
    production-grade pattern: fewer retries, no parse-error fallbacks needed.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY not set"}

    client = genai.Client(api_key=api_key)
    system_prompt = load_system_prompt()
    user_message = code if not language_hint else f"Language hint: {language_hint}\n\n```\n{code}\n```"

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.2,
        max_output_tokens=4096,
    )

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=user_message, config=config
            )
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            return {
                "error": "model returned non-JSON output",
                "raw": getattr(response, "text", ""),
                "exception": str(exc),
            }
        except Exception as exc:
            last_exc = exc
            # Retry on 503 (overloaded) and 429 (rate limit) — common transient errors.
            if "503" in str(exc) or "429" in str(exc) or "UNAVAILABLE" in str(exc):
                time.sleep(2 ** attempt)
                continue
            return {"error": f"API call failed: {exc}"}
    return {"error": f"API call failed after 3 retries: {last_exc}"}
