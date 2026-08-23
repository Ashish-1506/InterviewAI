from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CodeEvaluateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question_id: str = Field(..., min_length=1)
    language: Literal["python", "javascript", "java"] = "python"
    code: str = Field(..., min_length=1)
    # The client should send the current turn index and question text for linking.
    turnIndex: Optional[int] = None


class TestCaseResult(BaseModel):
    input: Any
    expected: Any
    actual: Any
    passed: bool
    error: Optional[str] = None


class CodeEvaluationOut(BaseModel):
    question_id: str
    passed: bool

    startedAt: Optional[datetime] = None
    finishedAt: Optional[datetime] = None

    testResults: list[TestCaseResult] = []
    summary: str

    # Raw execution output (best-effort)
    stdout: Optional[str] = None
    stderr: Optional[str] = None

    # AI-generated review
    aiReview: Optional[str] = None


