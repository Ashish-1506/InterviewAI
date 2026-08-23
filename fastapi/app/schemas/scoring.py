from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CategoryScores(BaseModel):
    communication: float = Field(..., ge=0, le=10)
    technical_depth: float = Field(..., ge=0, le=10)
    confidence: float = Field(..., ge=0, le=10)
    problem_solving: float = Field(..., ge=0, le=10)


class QuestionScore(BaseModel):
    question: str
    mode: Literal["HR", "Technical"]
    question_id: Optional[str] = None
    turn_index: int = 0

    # Candidate signals
    answer_text: Optional[str] = None
    code_submission: Optional[Dict[str, Any]] = None
    speech_metrics: Optional[Dict[str, Any]] = None
    emotion_snapshot: Optional[Dict[str, Any]] = None
    code_eval: Optional[Dict[str, Any]] = None

    # LLM judgement (0-10)
    relevance: float = Field(..., ge=0, le=10)
    depth: float = Field(..., ge=0, le=10)
    structure: float = Field(..., ge=0, le=10)
    overall: float = Field(..., ge=0, le=10)

    justification: str


class FinalScoreResponse(BaseModel):
    session_id: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Category subscores (0-10 each)
    category_scores: CategoryScores

    # Weighted overall score mapped to 0-100
    overall_score_0_to_100: float = Field(..., ge=0, le=100)

    weights_used: Dict[str, float]

    # Per-question breakdown
    question_scores: List[QuestionScore]


class WeaknessEvidence(BaseModel):
    question: str
    mode: Literal["HR", "Technical"]
    turn_index: Optional[int] = None
    moment: Optional[str] = None
    evidence: str


class StrengthEvidence(BaseModel):
    question: str
    mode: Literal["HR", "Technical"]
    turn_index: Optional[int] = None
    moment: Optional[str] = None
    evidence: str


class WeaknessStrengthReport(BaseModel):
    session_id: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    strengths: List[StrengthEvidence] = Field(default_factory=list)
    weaknesses: List[WeaknessEvidence] = Field(default_factory=list)

