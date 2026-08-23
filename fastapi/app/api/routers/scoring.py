from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_auth
from app.core.config import get_settings
from app.schemas.scoring import (
    CategoryScores,
    FinalScoreResponse,
    QuestionScore,
    StrengthEvidence,
    WeaknessEvidence,
    WeaknessStrengthReport,
)
from app.services.mongo_store import MongoStore
from app.services.scoring_engine import ScoringEngine
from app.services.weakness_reporter import WeaknessReporter


router = APIRouter(prefix="/api")


@router.get("/scoring/final", response_model=FinalScoreResponse)
async def get_final_scoring(session_id: str, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()
    mongo = MongoStore(settings=settings)

    engine = ScoringEngine(settings=settings, mongo=mongo)
    return await engine.score_session(session_id=session_id)


@router.get("/scoring/weaknesses", response_model=WeaknessStrengthReport)
async def get_weakness_strengths(session_id: str, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()
    mongo = MongoStore(settings=settings)

    reporter = WeaknessReporter(settings=settings, mongo=mongo)
    return await reporter.generate_weakness_strength_report(session_id=session_id)

