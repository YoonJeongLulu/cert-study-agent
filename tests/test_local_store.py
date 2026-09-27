from datetime import datetime, timedelta, timezone

from fallbacks import fallback_lesson
from exams import SAA_PROFILE
from local_store import LocalStore


def test_exam_question_and_answer_round_trip(tmp_path):
    store = LocalStore(str(tmp_path / "study.sqlite3"))
    store.save_exam(SAA_PROFILE)
    store.set_default("active_exam_id", SAA_PROFILE.id)
    assert store.active_exam().id == SAA_PROFILE.id

    lesson = fallback_lesson("security")
    store.save_question("q1", SAA_PROFILE.id, lesson)
    assert store.toggle_selection("q1", 1) == [1]
    assert store.record_answer("q1", [1], True) is True
    assert store.record_answer("q1", [1], True) is False
    assert store.overall_stats(SAA_PROFILE.id) == {"answered": 1, "correct": 1}


def test_slot_prevents_duplicate_hour(tmp_path):
    store = LocalStore(str(tmp_path / "study.sqlite3"))
    assert store.acquire_slot("exam", "2026100109") is True
    assert store.acquire_slot("exam", "2026100109") is False
    store.release_slot("exam", "2026100109")
    assert store.acquire_slot("exam", "2026100109") is True


def test_wrong_answer_review_waits_for_time_and_two_new_lessons(tmp_path):
    store = LocalStore(str(tmp_path / "study.sqlite3"))
    store.save_exam(SAA_PROFILE)
    lesson = fallback_lesson("security")
    store.save_question("missed", SAA_PROFILE.id, lesson)
    assert store.record_answer("missed", [0], False) is True

    assert store.queue_review("missed") == "created"
    assert store.queue_review("missed") == "exists"
    assert store.pending_review_count(SAA_PROFILE.id) == 1

    future = datetime.now(timezone.utc) + timedelta(hours=5)
    assert store.next_due_review(SAA_PROFILE.id, future) is None
    store.note_new_lesson(SAA_PROFILE.id)
    assert store.next_due_review(SAA_PROFILE.id, future) is None
    store.note_new_lesson(SAA_PROFILE.id)
    review = store.next_due_review(SAA_PROFILE.id, future)
    assert review is not None
    assert review["lesson"].topic == lesson.topic

    store.mark_review_sent(review["id"])
    assert store.pending_review_count(SAA_PROFILE.id) == 0
