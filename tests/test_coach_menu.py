from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from coach import Coach
from config import Config
from local_store import LocalStore


class FakeTelegram:
    def __init__(self):
        self.sent = []
        self.callbacks = []
        self.edits = []

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return {"message_id": len(self.sent)}

    def answer_callback(self, callback_id, text=""):
        self.callbacks.append((callback_id, text))

    def edit_reply_markup(self, chat_id, message_id, reply_markup):
        self.edits.append((chat_id, message_id, reply_markup))

    def edit_message(self, chat_id, message_id, text, reply_markup):
        self.edits.append((chat_id, message_id, text, reply_markup))


def make_coach(tmp_path):
    config = Config(
        telegram_token="token",
        telegram_chat_id=123,
        openai_api_key="key",
        openai_model="model",
        timezone="Asia/Seoul",
        schedule_start_hour=9,
        schedule_end_hour=22,
        exam_at="2026-10-05T09:00:00+09:00",
        database_path=str(tmp_path / "study.sqlite3"),
        max_questions_per_lesson=2,
    )
    return Coach(config, LocalStore(config.database_path), FakeTelegram())


def test_start_shows_persistent_button_menu(tmp_path):
    coach = make_coach(tmp_path)
    coach.handle_update({"message": {"chat": {"id": 123}, "text": "/start"}})
    markup = coach.api.sent[-1][2]["reply_markup"]
    labels = [button["text"] for row in markup["keyboard"] for button in row]
    assert "🧠 지금 학습" in labels
    assert "🔥 연속 문제" in labels
    assert "🎯 시험 선택" in labels
    assert markup["is_persistent"] is True


def test_exam_selection_button_opens_inline_menu(tmp_path):
    coach = make_coach(tmp_path)
    coach.handle_update({"message": {"chat": {"id": 123}, "text": "🎯 시험 선택"}})
    markup = coach.api.sent[-1][2]["reply_markup"]
    assert markup["inline_keyboard"][-1][0]["callback_data"] == "menu:add_exam"


def test_schedule_and_deadline_boundaries(tmp_path):
    coach = make_coach(tmp_path)
    tz = ZoneInfo("Asia/Seoul")
    assert coach.current_slot(datetime(2026, 10, 4, 22, 30, tzinfo=tz)) == "2026100422"
    assert coach.current_slot(datetime(2026, 10, 4, 23, 0, tzinfo=tz)) is None
    assert coach.current_slot(datetime(2026, 10, 5, 9, 0, tzinfo=tz)) is None


def test_schedule_can_be_changed_from_inline_menu(tmp_path):
    coach = make_coach(tmp_path)
    coach.handle_update({
        "callback_query": {
            "id": "cb1",
            "data": "schedule:8:23",
            "message": {"message_id": 5, "chat": {"id": 123}},
        }
    })
    assert coach.schedule_hours() == (8, 23)
    assert coach.api.callbacks[-1][1] == "알림 시간을 변경했어요."


def test_answer_button_records_and_sends_explanation(tmp_path):
    from fallbacks import fallback_lesson

    coach = make_coach(tmp_path)
    lesson = fallback_lesson("security")
    coach.store.save_question("q1", coach.store.active_exam().id, lesson)
    coach.handle_update({
        "callback_query": {
            "id": "cb2",
            "data": "answer:q1:1",
            "message": {"message_id": 6, "chat": {"id": 123}},
        }
    })
    assert coach.store.overall_stats(coach.store.active_exam().id) == {"answered": 1, "correct": 1}
    assert any("정답입니다" in text for _, text, _ in coach.api.sent)


def test_wrong_answer_offers_and_queues_spaced_review(tmp_path):
    from fallbacks import fallback_lesson

    coach = make_coach(tmp_path)
    lesson = fallback_lesson("security")
    coach.store.save_question("q1", coach.store.active_exam().id, lesson)
    coach.handle_update({
        "callback_query": {
            "id": "cb-wrong",
            "data": "answer:q1:0",
            "message": {"message_id": 6, "chat": {"id": 123}},
        }
    })
    callbacks = [
        button["callback_data"]
        for row in coach.api.sent[-1][2]["reply_markup"]["inline_keyboard"]
        for button in row
    ]
    assert "review:add:q1" in callbacks

    coach.handle_update({
        "callback_query": {
            "id": "cb-review",
            "data": "review:add:q1",
            "message": {"message_id": 7, "chat": {"id": 123}},
        }
    })
    assert coach.store.pending_review_count(coach.store.active_exam().id) == 1
    assert "복습을 예약했어요" in coach.api.sent[-1][1]


def test_continuous_practice_menu_starts_generation(tmp_path, monkeypatch):
    from fallbacks import fallback_lesson

    coach = make_coach(tmp_path)
    monkeypatch.setattr("coach.generate_lesson", lambda **kwargs: fallback_lesson(kwargs["domain"]))
    coach.handle_update({"message": {"chat": {"id": 123}, "text": "🔥 연속 문제"}})
    assert coach.store.get_setting("continuous_mode") == "true"
    assert any("연속 풀이를 시작" in text for _, text, _ in coach.api.sent)
    assert any("Practice question" in text for _, text, _ in coach.api.sent)


def test_hourly_study_set_sends_concept_and_button_question(tmp_path, monkeypatch):
    from fallbacks import fallback_lesson

    coach = make_coach(tmp_path)
    monkeypatch.setattr("coach.generate_lesson", lambda **kwargs: fallback_lesson(kwargs["domain"]))
    assert coach.send_study_set("2026100409") is True
    assert len(coach.api.sent) == 2
    assert "핵심 개념" in coach.api.sent[0][1]
    assert "inline_keyboard" in coach.api.sent[1][2]["reply_markup"]
    assert coach.store.has_slot(coach.store.active_exam().id, "2026100409") is True


def test_due_review_is_regenerated_as_a_new_scenario(tmp_path, monkeypatch):
    from fallbacks import fallback_lesson

    coach = make_coach(tmp_path)
    prior = fallback_lesson("security")
    exam_id = coach.store.active_exam().id
    coach.store.save_question("missed", exam_id, prior)
    coach.store.record_answer("missed", [0], False)
    coach.store.queue_review("missed")
    with coach.store.connect() as db:
        db.execute(
            "UPDATE reviews SET due_at='2000-01-01T00:00:00+00:00', new_lessons_seen=2 "
            "WHERE id='missed'"
        )

    captured = {}

    def fake_generate(**kwargs):
        captured["review_context"] = kwargs.get("review_context")
        return fallback_lesson(kwargs["domain"])

    monkeypatch.setattr("coach.generate_lesson", fake_generate)
    assert coach.send_study_set("review-slot") is True
    assert captured["review_context"].question_en == prior.question_en
    assert "복습 개념" in coach.api.sent[0][1]
    assert "Review question" in coach.api.sent[1][1]
    with coach.store.connect() as db:
        row = db.execute(
            "SELECT is_review, review_source_id FROM questions "
            "WHERE review_source_id='missed'"
        ).fetchone()
    assert dict(row) == {"is_review": 1, "review_source_id": "missed"}
    assert coach.store.pending_review_count(exam_id) == 0
