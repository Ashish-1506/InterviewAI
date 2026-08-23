from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


SERVICE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="InterviewAI AI Services", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    # LLM provider selection
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    # Gemini (optional; only used when LLm_PROVIDER=gemini)
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    # Backend internal base URL for resolving locally-hosted resume URLs
    backend_internal_base_url: str = Field(default="http://node-api:4000", alias="BACKEND_INTERNAL_BASE_URL")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    # Question bank + FAISS persistence
    question_bank_path: str = Field(
        default=str(SERVICE_ROOT / "data" / "question_bank.json"),
        alias="QUESTION_BANK_PATH",
    )
    faiss_index_path: str = Field(
        default=str(SERVICE_ROOT / "data" / "faiss_index"),
        alias="FAISS_INDEX_PATH",
    )

    # MongoDB (used for conversation state in InterviewSession)
    mongo_uri: str = Field(default="mongodb://mongo:27017/interviewai", alias="MONGODB_URI")
    mongo_db: str = Field(default="interviewai", alias="MONGODB_DB")

    scoring_weights_json: str | None = Field(default=None, alias="SCORING_WEIGHTS_JSON")

    # -------- Part 4: Voice layer --------
    stt_provider: str = Field(default="whisper", alias="STT_PROVIDER")
    stt_whisper_model: str | None = Field(default="base", alias="WHISPER_MODEL")

    tts_provider: str = Field(default="none", alias="TTS_PROVIDER")
    coqui_model: str = Field(default="tts_models/en/ljspeech/tacotron2-DDC", alias="COQUI_MODEL")
    coqui_gpu: bool = Field(default=False, alias="COQUI_GPU")



@lru_cache
def get_settings() -> Settings:
    return Settings()


