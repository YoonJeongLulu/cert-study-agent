import json

import exams


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def test_exam_resolver_keeps_only_provider_sources(monkeypatch):
    profile = {
        "title": "Example Certification",
        "provider": "Example Org",
        "version": "EX-1",
        "question_guidance": "Four-option scenario questions.",
        "supports_multiple_response": False,
        "domains": [{"id": "one", "label": "Domain One", "weight": 100, "topics": ["Topic A"]}],
        "official_domains": ["certs.example.com"],
        "official_source_urls": ["https://certs.example.com/guide"],
    }
    body = {
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"url": "https://certs.example.com/objectives"},
                        {"url": "https://unofficial.example.net/notes"},
                    ]
                },
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(profile)}],
            },
        ]
    }
    monkeypatch.setattr(exams, "urlopen", lambda request, timeout: FakeResponse(body))
    resolved = exams.resolve_exam_profile(api_key="key", model="model", exam_name="EX-1")
    assert "https://certs.example.com/guide" in resolved.official_source_urls
    assert "https://certs.example.com/objectives" in resolved.official_source_urls
    assert all("unofficial.example.net" not in url for url in resolved.official_source_urls)
