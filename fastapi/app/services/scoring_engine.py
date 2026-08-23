from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.core.config import Settings, get_settings
from app.schemas.scoring import CategoryScores, FinalScoreResponse, QuestionScore
from app.services.llm_provider import LLMProvider
from app.services.mongo_store import MongoStore
from app.services.response_scoring import score_response


_DEFAULT_WEIGHTS = {
    "communication": 0.3,
    "technical_depth": 0.25,
    "confidence": 0.25,
    "problem_solving": 0.2,
}


def _clamp_0_10(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        v = 0.0
    return max(0.0, min(10.0, v))


@dataclass
class ScoringEngine:
    settings: Settings
    mongo: MongoStore

    def __post_init__(self) -> None:
        self._llm = LLMProvider(settings=self.settings).build_model()

    def _weights(self) -> Dict[str, float]:
        # Optional: allow weights via JSON env var
        raw = getattr(self.settings, "scoring_weights_json", None)
        if raw:
            try:
                w = json.loads(raw)
                if isinstance(w, dict):
                    merged = {**_DEFAULT_WEIGHTS, **{k: float(v) for k, v in w.items()}}
                    return merged
            except Exception:
                pass
        # Fallback: defaults
        return dict(_DEFAULT_WEIGHTS)

    def _overall_from_category(self, cats: CategoryScores, weights: Dict[str, float]) -> float:
        # Map category 0-10 -> weighted 0-100
        total_w = sum(weights.values()) or 1.0
        score_0_10 = (
            cats.communication * weights.get("communication", 0) +
            cats.technical_depth * weights.get("technical_depth", 0) +
            cats.confidence * weights.get("confidence", 0) +
            cats.problem_solving * weights.get("problem_solving", 0)
        ) / total_w
        return float(max(0.0, min(10.0, score_0_10)) * 10.0)

    def _build_question_judge_prompt(
        self,
        *,
        question: str,
        mode: str,
        answer_text: Optional[str],
        speech_metrics: Optional[Dict[str, Any]],
        emotion_snapshot: Optional[Dict[str, Any]],
        code_eval: Optional[Dict[str, Any]],
        structure_hint: str = "focus on relevance, depth, structure" ,
    ) -> str:
        speech_metrics = speech_metrics or {}
        emotion_snapshot = emotion_snapshot or {}
        code_eval = code_eval or {}

        return (
            "You are an expert interview scorer. "
            "Given the interview question and the candidate's answer (plus optional signals), "
            "produce a strict JSON object ONLY with keys: "
            "relevance (0-10), depth (0-10), structure (0-10), overall (0-10), justification (string).\n\n"
            "Scoring rules:\n"
            "- relevance: did they address the question directly?\n"
            "- depth: concrete details, reasoning, examples; for Technical: correctness cues from code_eval if present.\n"
            "- structure: clarity, organization (STAR for HR / stepwise for Technical).\n"
            "- overall: weighted combination of the three; remain consistent with the justification.\n\n"
            f"Interview mode: {mode}\n\n"
            f"Question: {question}\n\n"
            f"Candidate answer: {answer_text or ''}\n\n"
            f"Speech metrics (may be partial): {speech_metrics}\n\n"
            f"Emotion snapshot (may be partial): {emotion_snapshot}\n\n"
            f"Code evaluation (Technical only; may be partial): {code_eval}\n\n"
            "Return JSON only." 
        )

    async def _judge_question(
        self,
        *,
        question: str,
        mode: str,
        answer_text: Optional[str],
        speech_metrics: Optional[Dict[str, Any]],
        emotion_snapshot: Optional[Dict[str, Any]],
        code_eval: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt = self._build_question_judge_prompt(
            question=question,
            mode=mode,
            answer_text=answer_text,
            speech_metrics=speech_metrics,
            emotion_snapshot=emotion_snapshot,
            code_eval=code_eval,
        )

        try:
            raw = await self._llm.ainvoke(prompt)
            content = getattr(raw, "content", None) or str(raw)
            try:
                data = json.loads(content)
            except Exception:
                start = content.find("{")
                end = content.rfind("}")
                if start < 0 or end <= start:
                    raise
                data = json.loads(content[start : end + 1])
            if not isinstance(data, dict):
                raise ValueError("Scoring response was not a JSON object")
            return data
        except Exception:
            # The same response-based rubric used in the live interview keeps
            # final reports usable if the configured LLM is unavailable.
            local = score_response(question, answer_text or "", mode)
            return {
                "relevance": local["relevance"] / 10,
                "depth": local["depth"] / 10,
                "structure": local["structure"] / 10,
                "overall": local["overall"] / 10,
                "justification": local["feedback"],
            }

    async def score_session(self, session_id: str) -> FinalScoreResponse:
        session_doc = await self.mongo.get_interview_session(session_id)
        if not session_doc:
            raise HTTPException(status_code=404, detail="Session not found")

        turns: List[Dict[str, Any]] = session_doc.get("conversationTurns") or []
        emotion_analysis = session_doc.get("emotionAnalysis") or {}
        aggregated_by_turn = emotion_analysis.get("aggregatedByTurn") or []
        aggregated_by_turn = sorted(aggregated_by_turn, key=lambda x: x.get("turn_index", 0))

        emotion_by_turn: Dict[int, Dict[str, float]] = {}
        for b in aggregated_by_turn:
            ti = int(b.get("turn_index") or 0)
            averages = b.get("averages") or {}
            # keep only requested five categories
            emotion_by_turn[ti] = {k: float(averages.get(k, 0.0)) for k in ["confident","nervous","neutral","engaged","confused"]}

        question_scores: List[QuestionScore] = []

        for idx, t in enumerate(turns):
            question = t.get("question") or ""
            answer_text = t.get("answer")
            mode = t.get("mode") or session_doc.get("type") or "HR"
            question_id = t.get("questionId") or t.get("question_id")

            # The final question is normally still pending; it must not count
            # as an unanswered, zero-score response.
            if not question.strip() or not str(answer_text or "").strip():
                continue

            speech_metrics = None
            if any(k in t for k in ["fillerWordCount", "wpm", "avgPauseLengthS", "verbalConfidence"]):
                speech_metrics = {
                    "fillerWordCount": t.get("fillerWordCount"),
                    "wpm": t.get("wpm"),
                    "avgPauseLengthS": t.get("avgPauseLengthS"),
                    "verbalConfidence": t.get("verbalConfidence"),
                }

            # emotion: best effort to map turn index
            turn_index = idx
            emotion_snapshot = emotion_by_turn.get(turn_index)

            code_eval = t.get("codeSubmission") if isinstance(t.get("codeSubmission"), dict) else None

            stored_score = t.get("responseScore") if isinstance(t.get("responseScore"), dict) else None
            judge = await self._judge_question(
                question=question,
                mode=mode,
                answer_text=answer_text,
                speech_metrics=speech_metrics,
                emotion_snapshot=emotion_snapshot,
                code_eval=code_eval,
            )
            if stored_score and not getattr(self.settings, "openai_api_key", None) and not getattr(self.settings, "gemini_api_key", None):
                judge = {
                    "relevance": float(stored_score.get("relevance", 0)) / 10,
                    "depth": float(stored_score.get("depth", 0)) / 10,
                    "structure": float(stored_score.get("structure", 0)) / 10,
                    "overall": float(stored_score.get("overall", 0)) / 10,
                    "justification": str(stored_score.get("feedback", "")),
                }

            qs = QuestionScore(
                question=question,
                mode=mode,
                question_id=str(question_id) if question_id is not None else None,
                turn_index=turn_index,
                answer_text=answer_text,
                code_submission={k: v for k, v in (t.get("codeSubmission") or {}).items()} if isinstance(t.get("codeSubmission"), dict) else None,
                speech_metrics=speech_metrics,
                emotion_snapshot=emotion_snapshot,
                code_eval=code_eval,
                relevance=_clamp_0_10(judge.get("relevance", 0)),
                depth=_clamp_0_10(judge.get("depth", 0)),
                structure=_clamp_0_10(judge.get("structure", 0)),
                overall=_clamp_0_10(judge.get("overall", 0)),
                justification=str(judge.get("justification", "")),
            )
            question_scores.append(qs)

        # Category aggregation (simple average across question overall + component mapping)
        # Use relevance/depth/structure as proxies.
        if question_scores:
            avg_relevance = sum(q.relevance for q in question_scores) / len(question_scores)
            avg_depth = sum(q.depth for q in question_scores) / len(question_scores)
            avg_structure = sum(q.structure for q in question_scores) / len(question_scores)
            # Confidence proxy: speech metrics verbalConfidence or emotion confident
            conf_vals = []
            ps_vals = []
            tech_vals = []

            for q in question_scores:
                if q.speech_metrics and q.speech_metrics.get("verbalConfidence") is not None:
                    conf_vals.append(float(q.speech_metrics["verbalConfidence"]) / 10.0)
                if q.emotion_snapshot and q.emotion_snapshot.get("confident") is not None:
                    conf_vals.append(float(q.emotion_snapshot["confident"] * 10.0))

                # Technical depth: if Technical mode, rely more on depth; else shallow.
                if q.mode == "Technical":
                    tech_vals.append(q.depth)

                # Problem solving: depth + structure proxy
                ps_vals.append((q.depth * 0.6) + (q.structure * 0.4))

            communication = (avg_structure * 0.6) + (avg_relevance * 0.4)
            technical_depth = (sum(tech_vals)/len(tech_vals)) if tech_vals else (avg_depth)
            confidence = (sum(conf_vals)/len(conf_vals)) if conf_vals else 5.0
            problem_solving = sum(ps_vals)/len(ps_vals) if ps_vals else avg_depth

            cats = CategoryScores(
                communication=_clamp_0_10(communication),
                technical_depth=_clamp_0_10(technical_depth),
                confidence=_clamp_0_10(confidence),
                problem_solving=_clamp_0_10(problem_solving),
            )
        else:
            cats = CategoryScores(communication=0, technical_depth=0, confidence=0, problem_solving=0)

        weights = self._weights()
        overall_0_100 = self._overall_from_category(cats, weights)

        return FinalScoreResponse(
            session_id=str(session_id),
            category_scores=cats,
            overall_score_0_to_100=overall_0_100,
            weights_used=weights,
            question_scores=question_scores,
        )

