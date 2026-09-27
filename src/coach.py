from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from html import escape
from typing import Any, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from config import Config
from content import Lesson
from exams import BUILTIN_EXAMS, ExamProfile, SAA_PROFILE, resolve_exam_profile
from fallbacks import fallback_lesson
from generator import generate_lesson
from local_store import LocalStore
from render import (
    answer_keyboard,
    concept_message,
    explanation_message,
    question_message,
    split_telegram_text,
)
from syllabus import desired_question_type, select_topic
from telegram_api import TelegramAPI


LOG = logging.getLogger(__name__)


class Coach:
    def __init__(self, config: Config, store: LocalStore, api: TelegramAPI):
        self.config = config
        self.store = store
        self.api = api
        self.store.save_exam(SAA_PROFILE)
        self.store.set_default("active_exam_id", SAA_PROFILE.id)
        self.store.set_default("paused", "false")
        self.store.set_default("continuous_mode", "false")
        self.store.set_default("schedule_start_hour", str(config.schedule_start_hour))
        self.store.set_default("schedule_end_hour", str(config.schedule_end_hour))
        self.store.set_default("exam_at", config.exam_at)

    @property
    def chat_id(self) -> int:
        return self.config.telegram_chat_id

    def schedule_hours(self) -> tuple:
        return (
            int(self.store.get_setting("schedule_start_hour", str(self.config.schedule_start_hour))),
            int(self.store.get_setting("schedule_end_hour", str(self.config.schedule_end_hour))),
        )

    def exam_at(self) -> Optional[datetime]:
        value = self.store.get_setting("exam_at", self.config.exam_at).strip()
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(self.config.timezone))
        return parsed.astimezone(ZoneInfo(self.config.timezone))

    def current_slot(self, now: Optional[datetime] = None) -> Optional[str]:
        now = now or datetime.now(ZoneInfo(self.config.timezone))
        deadline = self.exam_at()
        if deadline and now >= deadline:
            return None
        start, end = self.schedule_hours()
        if not start <= now.hour <= end:
            return None
        return now.strftime("%Y%m%d%H")

    def _send_chunks(
        self,
        text: str,
        reply_markup: Optional[Mapping[str, Any]] = None,
    ) -> None:
        chunks = split_telegram_text(text)
        for index, chunk in enumerate(chunks):
            markup = reply_markup if index == len(chunks) - 1 else None
            self.api.send_message(self.chat_id, chunk, reply_markup=markup)

    @staticmethod
    def _main_menu() -> Mapping[str, Any]:
        return {
            "keyboard": [
                [{"text": "🧠 지금 학습"}, {"text": "🔥 연속 문제"}],
                [{"text": "📊 학습 현황"}, {"text": "🎯 시험 선택"}],
                [{"text": "⏰ 알림 설정"}, {"text": "⏸ 일시정지"}],
                [{"text": "▶️ 다시 시작"}, {"text": "❓ 도움말"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
        }

    def _exam_menu(self) -> Mapping[str, Any]:
        active = self.store.active_exam().id
        rows = []
        for exam_id, title in self.store.list_exams():
            label = ("✓ " if exam_id == active else "") + title
            rows.append([{"text": label[:50], "callback_data": f"setexam:{exam_id}"}])
        rows.append([{"text": "➕ 다른 시험 추가", "callback_data": "menu:add_exam"}])
        return {"inline_keyboard": rows}

    def _schedule_menu(self) -> Mapping[str, Any]:
        current = self.schedule_hours()
        presets = [(9, 22), (8, 23), (0, 23)]
        rows = []
        for start, end in presets:
            label = f"{start:02d}:00~{end:02d}:00"
            if current == (start, end):
                label = "✓ " + label
            rows.append([{"text": label, "callback_data": f"schedule:{start}:{end}"}])
        rows.append([{"text": "시험 일시 확인", "callback_data": "menu:deadline"}])
        return {"inline_keyboard": rows}

    def _continuous_keyboard(self) -> Optional[Mapping[str, Any]]:
        if self.store.get_setting("continuous_mode", "false") != "true":
            return None
        return {
            "inline_keyboard": [[
                {"text": "다음 문제 ▶", "callback_data": "practice:next"},
                {"text": "연속 풀이 종료", "callback_data": "practice:stop"},
            ]]
        }

    def _show_exam_menu(self) -> None:
        self.api.send_message(
            self.chat_id,
            "🎯 <b>준비할 시험을 선택하세요.</b>\n목록에 없으면 ‘다른 시험 추가’를 누르면 됩니다.",
            reply_markup=self._exam_menu(),
        )

    def _show_schedule_menu(self) -> None:
        self.api.send_message(
            self.chat_id,
            "⏰ <b>알림 시간대를 선택하세요.</b>\n선택한 범위에서 매시 정각에 한 회차씩 보냅니다.",
            reply_markup=self._schedule_menu(),
        )

    def _create_lesson(
        self,
        exam: ExamProfile,
        domain: str,
        topic: str,
        question_type: str,
        variant: int,
        review_context: Optional[Lesson] = None,
    ) -> Lesson:
        try:
            return generate_lesson(
                api_key=self.config.openai_api_key,
                model=self.config.openai_model,
                exam=exam,
                domain=domain,
                topic=topic,
                question_type=question_type,
                variant=variant,
                review_context=review_context,
                use_web_search=self.config.lesson_web_search,
                reasoning_effort=self.config.openai_reasoning_effort,
                max_output_tokens=self.config.openai_max_output_tokens,
            )
        except Exception:
            LOG.exception("Question generation failed")
            if (
                self.config.allow_fallback_questions
                and exam.id == SAA_PROFILE.id
                and variant == 1
                and review_context is None
            ):
                return fallback_lesson(domain)
            raise

    def send_study_set(self, slot: str, *, ignore_pause: bool = False) -> bool:
        if self.store.is_paused() and not ignore_pause:
            return False
        exam = self.store.active_exam()
        if not self.store.acquire_slot(exam.id, slot):
            return False
        try:
            review = self.store.next_due_review(exam.id)
            if review:
                domain, topic = str(review["domain_id"]), str(review["topic"])
            else:
                domain, topic = select_topic(
                    slot,
                    exam,
                    self.store.domain_stats(exam.id),
                    self.store.recent_topics(exam.id),
                )
            first_type = desired_question_type(slot, exam)
            first = self._create_lesson(
                exam,
                domain,
                topic,
                first_type,
                1,
                review_context=review["lesson"] if review else None,
            )
            lessons = [first]
            if not review and first.needs_second_question and self.config.max_questions_per_lesson >= 2:
                second_type = "single" if first_type == "multiple" else desired_question_type(slot + "-2", exam)
                try:
                    lessons.append(self._create_lesson(exam, domain, topic, second_type, 2))
                except Exception:
                    LOG.warning("Second question was skipped after generation failure")

            self.api.send_message(self.chat_id, concept_message(first, exam, is_review=bool(review)))
            total = len(lessons)
            for index, lesson in enumerate(lessons, 1):
                question_id = uuid.uuid4().hex[:20]
                self.store.save_question(
                    question_id,
                    exam.id,
                    lesson,
                    is_review=bool(review),
                    review_source_id=str(review["id"]) if review else None,
                )
                sent = self.api.send_message(
                    self.chat_id,
                    question_message(
                        lesson,
                        position=(index, total) if total > 1 else None,
                        is_review=bool(review),
                    ),
                    reply_markup=answer_keyboard(question_id, lesson),
                )
                self.store.set_message_id(question_id, int(sent["message_id"]))
            if review:
                self.store.mark_review_sent(str(review["id"]))
            else:
                self.store.note_new_lesson(exam.id)
            self.store.complete_slot(exam.id, slot)
            return True
        except Exception:
            self.store.release_slot(exam.id, slot)
            LOG.exception("Failed to send study set")
            try:
                self.api.send_message(
                    self.chat_id,
                    "⚠️ 이번 회차 문제를 만들지 못했어요. 다음 시간에 자동으로 다시 시도할게요.",
                )
            except Exception:
                LOG.exception("Failed to send generation failure notice")
            return False

    def send_now(self) -> bool:
        slot = datetime.now(ZoneInfo(self.config.timezone)).strftime("manual-%Y%m%d%H%M%S")
        return self.send_study_set(slot, ignore_pause=True)

    def _grade(
        self,
        callback_id: str,
        question_id: str,
        selected: Sequence[int],
        message_id: int,
    ) -> None:
        item = self.store.get_question(question_id)
        if not item:
            self.api.answer_callback(callback_id, "문제 기록을 찾지 못했어요.")
            return
        lesson = item["lesson"]
        selected_values = sorted(set(int(index) for index in selected))
        expected = 1 if lesson.question_type == "single" else 2
        if len(selected_values) != expected:
            self.api.answer_callback(callback_id, f"답을 {expected}개 선택해주세요.")
            return
        is_correct = selected_values == lesson.correct_answer_indices
        if not self.store.record_answer(question_id, selected_values, is_correct):
            self.api.answer_callback(callback_id, "이미 제출한 문제입니다.")
            return
        self.api.answer_callback(callback_id, "정답이에요!" if is_correct else "해설을 확인해보세요.")
        self.api.edit_reply_markup(self.chat_id, message_id, None)
        rows = []
        if not is_correct:
            rows.append([
                {"text": "🔁 복습 예약", "callback_data": f"review:add:{question_id}"},
                {"text": "➡️ 새 개념 계속", "callback_data": f"review:skip:{question_id}"},
            ])
        continuous_markup = self._continuous_keyboard()
        if continuous_markup:
            rows.extend(continuous_markup["inline_keyboard"])
        markup = {"inline_keyboard": rows} if rows else None
        self._send_chunks(explanation_message(lesson, selected_values, is_correct), markup)

    def _handle_callback(self, callback: Mapping[str, Any]) -> None:
        callback_id = str(callback["id"])
        message = callback.get("message") or {}
        if int((message.get("chat") or {}).get("id", 0)) != self.chat_id:
            return
        message_id = int(message["message_id"])
        parts = str(callback.get("data", "")).split(":")
        if len(parts) == 3 and parts[:2] == ["review", "add"]:
            result = self.store.queue_review(parts[2])
            messages = {
                "created": (
                    "🔁 복습을 예약했어요. 새 개념을 최소 2개 학습하고 4시간이 지난 뒤, "
                    "같은 핵심을 다른 시나리오로 다시 출제할게요."
                ),
                "exists": "이미 같은 개념의 복습이 예약되어 있어요.",
                "ineligible": "복습 예약이 가능한 오답 기록을 찾지 못했어요.",
            }
            self.api.answer_callback(callback_id, messages[result])
            self.api.edit_reply_markup(self.chat_id, message_id, None)
            self.api.send_message(
                self.chat_id,
                messages[result],
                reply_markup=self._continuous_keyboard(),
            )
            return
        if len(parts) == 3 and parts[:2] == ["review", "skip"]:
            self.api.answer_callback(callback_id, "새 개념 학습을 계속할게요.")
            self.api.edit_reply_markup(self.chat_id, message_id, None)
            if self._continuous_keyboard():
                self.api.send_message(
                    self.chat_id,
                    "➡️ 복습은 건너뛰었어요. 준비되면 다음 문제를 눌러주세요.",
                    reply_markup=self._continuous_keyboard(),
                )
            return
        if parts == ["practice", "next"]:
            self.api.answer_callback(callback_id, "다음 문제를 준비할게요.")
            self.api.edit_reply_markup(self.chat_id, message_id, None)
            self.api.send_message(self.chat_id, "🔥 다음 문제를 만들고 있어요.")
            self.send_now()
            return
        if parts == ["practice", "stop"]:
            self.store.set_setting("continuous_mode", "false")
            self.api.answer_callback(callback_id, "연속 풀이를 종료했어요.")
            self.api.edit_reply_markup(self.chat_id, message_id, None)
            self.api.send_message(
                self.chat_id,
                "⏹ 연속 풀이를 종료했어요. 매시간 정기 알림은 그대로 유지됩니다.",
            )
            return
        if len(parts) == 2 and parts[0] == "setexam":
            profile = self.store.get_exam(parts[1])
            if profile is None:
                self.api.answer_callback(callback_id, "저장된 시험을 찾지 못했어요.")
                return
            self.store.set_active_exam(profile.id)
            self.api.answer_callback(callback_id, "시험을 변경했어요.")
            self.api.send_message(self.chat_id, f"✅ <b>{escape(profile.title)}</b> 학습을 시작합니다.")
            return
        if parts == ["menu", "add_exam"]:
            self.store.set_setting("pending_action", "add_exam")
            self.api.answer_callback(callback_id, "시험명을 입력해주세요.")
            self.api.send_message(
                self.chat_id,
                "추가할 시험의 정확한 이름이나 코드를 입력해주세요.\n"
                "예: <code>CKA</code>, <code>AZ-104</code>, <code>AWS DVA-C02</code>",
            )
            return
        if len(parts) == 3 and parts[0] == "schedule":
            start, end = int(parts[1]), int(parts[2])
            self.store.set_setting("schedule_start_hour", str(start))
            self.store.set_setting("schedule_end_hour", str(end))
            self.api.answer_callback(callback_id, "알림 시간을 변경했어요.")
            self.api.send_message(self.chat_id, f"⏰ 매일 <b>{start:02d}:00~{end:02d}:00</b>로 변경했습니다.")
            return
        if parts == ["menu", "deadline"]:
            deadline = self.exam_at()
            value = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "미설정"
            self.api.answer_callback(callback_id)
            self.api.send_message(
                self.chat_id,
                f"📅 현재 시험 일시: <b>{value}</b>\n"
                "변경하려면 <code>/deadline 2026-10-05 09:00</code>처럼 보내주세요.",
            )
            return
        if len(parts) == 3 and parts[0] == "answer":
            question_id = parts[1]
            try:
                index = int(parts[2])
            except ValueError:
                self.api.answer_callback(callback_id, "잘못된 선택입니다.")
                return
            item = self.store.get_question(question_id)
            if not item:
                self.api.answer_callback(callback_id, "문제를 찾지 못했어요.")
                return
            lesson = item["lesson"]
            if index < 0 or index >= len(lesson.options_en):
                self.api.answer_callback(callback_id, "잘못된 선택입니다.")
                return
            if lesson.question_type == "single":
                self._grade(callback_id, question_id, [index], message_id)
                return
            try:
                selected = self.store.toggle_selection(question_id, index)
            except ValueError:
                self.api.answer_callback(callback_id, "이미 제출한 문제입니다.")
                return
            self.api.answer_callback(callback_id, "선택을 변경했어요.")
            self.api.edit_message(
                self.chat_id,
                message_id,
                question_message(lesson, selected, is_review=bool(item.get("is_review"))),
                answer_keyboard(question_id, lesson, selected),
            )
            return
        if len(parts) == 2 and parts[0] == "submit":
            question_id = parts[1]
            item = self.store.get_question(question_id)
            if not item:
                self.api.answer_callback(callback_id, "문제를 찾지 못했어요.")
                return
            self._grade(callback_id, question_id, item["selected"], message_id)
            return
        self.api.answer_callback(callback_id, "지원하지 않는 동작입니다.")

    def _help(self) -> str:
        return (
            "🎓 <b>자격증 시간별 코치</b>\n\n"
            "선택한 시험의 핵심 개념과 영어 문제를 보내고, 답을 누르면 즉시 해설합니다.\n\n"
            "/status — 학습 현황\n"
            "/exam — 현재 시험 확인\n"
            "/exam 시험명 — 새 시험의 공식 가이드를 찾아 전환\n"
            "/exams — 저장된 시험 목록\n"
            "/now — 지금 한 회차 학습\n"
            "/practice — 원하는 만큼 연속 풀이\n"
            "/schedule — 알림 시간 확인\n"
            "/schedule 9 22 — 매일 09~22시로 변경\n"
            "/deadline — 시험 일시 확인\n"
            "/deadline 2026-10-05 09:00 — 시험 일시 변경\n"
            "/pause · /resume — 정기 알림 중지·재개"
        )

    def _status(self) -> str:
        exam = self.store.active_exam()
        overall = self.store.overall_stats(exam.id)
        answered, correct = overall["answered"], overall["correct"]
        accuracy = round(correct / answered * 100) if answered else 0
        state = "일시정지" if self.store.is_paused() else "학습 중"
        continuous = self.store.get_setting("continuous_mode", "false") == "true"
        start, end = self.schedule_hours()
        deadline = self.exam_at()
        lines = [
            "📊 <b>학습 현황</b>",
            f"시험: <b>{escape(exam.title)}</b>",
            f"상태: <b>{state}</b>",
            f"연속 풀이: <b>{'켜짐' if continuous else '꺼짐'}</b>",
            f"알림: 매일 <b>{start:02d}:00~{end:02d}:00</b>",
            f"시험 일시: <b>{deadline.strftime('%Y-%m-%d %H:%M') if deadline else '미설정'}</b>",
            f"풀이: <b>{answered}문제</b> · 정답: <b>{correct}문제 ({accuracy}%)</b>",
            f"예약 복습: <b>{self.store.pending_review_count(exam.id)}개</b>",
            (
                f"AI 생성: <b>{escape(self.config.openai_model)}</b> · "
                f"reasoning {escape(self.config.openai_reasoning_effort)} · "
                f"회차 웹 검색 {'켜짐' if self.config.lesson_web_search else '꺼짐'}"
            ),
        ]
        stats = self.store.domain_stats(exam.id)
        if stats:
            lines.append("")
            for domain in exam.domains:
                current = stats.get(domain.id, {})
                count = int(current.get("answered", 0))
                right = int(current.get("correct", 0))
                value = round(right / count * 100) if count else 0
                lines.append(f"• {escape(domain.label)}: {right}/{count} ({value}%)")
        return "\n".join(lines)

    def _switch_exam(self, query: str) -> None:
        key = query.strip().lower()
        profile = BUILTIN_EXAMS.get(key) or self.store.get_exam(query.strip())
        if profile is None:
            self.api.send_message(
                self.chat_id,
                f"🔎 <b>{escape(query)}</b>의 최신 공식 시험 가이드를 확인하고 있어요. 잠시만 기다려주세요.",
            )
            profile = resolve_exam_profile(
                api_key=self.config.openai_api_key,
                model=self.config.openai_model,
                exam_name=query,
                reasoning_effort=self.config.openai_reasoning_effort,
                max_output_tokens=max(2600, self.config.openai_max_output_tokens),
            )
            self.store.save_exam(profile)
        self.store.set_active_exam(profile.id)
        sources = "\n".join(f"• {escape(url)}" for url in profile.official_source_urls[:3])
        source_text = f"\n\n공식 참고 자료\n{sources}" if sources else ""
        self.api.send_message(
            self.chat_id,
            f"✅ 학습 시험을 <b>{escape(profile.title)}</b>로 변경했습니다.\n"
            f"다음 회차부터 새 출제 범위와 기존 오답 통계를 반영합니다.{source_text}",
        )

    def _handle_message(self, message: Mapping[str, Any]) -> None:
        if int((message.get("chat") or {}).get("id", 0)) != self.chat_id:
            return
        text = str(message.get("text", "")).strip()
        menu_actions = {
            "🧠 지금 학습": "/now",
            "🔥 연속 문제": "/practice",
            "📊 학습 현황": "/status",
            "🎯 시험 선택": "/exam",
            "⏰ 알림 설정": "/schedule",
            "⏸ 일시정지": "/pause",
            "▶️ 다시 시작": "/resume",
            "❓ 도움말": "/help",
        }
        pending = self.store.get_setting("pending_action")
        if text in menu_actions:
            self.store.set_setting("pending_action", "")
            text = menu_actions[text]
        elif pending == "add_exam" and not text.startswith("/"):
            self.store.set_setting("pending_action", "")
            try:
                self._switch_exam(text)
            except Exception:
                LOG.exception("Failed to add exam")
                self.api.send_message(
                    self.chat_id,
                    "시험 정보를 확인하지 못했어요. 정확한 시험명이나 시험 코드를 다시 입력해주세요.",
                    reply_markup=self._main_menu(),
                )
            return
        command, _, argument = text.partition(" ")
        if command.startswith("/"):
            command = command.split("@", 1)[0]
        command = command.lower()
        argument = argument.strip()
        if command in {"/start", "/help"}:
            self.api.send_message(self.chat_id, self._help(), reply_markup=self._main_menu())
        elif command == "/status":
            self.api.send_message(self.chat_id, self._status())
        elif command == "/pause":
            self.store.set_paused(True)
            self.store.set_setting("continuous_mode", "false")
            self.api.send_message(self.chat_id, "⏸ 정기 알림을 일시정지했습니다. /resume 으로 다시 시작할 수 있어요.")
        elif command == "/resume":
            self.store.set_paused(False)
            self.api.send_message(self.chat_id, "▶️ 정기 알림을 다시 시작했습니다.")
        elif command == "/exams":
            self._show_exam_menu()
        elif command == "/exam":
            if argument:
                try:
                    self._switch_exam(argument)
                except Exception:
                    LOG.exception("Failed to switch exam")
                    self.api.send_message(self.chat_id, "시험 정보를 확인하지 못했어요. 정확한 시험명이나 시험 코드를 다시 보내주세요.")
            else:
                self._show_exam_menu()
        elif command == "/schedule":
            if not argument:
                self._show_schedule_menu()
                return
            match = re.fullmatch(r"(\d{1,2})\s+(\d{1,2})", argument)
            if not match or not 0 <= int(match.group(1)) <= int(match.group(2)) <= 23:
                self.api.send_message(self.chat_id, "형식: <code>/schedule 9 22</code>")
                return
            start, end = map(int, match.groups())
            self.store.set_setting("schedule_start_hour", str(start))
            self.store.set_setting("schedule_end_hour", str(end))
            self.api.send_message(self.chat_id, f"⏰ 매일 <b>{start:02d}:00~{end:02d}:00</b>로 변경했습니다.")
        elif command == "/deadline":
            if not argument:
                deadline = self.exam_at()
                text = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "미설정"
                self.api.send_message(self.chat_id, f"📅 현재 시험 일시: <b>{text}</b>")
                return
            try:
                deadline = datetime.strptime(argument, "%Y-%m-%d %H:%M").replace(
                    tzinfo=ZoneInfo(self.config.timezone)
                )
            except ValueError:
                self.api.send_message(self.chat_id, "형식: <code>/deadline 2026-10-05 09:00</code>")
                return
            self.store.set_setting("exam_at", deadline.isoformat())
            self.api.send_message(self.chat_id, f"📅 시험 일시를 <b>{deadline.strftime('%Y-%m-%d %H:%M')}</b>로 변경했습니다.")
        elif command == "/now":
            self.store.set_setting("continuous_mode", "false")
            self.api.send_message(self.chat_id, "🧠 지금 학습할 문제를 만들고 있어요.")
            self.send_now()
        elif command == "/practice":
            self.store.set_setting("continuous_mode", "true")
            self.api.send_message(
                self.chat_id,
                "🔥 연속 풀이를 시작합니다. 해설 아래의 ‘다음 문제’를 누르면 계속 풀 수 있어요. "
                "매시간 정기 알림도 그대로 유지됩니다.",
            )
            self.send_now()
        elif command.startswith("/"):
            self.api.send_message(self.chat_id, "지원하지 않는 명령입니다. /help 를 확인해주세요.")

    def handle_update(self, update: Mapping[str, Any]) -> None:
        callback = update.get("callback_query")
        message = update.get("message")
        if callback:
            self._handle_callback(callback)
        elif message:
            self._handle_message(message)
