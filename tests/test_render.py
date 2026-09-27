from fallbacks import fallback_lesson
from exams import SAA_PROFILE
from render import answer_keyboard, concept_message, explanation_message, question_message, split_telegram_text


def test_html_is_escaped_in_question():
    data = fallback_lesson("security").as_dict()
    data["question_en"] = "Choose A < B & C"
    lesson = type(fallback_lesson("security")).from_mapping(data)
    rendered = question_message(lesson)
    assert "&lt;" in rendered
    assert "&amp;" in rendered


def test_single_keyboard_grades_immediately():
    lesson = fallback_lesson("security")
    keyboard = answer_keyboard("abc123", lesson)
    callbacks = [button["callback_data"] for button in keyboard["inline_keyboard"][0]]
    assert callbacks == [
        "answer:abc123:0",
        "answer:abc123:1",
        "answer:abc123:2",
        "answer:abc123:3",
    ]


def test_multiple_keyboard_marks_selections_and_has_submit():
    data = fallback_lesson("security").as_dict()
    data["question_type"] = "multiple"
    data["options_en"].append("Fifth")
    data["option_explanations_ko"].append("Fifth explanation")
    data["correct_answer_indices"] = [1, 4]
    lesson = type(fallback_lesson("security")).from_mapping(data)
    keyboard = answer_keyboard("qid", lesson, [1])
    assert keyboard["inline_keyboard"][1][0]["text"] == "✓ B"
    assert keyboard["inline_keyboard"][-1][0]["callback_data"] == "submit:qid"


def test_messages_stay_within_telegram_limit_or_split():
    lesson = fallback_lesson("cost")
    assert len(concept_message(lesson, SAA_PROFILE)) < 4096
    chunks = split_telegram_text(explanation_message(lesson, [0], True), limit=300)
    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
