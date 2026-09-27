#!/usr/bin/env python3
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_DIR / "src"
APP_DIR = Path.home() / "Library" / "Application Support" / "cert-study-coach"
RUNTIME_DIR = APP_DIR / "runtime"
CONFIG_PATH = APP_DIR / "config.json"
DATABASE_PATH = APP_DIR / "study.sqlite3"
LOG_DIR = APP_DIR / "logs"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.openai.cert-study-coach.plist"
LABEL = "com.openai.cert-study-coach"


sys.path.insert(0, str(SOURCE_DIR))
from telegram_api import TelegramAPI  # noqa: E402


def discover_chat_id(api: TelegramAPI) -> int:
    api.call("deleteWebhook", {"drop_pending_updates": True})
    print("\n텔레그램에서 방금 만든 봇에게 /start 를 보내주세요.")
    print("최대 2분 동안 개인 채팅을 기다립니다…")
    deadline = time.monotonic() + 120
    offset = None
    while time.monotonic() < deadline:
        updates = api.get_updates(offset=offset, timeout=10)
        for update in updates:
            offset = int(update["update_id"]) + 1
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            if chat.get("type") == "private" and chat.get("id") is not None:
                api.get_updates(offset=offset, timeout=0)
                return int(chat["id"])
    raise RuntimeError("/start 메시지를 찾지 못했습니다. 설정을 다시 실행해주세요.")


def write_config(token: str, chat_id: int, openai_key: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    value = {
        "telegram_token": token,
        "telegram_chat_id": chat_id,
        "openai_api_key": openai_key,
        "openai_model": "gpt-6-luna",
        "openai_reasoning_effort": "none",
        "openai_max_output_tokens": 1600,
        "lesson_web_search": False,
        "allow_fallback_questions": False,
        "timezone": "Asia/Seoul",
        "schedule_start_hour": 9,
        "schedule_end_hour": 22,
        "exam_at": "2026-10-05T09:00:00+09:00",
        "database_path": str(DATABASE_PATH),
        "max_questions_per_lesson": 2,
    }
    CONFIG_PATH.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONFIG_PATH.chmod(0o600)


def install_runtime() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_DIR, RUNTIME_DIR, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def write_launch_agent() -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(RUNTIME_DIR / "service.py"),
            "--config",
            str(CONFIG_PATH),
        ],
        "WorkingDirectory": str(RUNTIME_DIR),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_DIR / "launchd-out.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd-error.log"),
        "EnvironmentVariables": {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(RUNTIME_DIR),
        },
    }
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle)


def restart_launch_agent() -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", f"{domain}/{LABEL}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(PLIST_PATH)], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{LABEL}"], check=True)


def main() -> int:
    print("자격증 시간별 텔레그램 코치 설정\n")
    token = getpass.getpass("BotFather가 발급한 Telegram bot token: ").strip()
    if not token:
        raise RuntimeError("Telegram bot token이 필요합니다.")
    api = TelegramAPI(token, timeout=20)
    bot = api.call("getMe", {})["result"]
    print(f"봇 확인: @{bot.get('username', bot.get('first_name', 'unknown'))}")
    chat_id = discover_chat_id(api)
    print(f"개인 채팅 확인: {chat_id}")
    openai_key = getpass.getpass("OpenAI API key: ").strip()
    if not openai_key:
        raise RuntimeError("OpenAI API key가 필요합니다.")

    write_config(token, chat_id, openai_key)
    install_runtime()
    write_launch_agent()
    restart_launch_agent()
    api.send_message(
        chat_id,
        "✅ 자격증 학습 에이전트 설정이 끝났어요.\n"
        "기본 시험: AWS SAA-C03\n"
        "알림: 매일 09:00~22:00\n"
        "시험 일시: 2026-10-05 09:00\n\n"
        "/start 를 보내면 버튼 메뉴가 열립니다.",
    )
    print("\n설정 완료! 텔레그램에서 /start 를 보내 메뉴를 열어주세요.")
    print(f"설정 파일: {CONFIG_PATH}")
    print(f"로그 폴더: {LOG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
