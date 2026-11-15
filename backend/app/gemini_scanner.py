"""Gemini multimodal OCR and structured extraction for worker job offers."""

import json
from datetime import date
from decimal import Decimal
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings

MAX_INPUT_TEXT_CHARS = 20_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

OFFER_JSON_SCHEMA = {
        "type": "object",
    "properties": {
        "contractor_name": {"type": ["string", "null"]},
        "occupation": {"type": ["string", "null"]},
        "wage_amount": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
        "wage_period": {"type": ["string", "null"]},
        "working_hours": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "payment_terms": {"type": ["string", "null"]},
        "start_date": {"type": ["string", "null"]},
        "field_evidence": {
            "type": "object",
            "properties": {
                field: {"type": ["string", "null"]}
                for field in (
                    "contractor_name", "occupation", "wage_amount", "currency", "wage_period",
                    "working_hours", "location", "payment_terms", "start_date",
                )
            },
            "required": [
                "contractor_name", "occupation", "wage_amount", "currency", "wage_period",
                "working_hours", "location", "payment_terms", "start_date",
            ],
            "additionalProperties": False,
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "contractor_name", "occupation", "wage_amount", "currency", "wage_period",
        "working_hours", "location", "payment_terms", "start_date", "field_evidence", "notes",
    ],
    "additionalProperties": False,
}


class ExtractedOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractor_name: str | None = None
    occupation: str | None = None
    wage_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = None
    wage_period: str | None = None
    working_hours: str | None = None
    location: str | None = None
    payment_terms: str | None = None
    start_date: date | None = None
    field_evidence: dict[str, str | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


def _text_evidence_exists(excerpt: str | None, source_text: str) -> bool:
    if not excerpt:
        return False
    normalize = lambda value: " ".join(value.casefold().split())
    return normalize(excerpt) in normalize(source_text)


def validate_extraction(payload: dict, source_text: str | None) -> ExtractedOffer:
    try:
        result = ExtractedOffer.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="Gemini returned an invalid extraction response.") from exc

    notes = list(result.notes)
    fields = (
        "contractor_name", "occupation", "wage_amount", "currency", "wage_period",
        "working_hours", "location", "payment_terms", "start_date",
    )
    for field in fields:
        value = getattr(result, field)
        evidence = result.field_evidence.get(field)
        if value is None:
            continue
        if not evidence:
            setattr(result, field, None)
            notes.append(f"{field}: omitted because Gemini did not provide a source excerpt.")
        elif source_text and not _text_evidence_exists(evidence, source_text):
            setattr(result, field, None)
            notes.append(f"{field}: omitted because the cited excerpt did not match the submitted text.")
    result.notes = list(dict.fromkeys(notes))
    return result


async def extract_offer(source_text: str | None, image_bytes: bytes | None, mime_type: str | None) -> ExtractedOffer:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini offer scanning is not configured on this server.")

    instruction = (
        "Read the submitted job offer using OCR for any image. Extract only details explicitly present. "
        "Do not infer, calculate, translate, fill from common practice, or guess missing values. "
        "Use null for every field that is absent, unclear, or ambiguous. Return short exact source excerpts "
        "for each non-null value in field_evidence. For an image, the excerpt must reproduce visible text. "
        "Do not treat warnings, allegations, or claims about a contractor as verified facts. "
        "Dates must be ISO YYYY-MM-DD only when the full date is explicit. Wage amount must be numeric "
        "without currency symbols; preserve the currency separately only when explicitly shown."
    )
    parts: list[dict] = [{"text": instruction}]
    if source_text:
        parts.append({"text": f"Offer text supplied by worker:\n{source_text}"})
    if image_bytes is not None and mime_type is not None:
        import base64

        parts.append({"inlineData": {"mimeType": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    request = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0,
            "responseFormat": {
                "text": {"mimeType": "application/json", "schema": OFFER_JSON_SCHEMA}
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers={"x-goog-api-key": settings.gemini_api_key}, json=request)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Offer extraction timed out. Try a clearer or smaller image.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Offer extraction service could not be reached.") from exc

    if response.status_code == 429:
        raise HTTPException(status_code=503, detail="Offer extraction is busy. Try again shortly.")
    if response.is_error:
        # Provider response details may include request metadata; never echo it.
        raise HTTPException(status_code=502, detail="Gemini could not process this offer.")
    try:
        body = response.json()
        response_text = "".join(part.get("text", "") for part in body["candidates"][0]["content"]["parts"])
        extracted = json.loads(response_text)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Gemini returned an unreadable extraction response.") from exc
    # When an image is present the quoted evidence may be OCR text that is not
    # in the optional accompanying typed text; in that case still require a
    # citation, but leave image-grounding to the worker's review step.
    return validate_extraction(extracted, source_text if image_bytes is None else None)
