from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings


class ChatCompletionModel(Protocol):
    async def ainvoke(self, prompt: str) -> str: ...


class FallbackLLM:
    async def ainvoke(self, prompt: str) -> str:
        # The interview engine has an adaptive local fallback. Returning an
        # invalid model response deliberately routes it there instead of
        # repeating one hard-coded HR question for every answer.
        return ""


@dataclass
class LLMProvider:
    settings: Settings

    def get_provider(self) -> str:
        return (self.settings.llm_provider or "openai").lower()

    def build_model(self) -> Any:
        provider = self.get_provider()

        if provider == "openai":
            if not self.settings.openai_api_key:
                return FallbackLLM()

            try:
                from langchain_openai import ChatOpenAI
            except Exception:
                return FallbackLLM()

            return ChatOpenAI(
                model=self.settings.openai_model,
                api_key=self.settings.openai_api_key,
                temperature=0.2,
            )

        if provider == "gemini":
            if not self.settings.gemini_api_key:
                return FallbackLLM()

            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except Exception:
                return FallbackLLM()

            return ChatGoogleGenerativeAI(
                model=self.settings.gemini_model,
                api_key=self.settings.gemini_api_key,
                temperature=0.2,
            )

        raise ValueError(f"Unsupported llm_provider: {provider}")

