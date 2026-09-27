from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from content import LESSON_SCHEMA, Lesson
from exams import ExamProfile, _source_urls


LOG = logging.getLogger(__name__)
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


SYSTEM_PROMPT = """You are an expert certification-exam instructor. Create an original micro-lesson and an
original exam-style question. Never reproduce, request, or claim to reveal real exam questions or exam dumps.
Use only stable facts supported by the current official exam provider documentation. The concept, explanations,
and exam tip must be in natural Korean. The question and every answer option must be in professional English.
Also provide a faithful natural Korean translation of the complete question in question_ko; do not add clues or
change the constraints in the translation. Keep options_en in English for exam practice.
Make the scenario moderately difficult with plausible distractors and applied reasoning rather than trivia.
Avoid ambiguity, explain why every option is correct or incorrect, and keep the result concise enough for
Telegram. source_urls must be an empty array; verified tool sources are attached by the application."""


def _extract_output_text(response: Dict[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
            if content.get("type") == "refusal":
                raise RuntimeError("OpenAI refused the lesson request")
    raise RuntimeError("OpenAI response did not contain output text")


def generate_lesson(
    *,
    api_key: str,
    model: str,
    exam: ExamProfile,
    domain: str,
    topic: str,
    question_type: str,
    variant: int = 1,
    review_context: Optional[Lesson] = None,
    use_web_search: bool = True,
    reasoning_effort: str = "none",
    max_output_tokens: int = 1600,
    timeout: int = 70,
) -> Lesson:
    option_rule = (
        "Produce exactly 4 options and exactly one correct index."
        if question_type == "single"
        else "Produce exactly 5 options and exactly two correct indices."
    )
    review_instruction = ""
    if review_context is not None:
        previous_options = "\n".join(
            f"{index}. {option}" for index, option in enumerate(review_context.options_en)
        )
        review_instruction = f"""
This is a spaced-repetition review of an earlier missed concept. Test the same underlying concept, but create a
materially different scenario: change the actors, workload constraints, numbers, architecture context, distractor
framing, and correct-answer position. Do not reuse the prior wording or reveal that answer. Do not merely negate
or paraphrase the previous question. Set needs_second_question to false.
Prior question for variation control:
{review_context.question_en}
Prior options:
{previous_options}
"""
    prompt = f"""Exam: {exam.title}
Provider: {exam.provider}
Version: {exam.version}
Question style: {exam.question_guidance}
Blueprint domain id: {domain}
Focus topic: {topic}
Required question_type: {question_type}
Question variant: {variant}
{option_rule}
Return question_ko as a complete Korean translation of question_en.
Use zero-based, sorted, unique integers in correct_answer_indices. Return 2-4 Korean key points.
The domain and question_type fields must exactly match the requested values. Set needs_second_question to true
only when this is variant 1, the concept genuinely needs two distinct scenarios for exam readiness, and a second
question would add material coverage. Otherwise set it to false."""
    prompt += review_instruction
    payload = {
        "model": model,
        "store": False,
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": max_output_tokens,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "certification_micro_lesson",
                "strict": True,
                "schema": LESSON_SCHEMA,
            }
        },
    }
    if use_web_search and exam.official_domains:
        payload["tools"] = [{
            "type": "web_search",
            "filters": {"allowed_domains": exam.official_domains[:100]},
        }]
        payload["tool_choice"] = "auto"
        payload["include"] = ["web_search_call.action.sources"]
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI API request failed: {exc.reason}") from exc
    value = json.loads(_extract_output_text(body))
    value["source_urls"] = _source_urls(body)[:5]
    lesson = Lesson.from_mapping(value)
    if lesson.domain != domain or lesson.question_type != question_type:
        raise ValueError("generated lesson did not follow domain or question type")
    if not lesson.question_ko.strip():
        raise ValueError("generated lesson did not include a Korean question translation")
    usage = body.get("usage") or {}
    return replace(
        lesson,
        generation_mode="ai",
        generation_model=model,
        generation_id=str(body.get("id", "")),
        input_tokens=int(usage.get("input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
    )
