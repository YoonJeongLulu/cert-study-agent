from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from content import Lesson
from exams import ExamProfile


class LocalStore:
    def __init__(self, path: str):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exams (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS slots (
                    exam_id TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (exam_id, slot)
                );
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    exam_id TEXT NOT NULL,
                    domain_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    lesson_json TEXT NOT NULL,
                    selected_json TEXT NOT NULL DEFAULT '[]',
                    message_id INTEGER,
                    answered_at TEXT,
                    is_correct INTEGER,
                    is_review INTEGER NOT NULL DEFAULT 0,
                    review_source_id TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    exam_id TEXT NOT NULL,
                    domain_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    lesson_json TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    new_lessons_seen INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                );
                CREATE INDEX IF NOT EXISTS questions_exam_created
                    ON questions(exam_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS reviews_due
                    ON reviews(exam_id, status, due_at, new_lessons_seen);
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(questions)").fetchall()}
            if "is_review" not in columns:
                db.execute("ALTER TABLE questions ADD COLUMN is_review INTEGER NOT NULL DEFAULT 0")
            if "review_source_id" not in columns:
                db.execute("ALTER TABLE questions ADD COLUMN review_source_id TEXT")

    def set_default(self, key: str, value: str) -> None:
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def save_exam(self, profile: ExamProfile) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO exams(id, title, profile_json, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, profile_json=excluded.profile_json",
                (
                    profile.id,
                    profile.title,
                    json.dumps(profile.as_dict(), ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_exams(self) -> List[Tuple[str, str]]:
        with self.connect() as db:
            rows = db.execute("SELECT id, title FROM exams ORDER BY title").fetchall()
        return [(str(row["id"]), str(row["title"])) for row in rows]

    def get_exam(self, exam_id: str) -> Optional[ExamProfile]:
        with self.connect() as db:
            row = db.execute("SELECT profile_json FROM exams WHERE id=?", (exam_id,)).fetchone()
        return ExamProfile.from_mapping(json.loads(row["profile_json"])) if row else None

    def active_exam(self) -> ExamProfile:
        exam_id = self.get_setting("active_exam_id")
        profile = self.get_exam(exam_id)
        if profile is None:
            raise RuntimeError("active exam is not configured")
        return profile

    def set_active_exam(self, exam_id: str) -> None:
        if self.get_exam(exam_id) is None:
            raise KeyError(exam_id)
        self.set_setting("active_exam_id", exam_id)

    def is_paused(self) -> bool:
        return self.get_setting("paused", "false") == "true"

    def set_paused(self, value: bool) -> None:
        self.set_setting("paused", "true" if value else "false")

    def acquire_slot(self, exam_id: str, slot: str) -> bool:
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO slots(exam_id, slot, status, created_at) VALUES (?, ?, 'creating', ?)",
                    (exam_id, slot, datetime.now(timezone.utc).isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def complete_slot(self, exam_id: str, slot: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE slots SET status='sent' WHERE exam_id=? AND slot=?", (exam_id, slot))

    def has_slot(self, exam_id: str, slot: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                "SELECT 1 FROM slots WHERE exam_id=? AND slot=?", (exam_id, slot)
            ).fetchone()
        return row is not None

    def release_slot(self, exam_id: str, slot: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM slots WHERE exam_id=? AND slot=? AND status='creating'", (exam_id, slot))

    def recent_topics(self, exam_id: str, limit: int = 8) -> List[str]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT DISTINCT topic FROM questions WHERE exam_id=? ORDER BY created_at DESC LIMIT ?",
                (exam_id, limit),
            ).fetchall()
        return [str(row["topic"]) for row in rows]

    def domain_stats(self, exam_id: str) -> Dict[str, Dict[str, int]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT domain_id, COUNT(*) AS answered, "
                "SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) AS correct "
                "FROM questions WHERE exam_id=? AND answered_at IS NOT NULL GROUP BY domain_id",
                (exam_id,),
            ).fetchall()
        return {
            str(row["domain_id"]): {"answered": int(row["answered"]), "correct": int(row["correct"] or 0)}
            for row in rows
        }

    def save_question(
        self,
        question_id: str,
        exam_id: str,
        lesson: Lesson,
        *,
        is_review: bool = False,
        review_source_id: Optional[str] = None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO questions(id, exam_id, domain_id, topic, lesson_json, selected_json, "
                "is_review, review_source_id, created_at) VALUES (?, ?, ?, ?, ?, '[]', ?, ?, ?)",
                (
                    question_id,
                    exam_id,
                    lesson.domain,
                    lesson.topic,
                    json.dumps(lesson.as_dict(), ensure_ascii=False),
                    int(is_review),
                    review_source_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def set_message_id(self, question_id: str, message_id: int) -> None:
        with self.connect() as db:
            db.execute("UPDATE questions SET message_id=? WHERE id=?", (message_id, question_id))

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not row:
            return None
        return {
            **dict(row),
            "lesson": Lesson.from_mapping(json.loads(row["lesson_json"])),
            "selected": [int(item) for item in json.loads(row["selected_json"])],
        }

    def toggle_selection(self, question_id: str, index: int) -> List[int]:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT selected_json, answered_at FROM questions WHERE id=?", (question_id,)
            ).fetchone()
            if not row:
                raise KeyError(question_id)
            if row["answered_at"]:
                raise ValueError("question already answered")
            selected = {int(item) for item in json.loads(row["selected_json"])}
            if index in selected:
                selected.remove(index)
            else:
                selected.add(index)
            values = sorted(selected)
            db.execute("UPDATE questions SET selected_json=? WHERE id=?", (json.dumps(values), question_id))
        return values

    def record_answer(self, question_id: str, selected: Sequence[int], correct: bool) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE questions SET selected_json=?, answered_at=?, is_correct=? "
                "WHERE id=? AND answered_at IS NULL",
                (
                    json.dumps(sorted(set(int(item) for item in selected))),
                    datetime.now(timezone.utc).isoformat(),
                    int(correct),
                    question_id,
                ),
            )
        return cursor.rowcount == 1

    def overall_stats(self, exam_id: str) -> Dict[str, int]:
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS answered, SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) AS correct "
                "FROM questions WHERE exam_id=? AND answered_at IS NOT NULL",
                (exam_id,),
            ).fetchone()
        return {"answered": int(row["answered"]), "correct": int(row["correct"] or 0)}

    def queue_review(self, question_id: str) -> str:
        question = self.get_question(question_id)
        if not question or question.get("is_correct") != 0:
            return "ineligible"
        with self.connect() as db:
            same_question = db.execute(
                "SELECT id FROM reviews WHERE id=?",
                (question_id,),
            ).fetchone()
            if same_question:
                return "exists"
            existing = db.execute(
                "SELECT id FROM reviews WHERE exam_id=? AND domain_id=? AND topic=? AND status='pending'",
                (question["exam_id"], question["domain_id"], question["topic"]),
            ).fetchone()
            if existing:
                return "exists"
            now = datetime.now(timezone.utc)
            db.execute(
                "INSERT INTO reviews(id, exam_id, domain_id, topic, lesson_json, due_at, "
                "new_lessons_seen, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, 'pending', ?)",
                (
                    question_id,
                    question["exam_id"],
                    question["domain_id"],
                    question["topic"],
                    question["lesson_json"],
                    (now + timedelta(hours=4)).isoformat(),
                    now.isoformat(),
                ),
            )
        return "created"

    def note_new_lesson(self, exam_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE reviews SET new_lessons_seen = new_lessons_seen + 1 "
                "WHERE exam_id=? AND status='pending'",
                (exam_id,),
            )

    def next_due_review(self, exam_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM reviews WHERE exam_id=? AND status='pending' "
                "AND due_at<=? AND new_lessons_seen>=2 ORDER BY due_at, created_at LIMIT 1",
                (exam_id, now.astimezone(timezone.utc).isoformat()),
            ).fetchone()
        if not row:
            return None
        return {**dict(row), "lesson": Lesson.from_mapping(json.loads(row["lesson_json"]))}

    def mark_review_sent(self, review_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE reviews SET status='sent', sent_at=? WHERE id=? AND status='pending'",
                (datetime.now(timezone.utc).isoformat(), review_id),
            )

    def pending_review_count(self, exam_id: str) -> int:
        with self.connect() as db:
            row = db.execute(
                "SELECT COUNT(*) AS count FROM reviews WHERE exam_id=? AND status='pending'",
                (exam_id,),
            ).fetchone()
        return int(row["count"])

    def cleanup(self, days: int = 120) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM questions WHERE created_at < datetime('now', ?)", (f"-{days} days",))
            db.execute("DELETE FROM slots WHERE created_at < datetime('now', ?)", (f"-{days} days",))
            db.execute("DELETE FROM reviews WHERE created_at < datetime('now', ?)", (f"-{days} days",))
