from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True)
class ExamDomain:
    id: str
    label: str
    weight: float
    topics: List[str]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExamDomain":
        domain = cls(
            id=str(value["id"]).strip(),
            label=str(value["label"]).strip(),
            weight=float(value["weight"]),
            topics=[str(item).strip() for item in value["topics"] if str(item).strip()],
        )
        if not domain.id or not domain.label or domain.weight <= 0 or not domain.topics:
            raise ValueError("invalid exam domain")
        return domain

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "label": self.label, "weight": self.weight, "topics": list(self.topics)}


@dataclass(frozen=True)
class ExamProfile:
    id: str
    title: str
    provider: str
    version: str
    question_guidance: str
    supports_multiple_response: bool
    domains: List[ExamDomain]
    official_domains: List[str]
    official_source_urls: List[str]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExamProfile":
        profile = cls(
            id=str(value["id"]).strip(),
            title=str(value["title"]).strip(),
            provider=str(value["provider"]).strip(),
            version=str(value["version"]).strip(),
            question_guidance=str(value["question_guidance"]).strip(),
            supports_multiple_response=bool(value["supports_multiple_response"]),
            domains=[ExamDomain.from_mapping(item) for item in value["domains"]],
            official_domains=[_normalize_domain(item) for item in value.get("official_domains", [])],
            official_source_urls=[str(item).strip() for item in value.get("official_source_urls", []) if _is_url(item)],
        )
        if not profile.id or not profile.title or not profile.provider or not profile.domains:
            raise ValueError("invalid exam profile")
        ids = [domain.id for domain in profile.domains]
        if len(ids) != len(set(ids)):
            raise ValueError("exam domain ids must be unique")
        return profile

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "provider": self.provider,
            "version": self.version,
            "question_guidance": self.question_guidance,
            "supports_multiple_response": self.supports_multiple_response,
            "domains": [domain.as_dict() for domain in self.domains],
            "official_domains": list(self.official_domains),
            "official_source_urls": list(self.official_source_urls),
        }

    def domain(self, domain_id: str) -> ExamDomain:
        return next(domain for domain in self.domains if domain.id == domain_id)


def _normalize_domain(value: Any) -> str:
    text = str(value).strip().lower()
    if "://" in text:
        text = urlparse(text).hostname or ""
    return text.strip("./")


def _is_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


SAA_PROFILE = ExamProfile.from_mapping({
    "id": "aws-saa-c03",
    "title": "AWS Certified Solutions Architect - Associate (SAA-C03)",
    "provider": "Amazon Web Services",
    "version": "SAA-C03",
    "question_guidance": "Use scenario-based AWS architecture questions with plausible service trade-offs. Single-response questions have four options. Multiple-response questions have five options and exactly two correct answers.",
    "supports_multiple_response": True,
    "official_domains": ["docs.aws.amazon.com", "aws.amazon.com"],
    "official_source_urls": [
        "https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03.html",
        "https://docs.aws.amazon.com/aws-certification/latest/solutions-architect-associate-03/saa-03-in-scope-services.html",
    ],
    "domains": [
        {
            "id": "security",
            "label": "Design Secure Architectures",
            "weight": 30,
            "topics": [
                "IAM roles, resource policies, permission boundaries, and cross-account access",
                "KMS key policies, grants, envelope encryption, and rotation",
                "VPC security groups, network ACLs, endpoints, and PrivateLink",
                "S3 access control, Block Public Access, encryption, and presigned URLs",
                "Secrets Manager, Parameter Store, ACM, WAF, Shield, and GuardDuty",
                "Organizations SCPs, multi-account guardrails, and centralized logging",
            ],
        },
        {
            "id": "resilience",
            "label": "Design Resilient Architectures",
            "weight": 26,
            "topics": [
                "Multi-AZ versus Multi-Region design and failure isolation",
                "Route 53 routing policies, health checks, and failover",
                "SQS, SNS, EventBridge, retries, DLQs, and idempotency",
                "Auto Scaling, load balancers, health checks, and stateless tiers",
                "RDS and Aurora replicas, failover, backups, and global databases",
                "disaster recovery: backup/restore, pilot light, warm standby, and multi-site",
            ],
        },
        {
            "id": "performance",
            "label": "Design High-Performing Architectures",
            "weight": 24,
            "topics": [
                "S3, EBS, EFS, and FSx storage selection and performance",
                "CloudFront, Global Accelerator, caching, and edge architecture",
                "EC2 instance families, placement groups, and scaling patterns",
                "DynamoDB capacity, partition keys, indexes, DAX, and global tables",
                "RDS and Aurora read scaling, proxies, and connection management",
                "Kinesis, MSK, Glue, Athena, and high-throughput data ingestion",
            ],
        },
        {
            "id": "cost",
            "label": "Design Cost-Optimized Architectures",
            "weight": 20,
            "topics": [
                "EC2 pricing models, Savings Plans, Reserved Instances, and Spot",
                "S3 storage classes, lifecycle policies, Intelligent-Tiering, and Glacier",
                "NAT Gateway, VPC endpoints, data transfer, and network cost trade-offs",
                "serverless cost optimization with Lambda, Fargate, API Gateway, and queues",
                "database right-sizing, Aurora Serverless, DynamoDB modes, and caching",
                "Cost Explorer, Budgets, CUR, tags, and multi-account cost allocation",
            ],
        },
    ],
})


