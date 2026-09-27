# CertPulse

> 공부하러 찾아가지 않아도, 시험 문제와 오답 복습이 텔레그램으로 먼저 찾아오는 개인 자격증 학습 에이전트.

CertPulse는 정해진 시간마다 핵심 개념과 시험형 문제를 보내고, 답안 선택·즉시 해설·오답 재출제까지 텔레그램 안에서 끝내는 오픈소스 학습 봇입니다. AWS SAA를 기본 프로필로 제공하며 CKA, AZ-104 등 다른 시험의 공식 가이드를 기반으로 학습 프로필을 추가할 수 있습니다.

실제 시험 문제나 덤프를 수집하지 않습니다. OpenAI Responses API가 시험 범위와 학습 기록을 바탕으로 매 회차 새로운 문제를 생성합니다.

## 핵심 경험

- 매일 지정 시간대에 매시 정각 자동 학습 알림
- 중상 난도 영어 문제와 바로 아래 한국어 번역
- 단일·복수 선택형 Telegram 버튼 답안
- 정오답 즉시 판정, 모든 보기의 한국어 해설과 시험 단서
- 큰 개념은 서로 다른 시나리오로 최대 2문제 출제
- `🔥 연속 문제`로 시간 날 때 원하는 만큼 계속 풀이
- 오답은 새 개념 2개와 최소 4시간 간격을 둔 후 다른 상황으로 재출제
- 영역별 정답률과 최근 출제 이력을 반영한 적응형 주제 선택
- SQLite 기반 중복 방지·학습 기록·복습 큐

## 동작 구조

```text
Telegram
   │ 버튼·명령·정답
   ▼
CertPulse runner ─── SQLite 학습 기록
   │
   └── OpenAI Responses API
         ├── 개념·영문 문제·한국어 번역·해설 생성
         └── 새 시험 등록 시 공식 제공기관 문서 검색
```

봇은 Telegram long polling 방식이므로 **항상 한 인스턴스만 실행**해야 합니다. 두 인스턴스를 실행하면 Telegram `409 Conflict`가 발생합니다.

## 빠른 시작: Docker Compose

Docker가 기본 실행 방식입니다. 먼저 [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)을 설치하고 실행합니다. Apple Silicon(M1 이상)과 Intel 중 자신의 Mac에 맞는 설치 파일을 선택하세요.

```bash
docker --version
docker compose version
```

두 명령 모두 버전이 표시되면 준비가 끝난 것입니다.

### 1. 저장소와 환경변수 준비

```bash
git clone <YOUR_REPOSITORY_URL>
cd cert-study-coach
cp .env.example .env
```

`.env`에서 다음 세 값을 반드시 입력합니다.

```dotenv
TELEGRAM_BOT_TOKEN=BotFather가_발급한_토큰
TELEGRAM_CHAT_ID=내_개인_채팅_ID
OPENAI_API_KEY=OpenAI_Project_API_Key
```

`TELEGRAM_CHAT_ID`를 모르면 봇에게 `/start`를 보낸 뒤 아래 도구를 실행합니다. Bot Token은 화면에 표시되지 않습니다.

```bash
python3 scripts/find_chat_id.py
```

### 2. 실행

기존 `setup.command` 방식의 봇이 실행 중이었다면 Telegram `409 Conflict` 방지를 위해 먼저 중지합니다. 서비스가 없다는 메시지는 무시해도 됩니다.

```bash
launchctl bootout gui/$(id -u)/com.openai.cert-study-coach 2>/dev/null || true
```

```bash
docker compose up -d --build
docker compose logs -f
```

정상 실행 후 Telegram에서 `/start`, `/status`, `/now` 순서로 확인합니다.

```bash
docker compose restart
docker compose down
```

생성되는 로컬 이미지 이름은 `certpulse:latest`입니다. 학습 기록은 Docker named volume `coach-data`에 보존되므로 컨테이너를 다시 만들거나 `docker compose down`을 실행해도 유지됩니다. 볼륨까지 명시적으로 삭제하면 기록도 삭제되므로 `docker compose down -v`는 주의해서 사용하세요.

Docker Desktop이 실행 중이면 컨테이너가 비정상 종료되거나 Mac을 재시작한 뒤에도 자동으로 다시 시작됩니다. 다만 Mac이 꺼지거나 잠들면 알림도 멈추므로 24시간 운영하려면 같은 이미지를 상시 켜진 서버에 배포해야 합니다.

## macOS 로컬 설치

Docker 없이 Mac 로그인 세션에서 계속 실행하려면:

```bash
./setup.command
```

설정 도구가 Bot Token과 OpenAI API 키를 숨김 입력으로 받고, 개인 Chat ID를 찾은 후 다음 항목을 구성합니다.

