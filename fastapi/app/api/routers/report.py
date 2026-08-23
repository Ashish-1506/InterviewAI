from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_auth
from app.core.config import get_settings
from app.schemas.report_page import FinalReportPayload, QuestionBreakdownItem
from app.services.mongo_store import MongoStore
from app.services.scoring_engine import ScoringEngine
from app.services.weakness_reporter import WeaknessReporter


router = APIRouter(prefix="/api")


@router.get("/scoring/report", response_model=FinalReportPayload)
async def get_scoring_report(session_id: str, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()
    mongo = MongoStore(settings=settings)

    scoring = ScoringEngine(settings=settings, mongo=mongo)
    final = await scoring.score_session(session_id=session_id)

    reporter = WeaknessReporter(settings=settings, mongo=mongo)
    ww = await reporter.generate_weakness_strength_report(session_id=session_id)

    question_breakdown: List[QuestionBreakdownItem] = []
    for q in final.question_scores:
        answer_or_code = q.answer_text
        if q.code_submission and isinstance(q.code_submission, dict):
            # For Technical mode, prefer code submission string-ish summary.
            code = q.code_submission.get("code") if isinstance(q.code_submission, dict) else None
            if code:
                answer_or_code = code
        question_breakdown.append(
            QuestionBreakdownItem(
                question=q.question,
                mode=q.mode,
                question_id=q.question_id,
                turn_index=q.turn_index,
                answer_or_code=answer_or_code,
                ai_feedback={
                    "relevance": q.relevance,
                    "depth": q.depth,
                    "structure": q.structure,
                    "overall": q.overall,
                    "justification": q.justification,
                },
                emotion_snapshot=q.emotion_snapshot,
                speech_metrics=q.speech_metrics,
            )
        )

    return FinalReportPayload(
        session_id=str(session_id),
        overall_score_0_to_100=final.overall_score_0_to_100,
        category_scores=final.category_scores,
        weights_used=final.weights_used,
        strengths=ww.strengths,
        weaknesses=ww.weaknesses,
        question_breakdown=question_breakdown,
    )

