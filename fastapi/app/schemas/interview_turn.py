from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class InterviewTurnIn(BaseModel):
    """Incoming message from frontend to interviewer."""

    # text transcript for this turn (used when frontend is doing transcription)
    answer: str = Field(..., min_length=1)


class InterviewTurnOut(BaseModel):
    """Outgoing message from interviewer to frontend."""

    question: str
    response: Optional[str] = None

    # Metadata to support non-repetition and difficulty tracking.
    mode: Literal["HR", "Technical"]
    questionId: Optional[str] = None
    turnIndex: int = 0
    responseScore: Optional[Dict[str, Any]] = None


class ConversationTurnStored(BaseModel):
    question: str
    answer: str
    timestamp: datetime
    mode: Literal["HR", "Technical"]
    questionId: Optional[str] = None

    # Voice layer extensions (optional in Mongo)
    transcript: Optional[str] = None
    audioDurationMs: Optional[int] = None
    fillerWordCount: Optional[int] = None
    wpm: Optional[float] = None
    avgPauseLengthS: Optional[float] = None
    verbalConfidence: Optional[int] = None


