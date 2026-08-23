from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class RecordingControlIn(BaseModel):
    """Frontend -> backend recording control."""

    action: Literal["start", "stop"]


class AudioChunkIn(BaseModel):
    """Frontend -> backend audio chunk for transcription."""

    # base64-encoded audio bytes (webm/ogg/wav/whatever the browser records)
    audio_b64: str = Field(..., min_length=1)

    # Browser side: in ms, so STT/confidence can reason about pauses.
    chunk_start_ms: Optional[int] = None
    chunk_end_ms: Optional[int] = None


class InterviewVoiceTurnIn(BaseModel):
    """Frontend -> backend WS message. One of: recording control or chunk."""

    # If provided, WS will treat message as control.
    control: Optional[RecordingControlIn] = None

    # If provided, WS will treat message as chunk.
    audio: Optional[AudioChunkIn] = None


class VoiceTranscriptOut(BaseModel):
    transcript: str
    audio_duration_ms: int


class SpeechStatsOut(BaseModel):
    filler_word_count: int
    wpm: float
    avg_pause_length_s: float
    verbal_confidence: int


class InterviewTurnOutVoice(BaseModel):
    """Interviewer -> frontend WS message when sending the next question with audio + stats."""

    question: str
    response: Optional[str] = None

    mode: Literal["HR", "Technical"]
    questionId: Optional[str] = None
    turnIndex: int = 0

    # TTS
    questionAudioB64: Optional[str] = None
    questionAudioMimeType: Optional[str] = None

    # Candidate speech analysis
    transcript: Optional[str] = None
    audioDurationMs: Optional[int] = None
    fillerWordCount: Optional[int] = None
    wpm: Optional[float] = None
    avgPauseLengthS: Optional[float] = None
    verbalConfidence: Optional[int] = None
    responseScore: Optional[Dict[str, Any]] = None

    # Raw debugging fields
    receivedAt: Optional[datetime] = None

