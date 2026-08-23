from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_auth
from PIL import Image

from app.core.config import get_settings
from app.schemas.emotion import EmotionDetectIn, EmotionDetectOut, EmotionReportOut, EmotionScoresOut
from app.services.mongo_store import MongoStore


router = APIRouter(prefix="/api")


# -------- Emotion model (DeepFace, CPU) --------
# Privacy requirements: only periodic frame analysis; no raw video storage.
# This router decodes frames in-memory and immediately discards them.


try:
    from deepface import DeepFace  # type: ignore

    _DEEPFACE_AVAILABLE = True
except Exception:
    _DEEPFACE_AVAILABLE = False


_EMOTION_MAP = {
    # DeepFace output emotions: anger, disgust, fear, happiness, sadness, surprise, neutral
    # We map into the requested five-category space.
    # These mappings are intentionally soft and should be interpreted as trends only.
    "confident": ("happiness", 1.0),
    "engaged": ("happiness", 0.6),
    "neutral": ("neutral", 1.0),
    "nervous": ("fear", 1.0),
    "confused": ("surprise", 1.0),
}


def _normalize_scores(raw: dict[str, float]) -> dict[str, float]:
    # DeepFace returns scores that sum to 1 for its emotion categories.
    # We'll derive requested category scores as weighted sums from DeepFace outputs.
    def get(k: str) -> float:
        v = raw.get(k)
        return float(v) if v is not None else 0.0

    happiness = get("happiness")
    neutral = get("neutral")
    fear = get("fear")
    surprise = get("surprise")

    # Keep neutral as neutral.
    nervous = fear
    confused = surprise

    # engaged/confident both draw from happiness but split.
    confident = happiness
    engaged = min(1.0, happiness * 0.9)

    # If happiness is zero, engaged/confident are zero.
    neutral_score = neutral

    # Ensure no negatives and renormalize softly.
    scores = {
        "confident": max(0.0, confident),
        "nervous": max(0.0, nervous),
        "neutral": max(0.0, neutral_score),
        "engaged": max(0.0, engaged),
        "confused": max(0.0, confused),
    }

    s = sum(scores.values())
    if s > 0:
        scores = {k: float(v / s) for k, v in scores.items()}

    return scores


@dataclass
class EmotionEngine:
    mongo: MongoStore

    def __post_init__(self) -> None:
        if not _DEEPFACE_AVAILABLE:
            raise RuntimeError(
                "DeepFace is not available. Install it or configure a different emotion model."
            )

    async def detect_and_aggregate(self, req: EmotionDetectIn) -> EmotionDetectOut:
        settings = get_settings()

        # Decode JPEG
        try:
            jpeg_bytes = base64.b64decode(req.frame_jpeg_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 frame_jpeg_b64: {e}")

        # Load image in-memory
        try:
            img = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image payload: {e}")

        # Predict with DeepFace (emotion)
        try:
            # enforce_detection=False prevents hard failures if face detection fails.
            # We'll return neutral-biased results when uncertain.
            result = DeepFace.analyze(
                img,
                actions=["emotion"],
                enforce_detection=False,
            )

            # DeepFace may return list or dict depending on input.
            if isinstance(result, list):
                result = result[0] if result else {}

            raw_emotions = result.get("emotion") or {}
            scores_raw = _normalize_scores(raw_emotions)
        except Exception:
            # Best-effort fallback: all neutral
            scores_raw = {
                "confident": 0.0,
                "nervous": 0.0,
                "neutral": 1.0,
                "engaged": 0.0,
                "confused": 0.0,
            }

        scores_out = EmotionScoresOut(**scores_raw)

        # Persist aggregated emotion only.
        # We'll store under session document under `emotionAnalysis`.
        await self.mongo.append_emotion_sample(
            session_id=req.session_id,
            turn_index=req.turn_index,
            scores=scores_raw,
            timestamp_ms=req.timestamp_ms,
        )

        # Return detected scores for immediate UI indicator.
        return EmotionDetectOut(
            session_id=req.session_id,
            turn_index=req.turn_index,
            timestamp_ms=req.timestamp_ms,
            scores=scores_out,
        )


@router.post("/emotion/detect", response_model=EmotionDetectOut)
async def emotion_detect(req: EmotionDetectIn, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()
    mongo = MongoStore(settings=settings)
    engine = EmotionEngine(mongo=mongo)
    return await engine.detect_and_aggregate(req)


@router.get("/emotion/report", response_model=EmotionReportOut)
async def emotion_report(session_id: str, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()
    mongo = MongoStore(settings=settings)
    return await mongo.get_emotion_report(session_id=session_id)

