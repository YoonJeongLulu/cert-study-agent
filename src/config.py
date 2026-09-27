from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Optional


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value}")


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: int
    openai_api_key: str
    openai_model: str
    timezone: str
    schedule_start_hour: int
    schedule_end_hour: int
    exam_at: str
    database_path: str
    max_questions_per_lesson: int
    openai_reasoning_effort: str = "none"
    openai_max_output_tokens: int = 1600
    lesson_web_search: bool = False
    allow_fallback_questions: bool = False

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        value = {}
        if path:
            config_path = Path(path).expanduser()
            value = json.loads(config_path.read_text(encoding="utf-8"))

        def setting(env_name: str, json_name: str, default: Any = None) -> Any:
            env_value = os.environ.get(env_name)
            return env_value if env_value is not None else value.get(json_name, default)

        config = cls(
            telegram_token=str(setting("TELEGRAM_BOT_TOKEN", "telegram_token", "")).strip(),
            telegram_chat_id=int(setting("TELEGRAM_CHAT_ID", "telegram_chat_id", 0)),
            openai_api_key=str(setting("OPENAI_API_KEY", "openai_api_key", "")).strip(),
            openai_model=str(setting("OPENAI_MODEL", "openai_model", "gpt-6-luna")).strip(),
            timezone=str(setting("TZ", "timezone", "Asia/Seoul")).strip(),
            schedule_start_hour=int(setting("SCHEDULE_START_HOUR", "schedule_start_hour", 9)),
            schedule_end_hour=int(setting("SCHEDULE_END_HOUR", "schedule_end_hour", 22)),
            exam_at=str(setting("EXAM_AT", "exam_at", "")).strip(),
            database_path=str(Path(setting(
                "CERT_COACH_DATABASE_PATH",
                "database_path",
                "./data/study.sqlite3",
            )).expanduser()),
            max_questions_per_lesson=int(setting(
                "MAX_QUESTIONS_PER_LESSON",
                "max_questions_per_lesson",
                2,
            )),
            openai_reasoning_effort=str(setting(
                "OPENAI_REASONING_EFFORT",
                "openai_reasoning_effort",
                "none",
            )).strip(),
            openai_max_output_tokens=int(setting(
                "OPENAI_MAX_OUTPUT_TOKENS",
                "openai_max_output_tokens",
                1600,
            )),
            lesson_web_search=_as_bool(setting(
                "LESSON_WEB_SEARCH",
                "lesson_web_search",
                False,
            )),
            allow_fallback_questions=_as_bool(setting(
                "ALLOW_FALLBACK_QUESTIONS",
                "allow_fallback_questions",
                False,
            )),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.telegram_token or not self.openai_api_key or not self.telegram_chat_id:
            raise ValueError("Telegram token, Telegram chat ID, and OpenAI API key are required")
        if not 0 <= self.schedule_start_hour <= self.schedule_end_hour <= 23:
            raise ValueError("schedule hours must be between 0 and 23")
        if self.max_questions_per_lesson not in {1, 2}:
            raise ValueError("max_questions_per_lesson must be 1 or 2")
        if self.openai_reasoning_effort not in {"none", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported reasoning effort")
        if not 600 <= self.openai_max_output_tokens <= 8000:
            raise ValueError("openai_max_output_tokens must be between 600 and 8000")
