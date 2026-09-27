import pytest

from content import Lesson
from fallbacks import fallback_lesson


def test_all_fallback_lessons_are_valid():
    for domain in ("security", "resilience", "performance", "cost"):
        lesson = fallback_lesson(domain)
        lesson.validate()
        assert lesson.domain == domain
        assert len(lesson.options_en) == 4


def test_single_question_rejects_multiple_correct_answers():
    data = fallback_lesson("security").as_dict()
    data["correct_answer_indices"] = [0, 1]
    with pytest.raises(ValueError, match="needs 1 answers"):
        Lesson.from_mapping(data)


def test_multiple_question_requires_five_options_and_two_answers():
    data = fallback_lesson("security").as_dict()
    data["question_type"] = "multiple"
    data["options_en"].append("A fifth plausible option")
    data["option_explanations_ko"].append("다섯 번째 보기 해설")
    data["correct_answer_indices"] = [1, 4]
    lesson = Lesson.from_mapping(data)
    assert lesson.question_type == "multiple"
    assert lesson.correct_answer_indices == [1, 4]


def test_legacy_saved_lesson_without_korean_translation_still_loads():
    data = fallback_lesson("security").as_dict()
    data.pop("question_ko")
    lesson = Lesson.from_mapping(data)
    assert lesson.question_ko == ""
