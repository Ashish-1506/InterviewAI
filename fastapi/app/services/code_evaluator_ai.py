from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.llm_provider import LLMProvider
from app.core.config import Settings


@dataclass
class CodeReviewResult:
    ai_review: str


class CodeEvaluatorAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._llm = LLMProvider(settings=settings).build_model()

    async def review(self, *, problem_text: str, question_id: str, candidate_code: str, test_summary: dict[str, Any]) -> CodeReviewResult:
        passed = test_summary.get('passed')
        summary = test_summary.get('summary')
        failed = test_summary.get('failedCases') or []

        failed_snippet = ''
        if failed:
            # Include at most 2 failed cases.
            parts = []
            for f in failed[:2]:
                parts.append(f"Input: {f.get('input')} | Expected: {f.get('expected')} | Actual: {f.get('actual')} | Error: {f.get('error')}")
            failed_snippet = "\nFailed cases (up to 2):\n" + "\n".join(parts)

        prompt = (
            "You are an expert software engineer and interviewer. "
            "Provide a qualitative review of the candidate's solution for a coding interview problem. "
            "Be strict about correctness and complexity. "
            "Do NOT reveal hidden test cases beyond what is provided.\n\n"
            "Problem statement (may be abbreviated):\n"
            f"{problem_text}\n\n"
            f"Question ID: {question_id}\n\n"
            f"Test summary: {summary} (passed={passed})\n"
            f"{failed_snippet}\n\n"
            "Candidate code:\n"
            f"{candidate_code}\n\n"
            "Output format (plain text with headings):\n"
            "1) Correctness assessment\n"
            "2) Complexity (time and space) assessment\n"
            "3) Code quality notes\n"
            "4) Improvements (1-2 specific suggestions)\n"
        )

        raw = await self._llm.ainvoke(prompt)
        content = getattr(raw, 'content', None) or str(raw)
        return CodeReviewResult(ai_review=content)

