from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class Lesson:
    domain: str
    topic: str
    concept_title_ko: str
    concept_summary_ko: str
    key_points_ko: List[str]
    exam_trap_ko: str
    question_type: str
    question_en: str
    question_ko: str
    options_en: List[str]
    correct_answer_indices: List[int]
    option_explanations_ko: List[str]
    overall_explanation_ko: str
    exam_tip_ko: str
    related_terms: List[str]
    needs_second_question: bool
    source_urls: List[str]
    generation_mode: str = "fallback"
    generation_model: str = ""
    generation_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Lesson":
        lesson = cls(
            domain=str(value["domain"]),
            topic=str(value["topic"]),
            concept_title_ko=str(value["concept_title_ko"]),
            concept_summary_ko=str(value["concept_summary_ko"]),
            key_points_ko=[str(item) for item in value["key_points_ko"]],
            exam_trap_ko=str(value["exam_trap_ko"]),
            question_type=str(value["question_type"]),
            question_en=str(value["question_en"]),
            question_ko=str(value.get("question_ko", "")),
            options_en=[str(item) for item in value["options_en"]],
            correct_answer_indices=[int(item) for item in value["correct_answer_indices"]],
            option_explanations_ko=[str(item) for item in value["option_explanations_ko"]],
            overall_explanation_ko=str(value["overall_explanation_ko"]),
            exam_tip_ko=str(value["exam_tip_ko"]),
            related_terms=[str(item) for item in value["related_terms"]],
            needs_second_question=bool(value["needs_second_question"]),
            source_urls=[str(item) for item in value.get("source_urls", [])],
            generation_mode=str(value.get("generation_mode", "fallback")),
            generation_model=str(value.get("generation_model", "")),
            generation_id=str(value.get("generation_id", "")),
            input_tokens=int(value.get("input_tokens", 0)),
            output_tokens=int(value.get("output_tokens", 0)),
        )
        lesson.validate()
        return lesson

    def validate(self) -> None:
        if not self.domain.strip():
            raise ValueError("exam domain is required")
        if self.question_type not in {"single", "multiple"}:
            raise ValueError("unknown question type")
        expected_options = 4 if self.question_type == "single" else 5
        expected_answers = 1 if self.question_type == "single" else 2
        if len(self.options_en) != expected_options:
            raise ValueError(f"{self.question_type} question needs {expected_options} options")
        if len(self.option_explanations_ko) != expected_options:
            raise ValueError("every option needs an explanation")
        answers = sorted(set(self.correct_answer_indices))
        if len(answers) != expected_answers:
            raise ValueError(f"{self.question_type} question needs {expected_answers} answers")
        if answers != self.correct_answer_indices:
            raise ValueError("answer indices must be sorted and unique")
        if any(index < 0 or index >= expected_options for index in answers):
            raise ValueError("answer index is out of range")
        if not 2 <= len(self.key_points_ko) <= 5:
            raise ValueError("key points must contain 2-5 items")
        required_text = (
            self.topic,
            self.concept_title_ko,
            self.concept_summary_ko,
            self.exam_trap_ko,
            self.question_en,
            self.overall_explanation_ko,
            self.exam_tip_ko,
        )
        if any(not item.strip() for item in required_text):
            raise ValueError("lesson contains blank required text")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "topic": self.topic,
            "concept_title_ko": self.concept_title_ko,
            "concept_summary_ko": self.concept_summary_ko,
            "key_points_ko": list(self.key_points_ko),
            "exam_trap_ko": self.exam_trap_ko,
            "question_type": self.question_type,
            "question_en": self.question_en,
            "question_ko": self.question_ko,
            "options_en": list(self.options_en),
            "correct_answer_indices": list(self.correct_answer_indices),
            "option_explanations_ko": list(self.option_explanations_ko),
            "overall_explanation_ko": self.overall_explanation_ko,
            "exam_tip_ko": self.exam_tip_ko,
            "related_terms": list(self.related_terms),
            "needs_second_question": self.needs_second_question,
            "source_urls": list(self.source_urls),
            "generation_mode": self.generation_mode,
            "generation_model": self.generation_model,
            "generation_id": self.generation_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


LESSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "topic": {"type": "string"},
        "concept_title_ko": {"type": "string"},
        "concept_summary_ko": {"type": "string"},
        "key_points_ko": {"type": "array", "items": {"type": "string"}},
        "exam_trap_ko": {"type": "string"},
        "question_type": {"type": "string", "enum": ["single", "multiple"]},
        "question_en": {"type": "string"},
        "question_ko": {"type": "string"},
        "options_en": {"type": "array", "items": {"type": "string"}},
        "correct_answer_indices": {"type": "array", "items": {"type": "integer"}},
        "option_explanations_ko": {"type": "array", "items": {"type": "string"}},
        "overall_explanation_ko": {"type": "string"},
        "exam_tip_ko": {"type": "string"},
        "related_terms": {"type": "array", "items": {"type": "string"}},
        "needs_second_question": {"type": "boolean"},
        "source_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "domain",
        "topic",
        "concept_title_ko",
        "concept_summary_ko",
        "key_points_ko",
        "exam_trap_ko",
        "question_type",
        "question_en",
        "question_ko",
        "options_en",
        "correct_answer_indices",
        "option_explanations_ko",
        "overall_explanation_ko",
        "exam_tip_ko",
        "related_terms",
        "needs_second_question",
        "source_urls",
    ],
    "additionalProperties": False,
}