- 런타임·설정·SQLite: `~/Library/Application Support/cert-study-coach/`
- 로그: `~/Library/Application Support/cert-study-coach/logs/`
- 자동 실행: `~/Library/LaunchAgents/com.openai.cert-study-coach.plist`

Mac이 켜져 있고 사용자가 로그인되어 있어야 하며, 잠자기 중에는 알림이 지연될 수 있습니다.

## 환경변수

환경변수는 JSON 설정 파일보다 우선합니다.

| 변수 | 필수 | 기본값 | 설명 |
|---|---:|---|---|
| `TELEGRAM_BOT_TOKEN` | ✓ | - | BotFather 발급 토큰 |
| `TELEGRAM_CHAT_ID` | ✓ | - | 메시지를 받을 개인 채팅 ID |
| `OPENAI_API_KEY` | ✓ | - | OpenAI 프로젝트 API 키 |
| `OPENAI_MODEL` |  | `gpt-6-luna` | 문제 생성 모델 |
| `OPENAI_REASONING_EFFORT` |  | `none` | 추론 강도 |
| `OPENAI_MAX_OUTPUT_TOKENS` |  | `1600` | 회차당 출력 상한 |
| `TZ` |  | `Asia/Seoul` | 서비스 시간대 |
| `SCHEDULE_START_HOUR` |  | `9` | 알림 시작 시각 |
| `SCHEDULE_END_HOUR` |  | `22` | 알림 종료 시각 |
| `EXAM_AT` |  | 빈 값 | ISO 8601 시험 일시 |
| `CERT_COACH_DATABASE_PATH` |  | `./data/study.sqlite3` | SQLite 파일 경로 |
| `MAX_QUESTIONS_PER_LESSON` |  | `2` | 큰 개념의 최대 문제 수 |
| `LESSON_WEB_SEARCH` |  | `false` | 일반 회차별 웹 검색 여부 |
| `ALLOW_FALLBACK_QUESTIONS` |  | `false` | API 장애 시 내장 SAA 문제 허용 여부 |

비용을 낮추기 위해 일반 회차 웹 검색은 기본적으로 끕니다. 새 시험을 추가할 때는 공식 제공기관의 최신 시험 가이드를 찾기 위해 웹 검색이 사용될 수 있습니다.

## Telegram 사용법

하단 메뉴에서 대부분의 기능을 사용할 수 있습니다.

- `🧠 지금 학습`: 즉시 한 회차 생성
- `🔥 연속 문제`: 해설 후 다음 문제를 계속 생성
- `📊 학습 현황`: 정답률·복습 큐·AI 설정 확인
- `🎯 시험 선택`: 저장된 시험 전환 또는 새 시험 등록
- `⏰ 알림 설정`: 정기 알림 시간대 변경
- `⏸ 일시정지` / `▶️ 다시 시작`: 정기 알림 제어

명령어 예시:

```text
/exam CKA
/exam AZ-104
/practice
/schedule 9 22
/deadline 2026-10-05 09:00
```

## 배포 시 주의사항

- `.env`, `config.json`, SQLite DB와 로그는 Git에 커밋하지 않습니다.
- GitHub Actions·Render·Railway·Fly.io 등에서는 저장소 변수가 아니라 플랫폼의 **Secrets**에 키를 등록합니다.
- SQLite를 유지하려면 영구 디스크/볼륨이 필요합니다.
- Telegram long polling 충돌을 막기 위해 replica는 반드시 `1`로 유지합니다.
- 무료 플랜의 sleep/scale-to-zero가 켜지면 정시 알림이 누락될 수 있습니다.
- API 키에는 만료일과 지출 한도를 설정하고 주기적으로 교체하는 편이 안전합니다.

OpenAI 공식 문서도 API 키를 소스나 공개 저장소에 넣지 말고 환경변수 또는 Secret 관리 서비스로 주입하도록 권장합니다: [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices).

## GitHub에 게시

실제 키가 `.env`에만 있고 `git status`에 나타나지 않는지 확인한 다음:

```bash
git init
git add .
git status
git commit -m "Initial release: CertPulse Telegram study agent"
git branch -M main
git remote add origin <YOUR_REPOSITORY_URL>
git push -u origin main
```

키를 한 번이라도 커밋했다면 파일만 삭제하지 말고 해당 키를 즉시 폐기·재발급해야 합니다.

## 개발과 테스트

```bash
python3 -m pytest
```

단위 테스트는 Telegram이나 OpenAI의 실제 외부 API를 호출하지 않습니다.

```text
src/                 봇·스케줄러·문제 생성·저장소
scripts/setup.py     macOS 설치 도구
scripts/find_chat_id.py
tests/               외부 API 없는 단위 테스트
Dockerfile
compose.yaml
.env.example
```
