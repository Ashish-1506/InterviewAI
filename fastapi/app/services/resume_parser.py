from __future__ import annotations

import io
import json
import os
from urllib.parse import urlparse, urlunparse

import httpx
import pdfplumber
from docx import Document

from app.core.config import Settings
from app.schemas.resume import ParsedResumeResponse


def _download_file(file_url: str, settings: Settings) -> tuple[bytes, str]:
    candidates = [file_url]
    parsed_url = urlparse(file_url)

    if parsed_url.hostname in {"localhost", "127.0.0.1"}:
        internal_base = urlparse(settings.backend_internal_base_url)
        if internal_base.scheme and internal_base.netloc:
            candidates.append(
                urlunparse(
                    (
                        internal_base.scheme,
                        internal_base.netloc,
                        parsed_url.path,
                        parsed_url.params,
                        parsed_url.query,
                        parsed_url.fragment,
                    )
                )
            )

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            response = httpx.get(candidate, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            parsed_candidate = urlparse(candidate)
            filename = os.path.basename(parsed_candidate.path)
            return response.content, filename.lower()
        except Exception as error:  # pragma: no cover - exercised via fallback logic
            last_error = error

    if last_error is not None:
        raise last_error
    raise RuntimeError("Could not download resume file")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text() or ""
            if extracted:
                text_parts.append(extracted)

    return "\n".join(text_parts).strip()


def _extract_text_from_docx(file_bytes: bytes) -> str:
    document = Document(io.BytesIO(file_bytes))
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text).strip()


def _strict_json_schema(schema: dict) -> dict:
    """Make a Pydantic schema compatible with OpenAI strict JSON outputs."""
    if isinstance(schema, dict):
        # OpenAI's strict schema subset does not accept JSON Schema defaults.
        schema.pop("default", None)
        if schema.get("type") == "object":
            properties = schema.get("properties", {})
            schema["required"] = list(properties.keys())
            schema["additionalProperties"] = False
        for value in schema.values():
            if isinstance(value, (dict, list)):
                _strict_json_schema(value)
    elif isinstance(schema, list):
        for value in schema:
            if isinstance(value, (dict, list)):
                _strict_json_schema(value)
    return schema


def _call_llm(settings: Settings, resume_text: str) -> ParsedResumeResponse:
    provider = (settings.llm_provider or "gemini").lower()

    if provider != "gemini":
        return ParsedResumeResponse()

    if not settings.gemini_api_key:
        return ParsedResumeResponse()

    try:
        import google.generativeai as genai
    except ImportError:
        return ParsedResumeResponse()

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(model_name=settings.gemini_model)
        prompt = (
            "You are a resume parser. Return only valid JSON that matches the schema. "
            "Do not add commentary.\n\n"
            f"Schema:\n{json.dumps(ParsedResumeResponse.model_json_schema(), indent=2)}\n\n"
            f"Resume text:\n{resume_text}"
        )
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        content = getattr(response, "text", "") or "{}"
        return ParsedResumeResponse.model_validate_json(content)
    except Exception:
        return ParsedResumeResponse()


def parse_resume_from_url(file_url: str, settings: Settings) -> ParsedResumeResponse:
    file_bytes, filename = _download_file(file_url, settings)

    try:
        if filename.endswith(".pdf"):
            resume_text = _extract_text_from_pdf(file_bytes)
        elif filename.endswith(".docx"):
            resume_text = _extract_text_from_docx(file_bytes)
        else:
            raise ValueError("Only PDF and DOCX resume files are supported")
    except Exception as error:
        raise ValueError("Could not read the uploaded resume. The file may be corrupted or unsupported.") from error

    if not resume_text:
        raise ValueError("Could not extract text from the uploaded resume")

    if not settings.gemini_api_key:
        return ParsedResumeResponse()

    return _call_llm(settings, resume_text)
