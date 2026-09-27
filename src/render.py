from __future__ import annotations

from html import escape
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from content import Lesson
from exams import ExamProfile


LETTERS = "ABCDE"


def answer_labels(indices: Iterable[int]) -> str:
    return ", ".join(LETTERS[index] for index in sorted(indices))


def _source_links(urls: Sequence[str]) -> str:
    links = []
    for index, url in enumerate(urls[:3], 1):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        links.append(f'<a href="{escape(url, quote=True)}">공식 자료 {index}</a>')
    return " · ".join(links)


def concept_message(lesson: Lesson, exam: ExamProfile, *, is_review: bool = False) -> str:
    points = "\n".join(f"• {escape(point)}" for point in lesson.key_points_ko)
    terms = ", ".join(escape(name) for name in lesson.related_terms)
    domain = exam.domain(lesson.domain)
    sources = _source_links(lesson.source_urls or exam.official_source_urls)
    source_text = f"\n🔗 {sources}" if sources else ""
    mode = "복습 개념" if is_review else "핵심 개념"
    icon = "🔁" if is_review else "🧠"
    return (
        f"{icon} <b>{escape(exam.version or exam.title)} {mode} · {escape(domain.label)}</b>\n"
        f"<b>{escape(lesson.concept_title_ko)}</b>\n\n"
        f"{escape(lesson.concept_summary_ko)}\n\n"
        f"{points}\n\n"
        f"⚠️ <b>시험 함정</b>\n{escape(lesson.exam_trap_ko)}\n\n"
        f"<i>관련 키워드: {terms}</i>{source_text}"
    )


def question_message(
    lesson: Lesson,
    selected: Optional[Sequence[int]] = None,
    position: Optional[Sequence[int]] = None,
    is_review: bool = False,
) -> str:
    kind = "Choose ONE" if lesson.question_type == "single" else "Choose TWO"
    position_text = f" · {position[0]}/{position[1]}" if position else ""
    options = "\n".join(
        f"<b>{LETTERS[index]}.</b> {escape(option)}"
        for index, option in enumerate(lesson.options_en)
    )
    selected_text = ""
    if lesson.question_type == "multiple":
        labels = answer_labels(selected or []) or "없음"
        selected_text = f"\n\n현재 선택: <b>{labels}</b>"
    label = "Review question" if is_review else "Practice question"
    translation = ""
    if lesson.question_ko:
        translation = f"\n\n🇰🇷 <b>한국어 문제 번역</b>\n{escape(lesson.question_ko)}"
    if lesson.generation_mode == "ai":
        response_tag = escape(lesson.generation_id[:18]) if lesson.generation_id else "new-response"
        token_text = ""
        if lesson.input_tokens or lesson.output_tokens:
            token_text = f" · tokens {lesson.input_tokens}/{lesson.output_tokens}"
        provenance = (
            f"\n\n🤖 <i>AI generated · {escape(lesson.generation_model)} · "
            f"{response_tag}{token_text}</i>"
        )
    else:
        provenance = "\n\n📦 <i>Built-in fallback question</i>"
    return (
        f"🧩 <b>{label}{position_text} · {kind}</b>\n\n"
        f"🇬🇧 <b>English</b>\n{escape(lesson.question_en)}"
        f"{translation}\n\n{options}{selected_text}{provenance}"
    )


def answer_keyboard(
    question_id: str,
    lesson: Lesson,
    selected: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    selected_set = set(selected or [])
    buttons: List[Dict[str, str]] = []
    for index in range(len(lesson.options_en)):
        mark = "✓ " if index in selected_set else ""
        buttons.append({
            "text": mark + LETTERS[index],
            "callback_data": f"answer:{question_id}:{index}",
        })
    rows = [buttons] if lesson.question_type == "single" else [[button] for button in buttons]
    if lesson.question_type == "multiple":
        rows.append([{"text": "선택 제출", "callback_data": f"submit:{question_id}"}])
    return {"inline_keyboard": rows}


def explanation_message(lesson: Lesson, selected: Sequence[int], is_correct: bool) -> str:
    heading = "✅ <b>정답입니다!</b>" if is_correct else "❌ <b>아쉽습니다.</b>"
    option_notes = "\n".join(
        f"<b>{LETTERS[index]}.</b> {escape(note)}"
        for index, note in enumerate(lesson.option_explanations_ko)
    )
    return (
        f"{heading}\n"
        f"선택: <b>{answer_labels(selected) or '없음'}</b> · "
        f"정답: <b>{answer_labels(lesson.correct_answer_indices)}</b>\n\n"
        f"{escape(lesson.overall_explanation_ko)}\n\n"
        f"<b>보기 해설</b>\n{option_notes}\n\n"
        f"🎯 <b>Exam clue</b>\n{escape(lesson.exam_tip_ko)}"
    )


def split_telegram_text(text: str, limit: int = 4000) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > limit:
            chunks.append(paragraph[:limit])
            paragraph = paragraph[limit:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks
