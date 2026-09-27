#!/usr/bin/env python3
from __future__ import annotations

import getpass
import os
from pathlib import Path
import sys
import time


SOURCE_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE_DIR))

from telegram_api import TelegramAPI  # noqa: E402


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Telegram Bot Token: ").strip()
    if not token:
        raise RuntimeError("Telegram Bot Token is required")

    api = TelegramAPI(token, timeout=20)
    api.delete_webhook()
    print("텔레그램에서 봇에게 /start 를 보내주세요. 최대 2분 동안 기다립니다.")
    deadline = time.monotonic() + 120
    offset = None
    while time.monotonic() < deadline:
        for update in api.get_updates(offset=offset, timeout=10):
            offset = int(update["update_id"]) + 1
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            if chat.get("type") == "private" and chat.get("id") is not None:
                print(f"TELEGRAM_CHAT_ID={int(chat['id'])}")
                return 0
    raise RuntimeError("개인 채팅을 찾지 못했습니다. 다시 실행해주세요.")


if __name__ == "__main__":
    raise SystemExit(main())
