from __future__ import annotations

import hashlib
from typing import List, Mapping, Optional, Sequence, Tuple

from exams import ExamProfile


def _stable_fraction(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def select_topic(
    slot: str,
    exam: ExamProfile,
    domain_stats: Optional[Mapping[str, Mapping[str, int]]] = None,
    recent_topics: Optional[Sequence[str]] = None,
) -> Tuple[str, str]:
    """Choose a blueprint-weighted topic, increasing weight for weak domains."""
    domain_stats = domain_stats or {}
    recent = set(recent_topics or ())
    weighted: List[Tuple[str, float]] = []
    for domain in exam.domains:
        stats = domain_stats.get(domain.id, {})
        answered = int(stats.get("answered", 0))
        correct = int(stats.get("correct", 0))
        accuracy = (correct / answered) if answered else 0.65
        weakness_boost = 1.0 + max(0.0, 0.75 - accuracy)
        weighted.append((domain.id, domain.weight * weakness_boost))

    point = _stable_fraction("domain:" + slot) * sum(weight for _, weight in weighted)
    domain = weighted[-1][0]
    cursor = 0.0
    for candidate, weight in weighted:
        cursor += weight
        if point < cursor:
            domain = candidate
            break

    domain_spec = exam.domain(domain)
    candidates = [topic for topic in domain_spec.topics if topic not in recent]
    if not candidates:
        candidates = list(domain_spec.topics)
    index = int(_stable_fraction("topic:" + slot) * len(candidates))
    return domain, candidates[min(index, len(candidates) - 1)]


def desired_question_type(slot: str, exam: ExamProfile) -> str:
    """Roughly one in five lessons uses the exam's multiple-response style."""
    if exam.supports_multiple_response and _stable_fraction("type:" + slot) < 0.20:
        return "multiple"
    return "single"
