"""Fast, deterministic scoring for the answer that was just submitted.

This is intentionally independent of the LLM so feedback is available during an
interview even when an API key or model provider is unavailable.
"""
from __future__ import annotations

import re
from typing import Any


_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]+")
_STOP_WORDS = {
    "about", "after", "again", "also", "and", "answer", "because", "been", "being", "could",
    "describe", "during", "each", "from", "have", "into", "just", "more", "next", "role",
    "that", "their", "them", "then", "there", "they", "this", "time", "what", "when", "with",
    "would", "your", "you", "were", "will", "than", "where", "which", "while", "tell",
}


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD_RE.findall(text) if word.lower() not in _STOP_WORDS}


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def score_response(question: str, answer: str, mode: str = "HR") -> dict[str, Any]:
    """Return a transparent 0-100 response score and component scores.

    HR answers are rewarded for a concrete STAR story. Technical answers reward
    an explained approach, trade-offs, and validation. The result is a coaching
    signal, not an employment decision.
    """
    answer = (answer or "").strip()
    word_count = len(_WORD_RE.findall(answer))
    answer_words = _words(answer)
    question_words = _words(question or "")
    overlap = len(answer_words & question_words) / max(1, min(len(question_words), 6))

    is_hr = str(mode).upper() == "HR"
    if is_hr:
        components = {
            "situation": _has_any(answer, ("situation", "context", "when", "while", "project", "team", "client")),
            "task": _has_any(answer, ("task", "responsib", "goal", "needed to", "asked to", "challenge")),
            "action": _has_any(answer, ("i led", "i created", "i decided", "i worked", "i spoke", "i implemented", "i coordinated", "i changed")),
            "result": _has_any(answer, ("result", "outcome", "improved", "increased", "reduced", "delivered", "achieved", "%", "percent")),
        }
        structure = 20 + 20 * sum(components.values())
        depth = min(78, 22 + word_count * 0.65) + (12 if any(char.isdigit() for char in answer) else 0)
        # Behavioral prompts often share few literal words with a good answer;
        # enough concrete detail is a stronger relevance signal than keyword overlap.
        relevance = min(100, 48 + overlap * 35 + (12 if word_count >= 20 else 0))
        missing = [name for name, present in components.items() if not present]
        if missing:
            feedback = "Add " + ", ".join(missing[:2]) + " to make this a clearer STAR answer."
        else:
            feedback = "Strong STAR structure. Keep using specific actions and measurable outcomes."
    else:
        components = {
            "approach": _has_any(answer, ("approach", "first", "algorithm", "use a", "would use", "iterate")),
            "tradeoff": _has_any(answer, ("complexity", "time", "space", "trade-off", "memory", "optimal")),
            "validation": _has_any(answer, ("test", "edge case", "validate", "example", "error", "case")),
        }
        structure = 25 + 25 * sum(components.values())
        depth = min(80, 15 + word_count * 0.6) + (10 if _has_any(answer, ("o(n", "o(1", "complexity")) else 0)
        relevance = min(100, 40 + overlap * 42 + (12 if word_count >= 25 else 0))
        missing = [name for name, present in components.items() if not present]
        feedback = (
            "Explain the " + " and ".join(missing[:2]) + " in your next answer."
            if missing else "Clear technical reasoning with approach, trade-offs, and validation."
        )

    if word_count < 12:
        relevance = min(relevance, 45)
        depth = min(depth, 30)
        structure = min(structure, 45)
        feedback = "This answer is brief. Add a concrete example and the result you achieved."

    relevance = round(max(0, min(100, relevance)))
    depth = round(max(0, min(100, depth)))
    structure = round(max(0, min(100, structure)))
    overall = round(relevance * 0.35 + depth * 0.35 + structure * 0.30)
    return {
        "overall": overall,
        "relevance": relevance,
        "depth": depth,
        "structure": structure,
        "wordCount": word_count,
        "feedback": feedback,
    }
