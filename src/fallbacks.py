from __future__ import annotations

from typing import Dict

from content import Lesson


_FALLBACKS: Dict[str, Lesson] = {
    "security": Lesson.from_mapping({
        "domain": "security",
        "topic": "cross-account private S3 access",
        "concept_title_ko": "교차 계정 S3 접근의 정책 교집합",
        "concept_summary_ko": "다른 계정의 IAM 주체가 S3 버킷에 접근하려면 신뢰를 주는 리소스 정책과 호출 주체의 권한 정책을 함께 점검해야 합니다. 퍼블릭 공개나 장기 액세스 키는 필요하지 않습니다.",
        "key_points_ko": ["버킷 정책에서 외부 계정의 역할 ARN을 Principal로 허용합니다.", "외부 역할에도 필요한 S3 작업 권한이 있어야 합니다.", "SSE-KMS 객체라면 KMS 키 정책과 kms:Decrypt 권한도 별도로 확인합니다."],
        "exam_trap_ko": "버킷 ACL이나 퍼블릭 액세스를 켜는 선택지는 대부분 최소 권한 요구와 충돌합니다.",
        "question_type": "single",
        "question_en": "A company stores private reports in an S3 bucket in Account A. An analytics workload in Account B runs with an IAM role. The workload must read only the reports prefix without using long-term credentials. Which solution meets these requirements with the LEAST operational overhead?",
        "question_ko": "한 회사가 계정 A의 S3 버킷에 비공개 보고서를 저장하고 있습니다. 계정 B의 분석 워크로드는 IAM 역할로 실행됩니다. 이 워크로드는 장기 자격 증명을 사용하지 않고 reports 접두사만 읽어야 합니다. 운영 오버헤드를 최소화하면서 요구사항을 충족하는 솔루션은 무엇입니까?",
        "options_en": ["Make the bucket public and restrict access by source IP.", "Add the Account B role as a principal in the bucket policy and grant the role permission to read the reports prefix.", "Create an IAM user in Account A and store its access keys in the workload.", "Enable S3 Transfer Acceleration and share the accelerated endpoint."],
        "correct_answer_indices": [1],
        "option_explanations_ko": ["퍼블릭 공개는 비공개 요구와 최소 권한 원칙을 위반합니다.", "버킷 정책과 역할 정책을 조합하면 임시 자격 증명으로 지정 prefix만 안전하게 허용할 수 있습니다.", "장기 키를 배포하고 교체해야 하므로 요구사항과 운영 효율 모두에 불리합니다.", "Transfer Acceleration은 전송 경로 최적화 기능이며 권한을 부여하지 않습니다."],
        "overall_explanation_ko": "교차 계정 접근은 리소스 소유 계정의 버킷 정책이 외부 역할을 신뢰하고, 외부 역할의 IAM 정책도 해당 객체 읽기를 허용하도록 구성하는 것이 표준 패턴입니다.",
        "exam_tip_ko": "교차 계정 + 장기 키 금지라는 단서가 보이면 역할과 리소스 기반 정책의 조합을 먼저 검토하세요.",
        "related_terms": ["Amazon S3", "AWS IAM"],
        "needs_second_question": False,
        "source_urls": ["https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-walkthroughs-managing-access-example2.html"],
    }),
    "resilience": Lesson.from_mapping({
        "domain": "resilience",
        "topic": "decoupled order processing",
        "concept_title_ko": "SQS로 흡수하는 트래픽 급증과 실패",
        "concept_summary_ko": "생산자와 소비자 사이에 SQS를 두면 처리 속도 차이를 완충하고 소비자 장애 시 메시지를 보존할 수 있습니다. 가시성 제한 시간과 DLQ가 복원력의 핵심입니다.",
        "key_points_ko": ["가시성 제한 시간은 정상 처리 시간보다 충분히 길어야 합니다.", "처리 성공 후에만 메시지를 삭제합니다.", "반복 실패 메시지는 DLQ로 격리합니다."],
        "exam_trap_ko": "Standard Queue는 중복 전달 가능성이 있으므로 소비자는 멱등해야 합니다.",
        "question_type": "single",
        "question_en": "An order service sends jobs to an Amazon SQS standard queue. A worker sometimes takes 4 minutes to finish a job, but the queue visibility timeout is 1 minute. The same order is occasionally processed more than once. What should a solutions architect do FIRST?",
        "question_ko": "주문 서비스가 Amazon SQS 표준 대기열로 작업을 보냅니다. 워커가 작업을 완료하는 데 때때로 4분이 걸리지만, 대기열의 가시성 제한 시간은 1분입니다. 동일한 주문이 가끔 두 번 이상 처리됩니다. 솔루션스 아키텍트가 가장 먼저 해야 할 조치는 무엇입니까?",
        "options_en": ["Increase the message retention period.", "Set the visibility timeout longer than the maximum expected processing time and keep the worker idempotent.", "Replace the queue with an Amazon SNS topic.", "Decrease the long polling wait time."],
        "correct_answer_indices": [1],
        "option_explanations_ko": ["보존 기간은 메시지가 큐에 남는 총기간이며 처리 중 재노출 문제를 해결하지 않습니다.", "처리 중 메시지가 다시 보이는 직접 원인을 해결하며 Standard Queue의 중복 가능성에 대비해 멱등성도 유지합니다.", "SNS는 큐처럼 소비 완료까지 메시지를 보존하고 가시성 시간을 제공하지 않습니다.", "Long polling은 빈 응답과 호출 횟수를 줄이는 설정으로 중복 처리 원인과 무관합니다."],
        "overall_explanation_ko": "작업 시간보다 짧은 가시성 제한 때문에 첫 소비자가 처리 중일 때 메시지가 다시 노출됩니다. 제한 시간을 늘리고 멱등 처리를 유지해야 합니다.",
        "exam_tip_ko": "SQS 중복 처리 문제에서는 가시성 제한, 삭제 시점, 멱등성을 세트로 확인하세요.",
        "related_terms": ["Amazon SQS"],
        "needs_second_question": False,
        "source_urls": ["https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html"],
    }),
    "performance": Lesson.from_mapping({
        "domain": "performance",
        "topic": "global static and dynamic acceleration",
        "concept_title_ko": "CloudFront 캐시와 Global Accelerator의 차이",
        "concept_summary_ko": "CloudFront는 HTTP 콘텐츠를 엣지에 캐시할 수 있고, Global Accelerator는 고정 Anycast IP와 AWS 글로벌 네트워크를 이용해 TCP·UDP 트래픽 경로를 최적화합니다.",
        "key_points_ko": ["정적·캐시 가능한 HTTP 콘텐츠는 CloudFront가 우선입니다.", "비HTTP 또는 캐시할 수 없는 TCP·UDP는 Global Accelerator를 검토합니다.", "둘 다 다중 리전 엔드포인트의 상태 기반 라우팅에 활용될 수 있습니다."],
        "exam_trap_ko": "Global Accelerator는 애플리케이션 응답을 엣지에 캐시하지 않습니다.",
        "question_type": "single",
        "question_en": "A gaming company runs latency-sensitive UDP servers in two AWS Regions. Clients require two static global IP addresses, and traffic must enter the AWS global network near the client and be routed to a healthy regional endpoint. Which service should the company use?",
        "question_ko": "한 게임 회사가 두 AWS 리전에서 지연 시간에 민감한 UDP 서버를 운영합니다. 클라이언트는 두 개의 고정 글로벌 IP 주소를 필요로 하며, 트래픽은 클라이언트와 가까운 지점에서 AWS 글로벌 네트워크로 진입한 뒤 정상 상태인 리전 엔드포인트로 라우팅되어야 합니다. 어떤 서비스를 사용해야 합니까?",
        "options_en": ["Amazon CloudFront", "AWS Global Accelerator", "Amazon Route 53 geolocation routing only", "AWS Direct Connect"],
        "correct_answer_indices": [1],
        "option_explanations_ko": ["CloudFront는 주로 HTTP(S) 콘텐츠 전송과 캐싱에 사용하며 일반 UDP 게임 트래픽 요구에 맞지 않습니다.", "고정 Anycast IP, 가까운 엣지 진입, 상태 기반 엔드포인트 라우팅을 모두 제공합니다.", "Route 53은 DNS 응답을 제공하지만 두 개의 고정 Anycast IP와 동일한 경로 최적화를 제공하지 않습니다.", "Direct Connect는 고객 네트워크와 AWS를 연결하는 전용 회선이며 전 세계 인터넷 사용자를 위한 서비스가 아닙니다."],
        "overall_explanation_ko": "UDP, 고정 글로벌 IP, AWS 백본 진입이라는 세 단서가 Global Accelerator를 가리킵니다.",
        "exam_tip_ko": "캐시라는 단어가 없고 TCP/UDP·고정 IP·빠른 글로벌 경로가 강조되면 Global Accelerator를 떠올리세요.",
        "related_terms": ["AWS Global Accelerator", "Amazon CloudFront"],
        "needs_second_question": False,
        "source_urls": ["https://docs.aws.amazon.com/global-accelerator/latest/dg/what-is-global-accelerator.html"],
    }),
    "cost": Lesson.from_mapping({
        "domain": "cost",
        "topic": "private S3 access without NAT Gateway",
        "concept_title_ko": "S3 Gateway Endpoint로 줄이는 NAT 비용",
        "concept_summary_ko": "프라이빗 서브넷의 워크로드가 S3에만 접근한다면 Gateway VPC Endpoint를 사용해 NAT Gateway의 시간당 비용과 데이터 처리 비용을 피할 수 있습니다.",
        "key_points_ko": ["S3와 DynamoDB는 Gateway Endpoint를 지원합니다.", "라우팅 테이블에 엔드포인트 경로가 추가됩니다.", "엔드포인트 정책으로 접근 범위를 더 제한할 수 있습니다."],
        "exam_trap_ko": "인터넷 게이트웨이를 프라이빗 인스턴스에 직접 연결하는 방식은 동작하지 않으며 공개 경로 요구와도 충돌합니다.",
        "question_type": "single",
        "question_en": "EC2 instances in private subnets upload backups to Amazon S3 in the same Region. They currently use a NAT gateway and incur high data processing charges. The instances do not require general internet access. Which change will reduce cost while keeping traffic off the public internet?",
        "question_ko": "프라이빗 서브넷의 EC2 인스턴스가 같은 리전의 Amazon S3로 백업을 업로드합니다. 현재 NAT Gateway를 사용하여 높은 데이터 처리 비용이 발생하고 있습니다. 인스턴스에는 일반 인터넷 접근이 필요하지 않습니다. 퍼블릭 인터넷을 통하지 않으면서 비용을 줄이는 변경은 무엇입니까?",
        "options_en": ["Create an S3 gateway VPC endpoint and update the private route tables.", "Attach an internet gateway directly to each private subnet.", "Create an interface endpoint for every S3 bucket object.", "Move the instances to public subnets and assign Elastic IP addresses."],
        "correct_answer_indices": [0],
        "option_explanations_ko": ["S3 Gateway Endpoint는 NAT 없이 사설 경로로 S3에 접근하게 하며 별도의 시간당 엔드포인트 비용도 없습니다.", "인터넷 게이트웨이는 서브넷이 아니라 VPC에 연결되며 사설 주소만 가진 인스턴스의 직접 인터넷 경로가 되지 않습니다.", "S3는 인터페이스 엔드포인트도 지원하지만 이 시나리오의 단순 리전 내 접근에는 Gateway Endpoint가 일반적으로 더 경제적입니다.", "공인 IP를 부여하면 보안 요구에 불리하고 NAT 비용을 다른 공개 노출로 바꾸는 셈입니다."],
        "overall_explanation_ko": "리전 내 S3 접근만 필요한 프라이빗 워크로드에는 S3 Gateway Endpoint가 가장 직접적인 비용 최적화입니다.",
        "exam_tip_ko": "NAT 비용 + S3/DynamoDB가 함께 나오면 Gateway Endpoint를 가장 먼저 확인하세요.",
        "related_terms": ["Amazon VPC", "Amazon S3"],
        "needs_second_question": False,
        "source_urls": ["https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html"],
    }),
}


def fallback_lesson(domain: str) -> Lesson:
    return _FALLBACKS.get(domain, _FALLBACKS["security"])
