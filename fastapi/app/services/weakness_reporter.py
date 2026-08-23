from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import Settings
from app.schemas.scoring import (
    FinalScoreResponse,
    StrengthEvidence,
    WeaknessEvidence,
    WeaknessStrengthReport,
)
from app.services.llm_provider import LLMProvider
from app.services.mongo_store import MongoStore
from app.services.scoring_engine import ScoringEngine


@dataclass
class WeaknessReporter:
    settings: Settings
    mongo: MongoStore

    def __post_init__(self) -> None:
        self._llm = LLMProvider(settings=self.settings).build_model()

    def _build_prompt(self, *, final: FinalScoreResponse) -> str:
        # Provide compact evidence-rich context.
        qs = [
            {
                "question": q.question,
                "mode": q.mode,
                "turn_index": q.turn_index,
                "answer": q.answer_text,
                "speech_metrics": q.speech_metrics,
                "emotion_snapshot": q.emotion_snapshot,
                "code_eval": q.code_eval,
                "judgement": {
                    "relevance": q.relevance,
                    "depth": q.depth,
                    "structure": q.structure,
                    "overall": q.overall,
                    "justification": q.justification,
                },
            }
            for q in final.question_scores
        ]

        return (
            "You are an expert interview coach. "
            "Using the provided scoring outputs, produce evidence-backed weaknesses and strengths.\n\n"
            "Requirements:\n"
            "- Output MUST be valid JSON only with keys: strengths, weaknesses.\n"
            "- strengths: array of 2-3 items, each with keys: question, mode, turn_index, moment, evidence.\n"
            "- weaknesses: array of 3-5 items, each with keys: question, mode, turn_index, moment, evidence.\n"
            "- Avoid generic feedback; every item must cite a question and a concrete moment/evidence from the candidate signals or LLM justification.\n"
            "- Do not mention medical/diagnosis terms.\n\n"
            f"Final category scores: {final.category_scores.model_dump()}\n"
            f"Overall score (0-100): {final.overall_score_0_to_100}\n\n"
            f"Per-question judgements: {json.dumps(qs)}\n\n"
            "Return JSON only." 
        )

    async def generate_weakness_strength_report(self, session_id: str) -> Any:
        # Reuse scoring engine so weaknesses are consistent.
        scoring = ScoringEngine(settings=self.settings, mongo=self.mongo)
        final = await scoring.score_session(session_id=session_id)

        prompt = self._build_prompt(final=final)
        raw = await self._llm.ainvoke(prompt)
        content = getattr(raw, "content", None) or str(raw)

        try:
            data = json.loads(content)
        except Exception:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(content[start : end + 1])
            else:
                raise

        strengths = []
        for s in (data.get("strengths") or []):
            strengths.append(
                StrengthEvidence(
                    question=s.get("question") or "",
                    mode=s.get("mode") or "HR",
                    turn_index=s.get("turn_index"),
                    moment=s.get("moment"),
                    evidence=s.get("evidence") or "",
                )
            )

        weaknesses = []
        for w in (data.get("weaknesses") or []):
            weaknesses.append(
                WeaknessEvidence(
                    question=w.get("question") or "",
                    mode=w.get("mode") or "HR",
                    turn_index=w.get("turn_index"),
                    moment=w.get("moment"),
                    evidence=w.get("evidence") or "",
                )
            )

        return WeaknessStrengthReport(
            session_id=str(session_id),
            strengths=strengths,
            weaknesses=weaknesses,
        )

