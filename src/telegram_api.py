from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TelegramAPI:
    def __init__(self, token: str, timeout: int = 15):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout

    def call(
        self,
        method: str,
        payload: Mapping[str, Any],
        *,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        request = Request(
            f"{self.base_url}/{method}",
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"Telegram {method} returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Telegram {method} request failed: {exc.reason}") from exc
        if not body.get("ok"):
            raise RuntimeError(f"Telegram {method} failed: {body.get('description', 'unknown error')}")
        return body

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: Optional[Mapping[str, Any]] = None,
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": disable_notification,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self.call("sendMessage", payload)["result"]

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self.call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    def edit_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: Optional[Mapping[str, Any]],
    ) -> None:
        self.call(
            "editMessageReplyMarkup",
            {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup or {"inline_keyboard": []}},
        )

    def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: Mapping[str, Any]) -> None:
        self.call(
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": reply_markup,
            },
        )

    def get_updates(self, *, offset: Optional[int], timeout: int = 20) -> list:
        payload: Dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, timeout=timeout + 10).get("result", [])

    def delete_webhook(self) -> None:
        self.call("deleteWebhook", {"drop_pending_updates": False})

    def set_commands(self) -> None:
        self.call("setMyCommands", {"commands": [
            {"command": "status", "description": "학습 현황"},
            {"command": "exam", "description": "현재 시험 확인 또는 변경"},
            {"command": "exams", "description": "저장된 시험 목록"},
            {"command": "now", "description": "지금 한 회차 학습"},
            {"command": "practice", "description": "원하는 만큼 연속 풀이"},
            {"command": "schedule", "description": "알림 시간 확인 또는 변경"},
            {"command": "deadline", "description": "시험 일시 확인 또는 변경"},
            {"command": "pause", "description": "시간별 알림 일시정지"},
            {"command": "resume", "description": "시간별 알림 재개"},
            {"command": "help", "description": "사용 방법"},
        ]})
