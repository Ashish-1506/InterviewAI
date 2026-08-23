from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document


@dataclass
class QuestionBankLoader:
    settings: Any

    def load(self) -> list[dict[str, Any]]:
        with open(self.settings.question_bank_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # expected formats: either {"questions": [...]} or just [...]
        if isinstance(data, dict) and "questions" in data:
            return data["questions"]
        if isinstance(data, list):
            return data
        raise ValueError("Invalid question bank JSON format")

    def to_documents(self, questions: list[dict[str, Any]]) -> list[Document]:
        docs: list[Document] = []

        for q in questions:
            question_id = str(q.get("id") or q.get("questionId") or "")
            mode = q.get("mode") or q.get("round") or q.get("category")
            category = q.get("category")
            tags = q.get("tags") or q.get("skills") or []
            difficulty = q.get("difficulty")
            text = q.get("question") or q.get("text")

            if not text:
                continue

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "id": question_id,
                        "mode": mode,
                        "category": category,
                        "tags": tags if isinstance(tags, list) else [tags],
                        "difficulty": difficulty,
                    },
                )
            )

        return docs

