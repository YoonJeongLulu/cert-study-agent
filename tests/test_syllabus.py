from syllabus import desired_question_type, select_topic
from exams import SAA_PROFILE


def test_topic_selection_is_deterministic():
    first = select_topic("2026092412", SAA_PROFILE)
    second = select_topic("2026092412", SAA_PROFILE)
    assert first == second


def test_recent_topic_is_avoided_when_alternatives_exist():
    domain, topic = select_topic("2026092412", SAA_PROFILE)
    next_domain, next_topic = select_topic("2026092412", SAA_PROFILE, recent_topics=[topic])
    assert next_domain == domain
    assert next_topic != topic


def test_question_type_is_supported():
    assert desired_question_type("2026092412", SAA_PROFILE) in {"single", "multiple"}
