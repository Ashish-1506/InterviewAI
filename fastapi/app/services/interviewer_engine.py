from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.core.config import Settings
from app.schemas.interview_turn import InterviewTurnOut
from app.services.faiss_index import QuestionBankIndex
from app.services.llm_provider import LLMProvider
from app.services.question_bank import QuestionBankLoader
from app.services.mongo_store import MongoStore
from app.services.response_scoring import score_response


@dataclass
class InterviewerEngine:
    settings: Settings
    mongo: MongoStore

    def __post_init__(self) -> None:
        provider = (self.settings.llm_provider or "gemini").lower()

        self._embeddings = None

        try:
            from app.services.faiss_index import LocalFallbackEmbeddings
            self._embeddings = LocalFallbackEmbeddings()
        except Exception:
            self._embeddings = None

        self._llm = LLMProvider(settings=self.settings).build_model()

        self._bank_loader = QuestionBankLoader(settings=self.settings)
        self._bank_index = QuestionBankIndex(settings=self.settings)

        questions = self._bank_loader.load()
        documents = self._bank_loader.to_documents(questions)
        self._vectorstore = self._bank_index.load_or_build(self._embeddings, documents)

    def _format_history(self, turns: list[dict[str, Any]], last_n: int = 6) -> str:
        recent = turns[-last_n:]
        lines = []
        for t in recent:
            q = t.get("question")
            a = t.get("answer")
            if not q or a is None:
                continue
            lines.append(f"Interviewer question: {q}\nCandidate answer: {a}")
        return "\n\n".join(lines)

    def _recent_candidate_answer(self, turns: list[dict[str, Any]]) -> str:
        for turn in reversed(turns):
            answer = (turn.get("answer") or "").strip()
            if answer:
                return answer
        return ""

    def _recent_question(self, turns: list[dict[str, Any]]) -> str:
        for turn in reversed(turns):
            question = (turn.get("question") or "").strip()
            if question:
                return question
        return ""

    @staticmethod
    def _answer_anchor(answer: str) -> str:
        """Pick a useful phrase that makes a follow-up visibly answer-aware."""
        words = re.findall(r"[A-Za-z][A-Za-z'-]+", answer or "")
        ignored = {
            "about", "after", "also", "because", "been", "being", "could", "from", "have", "into",
            "just", "that", "their", "them", "then", "there", "they", "this", "time", "was", "were",
            "what", "when", "with", "would", "your", "you", "and", "the", "for", "our", "but",
        }
        useful = [word for word in words if len(word) > 3 and word.lower() not in ignored]
        return " ".join(useful[:3]) if useful else "that example"

    @staticmethod
    def _missing_star_parts(answer: str) -> list[str]:
        lower = (answer or "").lower()
        checks = {
            "situation": ("situation", "context", "project", "team", "client", "when "),
            "task": ("task", "responsib", "goal", "needed to", "asked to", "challenge"),
            "action": ("i led", "i created", "i decided", "i worked", "i spoke", "i implemented", "i coordinated"),
            "result": ("result", "outcome", "improved", "increased", "reduced", "delivered", "achieved", "%", "percent"),
        }
        return [part for part, signals in checks.items() if not any(signal in lower for signal in signals)]

    @staticmethod
    def _is_repeated_question(question: str, turns: list[dict[str, Any]]) -> bool:
        normalized = re.sub(r"\W+", " ", question.lower()).strip()
        if not normalized:
            return True
        previous = {
            re.sub(r"\W+", " ", str(turn.get("question") or "").lower()).strip()
            for turn in turns
        }
        return normalized in previous

    def _extract_question_payload(self, raw_content: str) -> dict[str, Any] | None:
        content = raw_content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                payload = json.loads(content[start : end + 1])
                if isinstance(payload, dict):
                    return payload
            except Exception:
                return None

        return None

    def _fallback_hr_question(self, turns: list[dict[str, Any]], resume_json: dict[str, Any], target_role: str) -> tuple[str, str | None]:
        latest_answer = self._recent_candidate_answer(turns)
        answered_turns = [turn for turn in turns if str(turn.get("answer") or "").strip()]
        project_names = []
        for project in resume_json.get("projects") or []:
            name = project.get("name")
            if name:
                project_names.append(str(name))

        if latest_answer:
            anchor = self._answer_anchor(latest_answer)
            missing = self._missing_star_parts(latest_answer)
            if len(latest_answer.split()) < 25:
                return (
                    f"You mentioned {anchor}. What was the situation, what was your responsibility, and what result did you achieve?",
                    None,
                )
            if missing:
                focus = missing[0]
                prompts = {
                    "situation": f"You mentioned {anchor}. What was the context and why was it important?",
                    "task": f"In the {anchor} example, what specifically were you accountable for?",
                    "action": f"You mentioned {anchor}. What actions did you personally take, and why?",
                    "result": f"What measurable outcome came from the {anchor} example?",
                }
                return prompts[focus], None

            themes = [
                "how you collaborated with people who had a different view",
                "a difficult decision you made with incomplete information",
                "a setback you faced and what you changed afterward",
                "how you prioritized competing work under pressure",
            ]
            theme = themes[(len(answered_turns) - 1) % len(themes)]
            return (
                f"Building on your {anchor} example, tell me about {theme}. What did you do and what was the outcome?",
                None,
            )

        if target_role:
            return (
                f"Why are you a strong fit for the {target_role} role, and what evidence from your experience supports that?",
                None,
            )

        return (
            "Tell me about a time you had to handle a challenge with limited information and how you approached it.",
            None,
        )

    def _fallback_technical_question(self, docs: list[Any], turns: list[dict[str, Any]], target_role: str) -> tuple[str, str | None]:
        latest_answer = self._recent_candidate_answer(turns)

        if docs:
            doc = docs[0]
            return str(doc.page_content), str(doc.metadata.get("id") or None)

        if latest_answer:
            return (
                "Walk me through the complexity of the approach you just described, and point out one edge case you would test next.",
                None,
            )

        if target_role:
            return (
                f"Let's start with a core problem relevant to {target_role}: describe how you would approach it, then analyze time and space complexity.",
                None,
            )

        return (
            "Describe a problem-solving approach you would use for a medium-difficulty coding question, then analyze its complexity.",
            None,
        )

    def _dedupe_filter(self, used_ids: set[str]):
        def _fn(meta: dict[str, Any]):
            qid = meta.get("id")
            if not qid:
                return True
            return qid not in used_ids

        return _fn

    def _build_hr_prompt(
        self,
        resume_json: dict[str, Any],
        history_text: str,
        target_role: str,
        current_question: str,
        current_answer: str,
    ):
        return (
            "You are InterviewAI, a professional but encouraging interviewer.\n"
            "Conduct an HR interview (behavioral) using the STAR method.\n"
            "Rules:\n"
            "- Ask exactly ONE question at a time.\n"
            "- If the candidate answer is vague, ask a follow-up probing for Situation, Task, Action, Result.\n"
            "- Reference the candidate's resume projects/experience by name when relevant.\n"
            "- After the first answer, begin the question with \"You mentioned ...\" and quote one concrete word or phrase from that answer.\n"
            "- Do not repeat a previous question or ask a generic background question after an answer was given.\n"
            "- Do not provide answers; only ask questions and request clarifications.\n"
            "- Output JSON only with fields: question, questionId, mode.\n"
            "- Keep the question short, specific, and grounded in the latest candidate answer.\n\n"
            f"Resume JSON: {resume_json}\n\n"
            f"Target role: {target_role}\n\n"
            f"Current question being answered: {current_question}\n"
            f"Current candidate answer: {current_answer}\n\n"
            f"Conversation history (last turns): {history_text}\n\n"
            "Return your next HR behavioral question now."
        )

    def _build_technical_prompt(
        self,
        resume_json: dict[str, Any],
        history_text: str,
        target_role: str,
        used_skill_tags: list[str],
        current_question: str,
        current_answer: str,
        code_eval_summary: str | None = None,
    ):
        extra = ""
        if code_eval_summary:
            extra = (
                "\n\nCandidate code evaluation summary (use to tailor your follow-up):\n"
                f"{code_eval_summary}\n\n"
                "When asking your next question, reference this summary concretely (correctness issues, complexity tradeoffs, and improvement area).\n"
            )

        return (
            "You are InterviewAI, a rigorous technical interviewer.\n"
            "Run a Technical interview using a question bank.\n"
            "Rules:\n"
            "- Ask exactly ONE question at a time.\n"
            "- Use the question context retrieved from the bank to stay specific to the role/skills.\n"
            "- If the candidate seems strong, escalate difficulty. If they struggle, simplify and request more detail.\n"
            "- Never give away the solution/answer. Only ask the question and request the candidate to think step-by-step.\n"
            "- Output JSON only with fields: question, questionId, mode.\n\n"
            f"Resume JSON: {resume_json}\n\n"
            f"Target role: {target_role}\n"
            f"Candidate skills/tags: {used_skill_tags}\n\n"
            f"Current question being answered: {current_question}\n"
            f"Current candidate answer: {current_answer}\n\n"
            f"Conversation history (last turns): {history_text}\n\n"
            f"{extra}"
            "Return your next Technical question now."
        )

    def _extract_used_question_ids(self, turns: list[dict[str, Any]]) -> set[str]:
        used = set()
        for t in turns:
            qid = t.get("questionId") or t.get("question_id")
            if qid:
                used.add(str(qid))
        return used

    def _select_technical_bank_questions(self, candidate_text: str, used_ids: set[str], k: int = 8):
        used_filter = self._dedupe_filter(used_ids)
        docs = self._bank_index.similarity_search(
            vectorstore=self._vectorstore,
            query=candidate_text,
            k=k,
            filter_fn=lambda meta: used_filter(meta),
        )
        return docs

    def _extract_latest_code_eval_summary(self, turns: list[dict[str, Any]]) -> Optional[str]:
        """Best-effort: locate most recent codeSubmission.* fields in conversationTurns."""
        for t in reversed(turns):
            cs = t.get("codeSubmission") if isinstance(t, dict) else None
            if isinstance(cs, dict):
                passed = cs.get("passed")
                summary = cs.get("summary")
                ai_review = cs.get("aiReview")

                if summary or ai_review:
                    parts = []
                    if passed is not None:
                        parts.append(f"Passed: {passed}")
                    if summary:
                        parts.append(f"Execution summary: {summary}")
                    if ai_review:
                        parts.append(f"AI review: {ai_review}")
                    return " | ".join(parts)

        return None

    async def get_next_question(
        self,
        session_doc: dict[str, Any],
        interview_type: str,
        last_n_turns: list[dict[str, Any]] | None = None,
    ):
        parsed_resume = session_doc.get("parsedResumeJson") or {}
        target_role = session_doc.get("targetRole") or ""

        turns = session_doc.get("conversationTurns") or []
        history_turns = last_n_turns if last_n_turns is not None else turns[-6:]
        used_ids = self._extract_used_question_ids(turns)
        history_text = self._format_history(history_turns, last_n=6)
        latest_code_eval_summary = self._extract_latest_code_eval_summary(turns)
        current_question = self._recent_question(turns)
        current_answer = self._recent_candidate_answer(turns)

        if interview_type == "HR":
            prompt = self._build_hr_prompt(
                resume_json=parsed_resume,
                history_text=history_text,
                target_role=target_role,
                current_question=current_question,
                current_answer=current_answer,
            )

            try:
                raw = await self._llm.ainvoke(prompt)
                content = getattr(raw, "content", None) or str(raw)
                payload = self._extract_question_payload(content)
            except Exception:
                payload = None

            question = str(payload.get("question") or "") if payload else ""
            if not question or self._is_repeated_question(question, turns):
                fallback_question, fallback_question_id = self._fallback_hr_question(turns, parsed_resume, target_role)
                return InterviewTurnOut(
                    mode="HR",
                    question=fallback_question,
                    questionId=fallback_question_id,
                    turnIndex=len(turns),
                    response=None,
                )

            return InterviewTurnOut(
                mode="HR",
                question=question,
                questionId=payload.get("questionId"),
                turnIndex=len(turns),
                response=None,
            )

        skills = parsed_resume.get("skills") or []
        candidate_text = " ".join([target_role] + skills)

        docs = self._select_technical_bank_questions(candidate_text, used_ids=used_ids)
        retrieved = "\n".join([f"- ({d.metadata.get('id')}) {d.page_content}" for d in docs[:5]])

        prompt = (
            self._build_technical_prompt(
                resume_json=parsed_resume,
                history_text=history_text,
                target_role=target_role,
                used_skill_tags=skills[:12],
                current_question=current_question,
                current_answer=current_answer,
                code_eval_summary=latest_code_eval_summary,
            )
            + "\n\nRelevant question bank candidates:\n"
            + retrieved
            + "\n\nChoose the best next question from the candidates."
        )

        try:
            raw = await self._llm.ainvoke(prompt)
            content = getattr(raw, "content", None) or str(raw)
            payload = self._extract_question_payload(content)
        except Exception:
            payload = None

        if not payload or not payload.get("question"):
            fallback_question, fallback_question_id = self._fallback_technical_question(docs, turns, target_role)
            return InterviewTurnOut(
                mode="Technical",
                question=fallback_question,
                questionId=fallback_question_id,
                turnIndex=len(turns),
                response=None,
            )

        return InterviewTurnOut(
            mode="Technical",
            question=str(payload["question"]),
            questionId=payload.get("questionId"),
            turnIndex=len(turns),
            response=None,
        )

    async def process_candidate_answer(self, session_id: str, answer: str, received_at: datetime) -> InterviewTurnOut:
        session_doc = await self.mongo.get_interview_session(session_id)
        if not session_doc:
            return InterviewTurnOut(mode="HR", question="Session not found", response=None, questionId=None, turnIndex=0)

        turns = session_doc.get("conversationTurns") or []
        interview_type = session_doc.get("type") or "HR"
        mode = "HR" if interview_type == "HR" else "Technical"

        if turns:
            current_question = self._recent_question(turns)
            response_score = score_response(current_question, answer, mode)
            await self.mongo.update_last_conversation_turn(
                session_id=session_id,
                overlay={
                    "answer": answer,
                    "timestamp": received_at,
                    "submittedAt": received_at,
                    "responseScore": response_score,
                },
            )
        else:
            await self.mongo.append_conversation_turn(
                session_id=session_id,
                turn_doc={
                    "question": "",
                    "answer": answer,
                    "timestamp": received_at,
                    "mode": mode,
                    "questionId": None,
                },
            )

        session_doc = await self.mongo.get_interview_session(session_id)
        if not session_doc:
            return InterviewTurnOut(mode=mode, question="Session not found", response=None, questionId=None, turnIndex=0)

        recent_turns = (session_doc.get("conversationTurns") or [])[-6:]
        next_out = await self.get_next_question(
            session_doc=session_doc,
            interview_type=interview_type,
            last_n_turns=recent_turns,
        )

        if not next_out.question:
            return InterviewTurnOut(
                mode=mode,
                question="Could you expand on your previous answer with a concrete example?",
                questionId=None,
                turnIndex=len(turns),
                response=None,
            )

        next_out.responseScore = response_score if turns else score_response("", answer, mode)
        return next_out

