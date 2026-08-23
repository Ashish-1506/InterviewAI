from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CategorySubScores(BaseModel):
    communication: float = Field(..., ge=0, le=10)
    technical_depth: float = Field(..., ge=0, le=10)
    confidence: float = Field(..., ge=0, le=10)
    problem_solving: float = Field(..., ge=0, le=10)


class QuestionBreakdownItem(BaseModel):
    question: str
    mode: Literal["HR", "Technical"]
    question_id: Optional[str] = None
    turn_index: int

    answer_or_code: Optional[str] = None
    # Raw AI scoring outputs (compact)
    ai_feedback: Dict[str, Any] = Field(default_factory=dict)

    emotion_snapshot: Optional[Dict[str, Any]] = None
    speech_metrics: Optional[Dict[str, Any]] = None


class FinalReportPayload(BaseModel):
    session_id: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    overall_score_0_to_100: float
    category_scores: CategorySubScores
    weights_used: Dict[str, float] = Field(default_factory=dict)

    strengths: List[Dict[str, Any]] = Field(default_factory=list)
    weaknesses: List[Dict[str, Any]] = Field(default_factory=list)

    question_breakdown: List[QuestionBreakdownItem] = Field(default_factory=list)

