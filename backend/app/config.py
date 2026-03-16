from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────
    APP_TITLE: str = "语音情绪分析系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────
    DATABASE_URL: str = "sqlite:////app/data/emotion_app.db"

    # ── Auth ─────────────────────────────────────────
    SECRET_KEY: str = "change-this-secret-key-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # ── File Storage ──────────────────────────────────
    UPLOAD_DIR: str = "/app/uploads/audio"
    MAX_AUDIO_SIZE_MB: int = 50

    # ── Whisper ───────────────────────────────────────
    WHISPER_PROVIDER: str = "local"   # local | openai
    WHISPER_MODEL: str = "base"       # tiny/base/small/medium/large
    WHISPER_DEVICE: str = "cpu"       # cpu | cuda
    OPENAI_API_KEY: str = ""

    # ── LLM ───────────────────────────────────────────
    # provider: ollama | openai | custom
    LLM_PROVIDER: str = "custom"

    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen3:8b"

    # ── Custom LLM (OpenRouter / any OpenAI-compatible API) ───
    # LLM_PROVIDER=custom to activate
    CUSTOM_LLM_BASE_URL: str = "https://v1.neuroweave.asia/chat/completions"
    CUSTOM_LLM_MODEL: str = "openrouter/hunter-alpha"
    CUSTOM_LLM_API_KEY: str = "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"

    # ── CORS ──────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()