from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


EmotionCategory = Literal[
    "confident",
    "nervous",
    "neutral",
    "engaged",
    "confused",
]


class EmotionDetectIn(BaseModel):
    session_id: str = Field(..., min_length=1)

    # Base64-encoded JPEG frame (privacy: periodic frame sampling; no raw video storage)
    frame_jpeg_b64: str = Field(..., min_length=1)

    # The frontend can optionally associate a sample to the interview question/turn.
    # If absent, backend will attempt to place it into the latest known turn.
    turn_index: Optional[int] = None

    timestamp_ms: Optional[int] = None


class EmotionScoresOut(BaseModel):
    confident: float
    nervous: float
    neutral: float
    engaged: float
    confused: float


class EmotionDetectOut(BaseModel):
    session_id: str
    turn_index: Optional[int] = None
    timestamp_ms: Optional[int] = None

    scores: EmotionScoresOut


class EmotionTurnAggregate(BaseModel):
    turn_index: int
    sample_count: int = 0

    averages: EmotionScoresOut

    # Soft trends derived from sample aggregates (not diagnoses)
    trend: dict[str, float] = Field(default_factory=dict)


class EmotionSessionSummaryOut(BaseModel):
    overall_averages: EmotionScoresOut
    dominant: list[EmotionCategory] = Field(default_factory=list)
    notable_shifts: list[str] = Field(default_factory=list)


class EmotionReportOut(BaseModel):
    session_id: str
    aggregated_by_turn: list[EmotionTurnAggregate]
    session_summary: EmotionSessionSummaryOut

    # Optional chart-friendly series
    chart_series: dict[str, list[float]]

