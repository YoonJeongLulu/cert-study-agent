import json

import pytest

import generator
from exams import SAA_PROFILE
from fallbacks import fallback_lesson


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def test_generate_lesson_uses_responses_structured_output(monkeypatch):
    expected = fallback_lesson("security")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse({
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(expected.as_dict())}],
            }]
        })

    monkeypatch.setattr(generator, "urlopen", fake_urlopen)
    lesson = generator.generate_lesson(
        api_key="test-key",
        model="test-model",
        exam=SAA_PROFILE,
        domain="security",
        topic="cross-account private S3 access",
        question_type="single",
        use_web_search=False,
    )
    assert lesson.question_en == expected.question_en
    assert lesson.source_urls == []
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["store"] is False
    assert captured["payload"]["reasoning"] == {"effort": "none"}
    assert captured["payload"]["max_output_tokens"] == 1600
    assert captured["payload"]["text"]["format"]["type"] == "json_schema"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert lesson.generation_mode == "ai"
    assert lesson.generation_model == "test-model"


def test_refusal_is_reported(monkeypatch):
    monkeypatch.setattr(
        generator,
        "urlopen",
        lambda request, timeout: FakeResponse({
            "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]
        }),
    )
    with pytest.raises(RuntimeError, match="refused"):
        generator.generate_lesson(
            api_key="test-key",
            model="test-model",
            exam=SAA_PROFILE,
            domain="security",
            topic="test",
            question_type="single",
            use_web_search=False,
        )


def test_review_generation_requires_a_different_scenario(monkeypatch):
    previous = fallback_lesson("security")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data.decode())
        return FakeResponse({
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(previous.as_dict())}],
            }]
        })

    monkeypatch.setattr(generator, "urlopen", fake_urlopen)
    generator.generate_lesson(
        api_key="test-key",
        model="test-model",
        exam=SAA_PROFILE,
        domain="security",
        topic=previous.topic,
        question_type="single",
        review_context=previous,
        use_web_search=False,
    )
    prompt = captured["payload"]["input"][1]["content"]
    assert "spaced-repetition review" in prompt
    assert "materially different scenario" in prompt
    assert previous.question_en in prompt