BUILTIN_EXAMS = {SAA_PROFILE.id: SAA_PROFILE, "saa-c03": SAA_PROFILE, "saa": SAA_PROFILE}


EXAM_PROFILE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "provider": {"type": "string"},
        "version": {"type": "string"},
        "question_guidance": {"type": "string"},
        "supports_multiple_response": {"type": "boolean"},
        "domains": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "weight": {"type": "number"},
                    "topics": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "label", "weight", "topics"],
                "additionalProperties": False,
            },
        },
        "official_domains": {"type": "array", "items": {"type": "string"}},
        "official_source_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "provider",
        "version",
        "question_guidance",
        "supports_multiple_response",
        "domains",
        "official_domains",
        "official_source_urls",
    ],
    "additionalProperties": False,
}


def _extract_output_text(response: Mapping[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"])
            if content.get("type") == "refusal":
                raise RuntimeError("OpenAI refused the exam profile request")
    raise RuntimeError("OpenAI response did not contain output text")


def _source_urls(value: Any) -> List[str]:
    found: List[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "url" and _is_url(item):
                found.append(str(item))
            else:
                found.extend(_source_urls(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_source_urls(item))
    return list(dict.fromkeys(found))


def _profile_id(title: str, version: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", f"{title}-{version}".lower()).strip("-")
    if words:
        return words[:48]
    return "exam-" + hashlib.sha256(title.encode()).hexdigest()[:10]


def resolve_exam_profile(
    *,
    api_key: str,
    model: str,
    exam_name: str,
    reasoning_effort: str = "none",
    max_output_tokens: int = 2600,
    timeout: int = 90,
) -> ExamProfile:
    payload = {
        "model": model,
        "store": False,
        "reasoning": {"effort": reasoning_effort},
        "max_output_tokens": max_output_tokens,
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "input": (
            "Research the current official exam guide for the following certification exam: "
            f"{exam_name}. Use the certification provider's official sources only. Build a reusable study "
            "profile with 2-8 blueprint domains, current weights when officially published, representative "
            "topics, and the real question response styles. If weights are not published, assign sensible "
            "relative weights that total approximately 100 and state no invented percentages in labels. "
            "official_domains must contain only provider-owned domains. official_source_urls must be direct "
            "official exam guide or objective URLs. Keep question_guidance concise."
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "certification_exam_profile",
                "strict": True,
                "schema": EXAM_PROFILE_SCHEMA,
            }
        },
    }
    request = Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
    source_urls = _source_urls(body)
    value["id"] = _profile_id(str(value["title"]), str(value["version"]))
    allowed = [_normalize_domain(item) for item in value.get("official_domains", [])]
    candidates = list(dict.fromkeys(value.get("official_source_urls", []) + source_urls))
    value["official_source_urls"] = [
        url
        for url in candidates
        if _is_url(url)
        and any(
            (urlparse(str(url)).hostname or "").lower() == domain
            or (urlparse(str(url)).hostname or "").lower().endswith("." + domain)
            for domain in allowed
        )
    ][:10]
    return ExamProfile.from_mapping(value)
