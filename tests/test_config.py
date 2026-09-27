import json

from config import Config


ENV_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "TZ",
    "SCHEDULE_START_HOUR",
    "SCHEDULE_END_HOUR",
    "EXAM_AT",
    "CERT_COACH_DATABASE_PATH",
    "MAX_QUESTIONS_PER_LESSON",
    "OPENAI_REASONING_EFFORT",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "LESSON_WEB_SEARCH",
    "ALLOW_FALLBACK_QUESTIONS",
]


def clear_config_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_config_can_load_from_environment_only(tmp_path, monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("CERT_COACH_DATABASE_PATH", str(tmp_path / "study.sqlite3"))
    monkeypatch.setenv("LESSON_WEB_SEARCH", "true")

    config = Config.load()

    assert config.telegram_token == "telegram-secret"
    assert config.telegram_chat_id == 12345
    assert config.openai_api_key == "openai-secret"
    assert config.openai_model == "gpt-6-luna"
    assert config.lesson_web_search is True
    assert config.allow_fallback_questions is False


def test_environment_overrides_json_config(tmp_path, monkeypatch):
    clear_config_env(monkeypatch)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "telegram_token": "json-token",
        "telegram_chat_id": 1,
        "openai_api_key": "json-key",
        "database_path": str(tmp_path / "json.sqlite3"),
    }))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "222")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    config = Config.load(str(path))

    assert config.telegram_token == "env-token"
    assert config.telegram_chat_id == 222
    assert config.openai_api_key == "env-key"


def test_invalid_boolean_environment_value_is_rejected(tmp_path, monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret")
    monkeypatch.setenv("ALLOW_FALLBACK_QUESTIONS", "sometimes")

    try:
        Config.load()
    except ValueError as exc:
        assert "invalid boolean" in str(exc)
    else:
        raise AssertionError("invalid boolean value should fail")
