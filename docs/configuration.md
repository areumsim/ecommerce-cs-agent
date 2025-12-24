# 설정 파일 레퍼런스

이 문서는 프로젝트의 모든 설정 파일 스키마를 설명합니다.

## 설정 파일 목록

| 파일 | 설명 |
|------|------|
| `configs/app.yaml` | 앱 전역 설정 |
| `configs/llm.yaml` | LLM Provider 설정 |
| `configs/rag.yaml` | RAG 검색 설정 |
| `configs/guardrails.yaml` | 입출력 가드레일 |
| `configs/auth.yaml` | 인증/보안 설정 |
| `configs/intents.yaml` | 의도 분류 설정 |

---

## 환경변수 우선순위

환경변수는 YAML 설정보다 우선합니다:

```bash
# 필수
OPENAI_API_KEY=sk-xxx          # OpenAI API 키
ANTHROPIC_API_KEY=sk-ant-xxx   # Anthropic API 키
GOOGLE_API_KEY=AIzaSyxxx       # Google API 키

# 선택
LLM_PROVIDER=openai            # 프로바이더 선택
JWT_SECRET_KEY=xxx             # JWT 시크릿 키 (운영 필수)
APP_PORT=8000                  # API 서버 포트
UI_PORT=7860                   # UI 서버 포트
```

---

## configs/app.yaml

앱 전역 설정입니다.

```yaml
# 앱 정보
app:
  name: "ecommerce-agent"        # 앱 이름
  version: "1.0.0"               # 버전
  description: "..."             # 설명
  environment: "development"     # development | staging | production

# 서버 설정
server:
  host: "0.0.0.0"               # 바인딩 주소
  port: 8000                    # API 서버 포트
  ui_port: 7860                 # UI 서버 포트 (Gradio)
  reload: true                  # 핫 리로드 (개발용)

# 로깅 설정
logging:
  level: "INFO"                 # DEBUG | INFO | WARNING | ERROR
  format: "json"                # text | json
  file: "./log/app.log"         # 로그 파일 경로 (null = 콘솔만)
  rotation:
    max_bytes: 10485760         # 10MB
    backup_count: 5             # 백업 파일 수

# 기본값
defaults:
  user_id: "user_001"           # 테스트용 기본 사용자
  order_limit: 10               # 주문 목록 제한
  ticket_limit: 10              # 티켓 목록 제한
  search_top_k: 5               # 검색 결과 수

# CORS 설정
cors:
  allowed_origins:
    - "*"                       # 운영 시 도메인 명시 권장

# 모니터링
monitoring:
  enable_prometheus: true       # Prometheus 메트릭 활성화
  metrics_path: "/metrics"      # 메트릭 엔드포인트
```

---

## configs/llm.yaml

LLM Provider 설정입니다. 자세한 내용은 [LLM 가이드](llm_guide.md)를 참조하세요.

```yaml
# 사용할 프로바이더: openai | anthropic | google | local
provider: openai

# OpenAI 설정
openai:
  api_key: ""                   # OPENAI_API_KEY 환경변수 권장
  model: gpt-4o-mini            # 모델 선택
  temperature: 0.7              # 0.0 ~ 2.0
  max_tokens: 1024              # 최대 출력 토큰
  timeout: 30                   # 타임아웃 (초)

# Anthropic 설정
anthropic:
  api_key: ""                   # ANTHROPIC_API_KEY 환경변수 권장
  model: claude-3-haiku-20240307
  temperature: 0.7
  max_tokens: 1024
  timeout: 30

# Google Gemini 설정
google:
  api_key: ""                   # GOOGLE_API_KEY 환경변수 권장
  model: gemini-1.5-flash
  temperature: 0.7
  max_tokens: 1024
  timeout: 30

# 로컬 LLM 설정 (vLLM, Ollama)
local:
  base_url: http://localhost:8080/v1
  model: local-model
  temperature: 0.7
  max_tokens: 1024
  timeout: 60                   # 로컬은 더 긴 타임아웃

# 프롬프트 경로
prompts:
  system: configs/prompts/system.txt
  order: configs/prompts/order.txt
  claim: configs/prompts/claim.txt
  policy: configs/prompts/policy.txt
  intent_classification: configs/prompts/intent_classification.txt
```

### 설정 값 설명

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `provider` | string | openai | 사용할 LLM 프로바이더 |
| `api_key` | string | "" | API 키 (환경변수 권장) |
| `model` | string | - | 사용할 모델 이름 |
| `temperature` | float | 0.7 | 응답 다양성 (0.0 ~ 2.0) |
| `max_tokens` | int | 1024 | 최대 출력 토큰 수 |
| `timeout` | int | 30 | 요청 타임아웃 (초) |
| `base_url` | string | - | 로컬 LLM 서버 URL |

---

## configs/rag.yaml

RAG (검색 증강 생성) 설정입니다.

```yaml
# 임베딩 모델 설정
embedding:
  model_name: "intfloat/multilingual-e5-small"  # 다국어 임베딩 모델
  batch_size: 32                                # 배치 크기
  normalize: true                               # 정규화 여부
  device: "auto"                                # auto | cpu | cuda

# 검색 설정
retrieval:
  mode: "hybrid"               # keyword | embedding | hybrid
  default_top_k: 5             # 기본 반환 수
  max_top_k: 20                # 최대 반환 수
  hybrid_alpha: 0.7            # 임베딩 가중치 (0.0~1.0)
  min_score: 0.0               # 최소 점수 임계값
  use_reranking: false         # 리랭킹 사용 여부

# 인덱스 설정
index:
  chunk_size: 1000             # 청크 크기 (문자 수)
  chunk_overlap: 100           # 청크 오버랩
  vector_index_type: "flat"    # flat | ivf
  ivf_nlist: 100               # IVF 클러스터 수

# 경로 설정
paths:
  policies_source: "data/processed/policies.jsonl"
  policies_index: "data/processed/policies_index.jsonl"
  vector_index: "data/processed/policies_vectors.faiss"
  embeddings_cache: "data/processed/policies_embeddings.npy"
```

### 검색 모드 설명

| 모드 | 설명 | 사용 시나리오 |
|------|------|--------------|
| `keyword` | 키워드 기반 검색 | 정확한 용어 검색 |
| `embedding` | 벡터 유사도 검색 | 의미 기반 검색 |
| `hybrid` | 키워드 + 벡터 조합 | 일반적인 사용 (권장) |

### hybrid_alpha 설정

```
hybrid_alpha = 0.0  → 100% 키워드
hybrid_alpha = 0.5  → 50% 키워드 + 50% 임베딩
hybrid_alpha = 0.7  → 30% 키워드 + 70% 임베딩 (기본값)
hybrid_alpha = 1.0  → 100% 임베딩
```

---

## configs/guardrails.yaml

입출력 가드레일 설정입니다.

```yaml
# 입력 가드레일
input:
  max_length: 2000             # 최대 입력 길이
  min_length: 1                # 최소 입력 길이

  # PII 패턴 (개인정보 마스킹)
  pii_patterns:
    phone_kr:
      pattern: "(01[0-9][-.]?\\d{3,4}[-.]?\\d{4})"
      mask: "***-****-****"
      description: "휴대폰 번호"
    email:
      pattern: "([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+)"
      mask: "***@***.***"
      description: "이메일 주소"
    rrn:
      pattern: "(\\d{6}[-.]?[1-4]\\d{6})"
      mask: "******-*******"
      description: "주민등록번호"
    card_number:
      pattern: "(\\d{4}[-.]?\\d{4}[-.]?\\d{4}[-.]?\\d{4})"
      mask: "****-****-****-****"
      description: "카드 번호"

  # 프롬프트 인젝션 패턴
  injection_patterns:
    - "(ignore|disregard|forget)\\s+(previous|all)\\s+(instructions?)"
    - "(you\\s+are\\s+now|act\\s+as)"
    - "jailbreak"
    - "(이전|모든)\\s*(지시|명령).*?(무시|잊어)"

  # 금지어
  blocked_words:
    - "시발"
    - "병신"

# 출력 가드레일
output:
  max_length: 4000             # 최대 출력 길이
  min_length: 1                # 최소 출력 길이

  # 톤 검증 (한국어 존댓말)
  tone:
    polite_endings:
      - "니다"
      - "세요"
      - "습니다"
    min_polite_ratio: 0.5      # 최소 존댓말 비율

  # 민감 정보 패턴 (출력에서 감지)
  sensitive_patterns:
    - "(sk-[a-zA-Z0-9]{20,})"  # API 키
    - "(traceback|stack\\s*trace)"  # 스택 트레이스

# 정책
policy:
  strict_mode: false           # 엄격 모드 (인젝션 시 차단)
  check_factual: true          # 사실 검증
  check_tone: true             # 톤 검증
```

### PII 패턴 커스터마이징

```yaml
pii_patterns:
  custom_pattern:
    pattern: "(YOUR_REGEX_HERE)"
    mask: "***MASKED***"
    description: "설명"
```

---

## configs/auth.yaml

인증 및 보안 설정입니다.

```yaml
# JWT 설정
jwt:
  secret_key: "change-in-production"  # JWT_SECRET_KEY 환경변수 권장
  algorithm: "HS256"                  # 암호화 알고리즘
  access_token_expire_minutes: 30     # 액세스 토큰 만료 (분)
  refresh_token_expire_days: 7        # 리프레시 토큰 만료 (일)

# 비밀번호 정책
password:
  min_length: 8                       # 최소 길이
  require_uppercase: false            # 대문자 필수
  require_lowercase: false            # 소문자 필수
  require_digit: false                # 숫자 필수
  require_special: false              # 특수문자 필수

# 보안 설정
security:
  max_login_attempts: 5               # 최대 로그인 시도
  lockout_duration_minutes: 15        # 잠금 시간 (분)
  max_sessions_per_user: 5            # 사용자당 최대 세션
```

### 운영 환경 필수 설정

```bash
# 반드시 환경변수로 설정
export JWT_SECRET_KEY="강력한-랜덤-시크릿-키"
```

---

## configs/intents.yaml

의도 분류 설정입니다.

```yaml
# LLM 기반 의도 분류
llm_classification:
  enabled: true                 # LLM 분류 활성화
  fallback_to_keyword: true     # 실패 시 키워드 fallback
  confidence_threshold: "medium"  # low | medium | high
  timeout: 10                   # 타임아웃 (초)
  max_retries: 1                # 재시도 횟수

# 의도 목록
intents:
  order:
    keywords:
      - "주문"
      - "배송"
      - "결제"
    sub_intents:
      - "status"      # 상태 조회
      - "cancel"      # 취소
      - "modify"      # 수정

  claim:
    keywords:
      - "환불"
      - "교환"
      - "반품"
    sub_intents:
      - "request"     # 요청
      - "status"      # 상태

  policy:
    keywords:
      - "정책"
      - "규정"
      - "안내"
```

---

## 설정 로딩 순서

```
1. configs/*.yaml 파일 로드
2. 환경변수로 오버라이드
3. 런타임 설정 적용
```

### 환경변수 오버라이드 규칙

| YAML 키 | 환경변수 |
|---------|----------|
| `llm.provider` | `LLM_PROVIDER` |
| `llm.openai.api_key` | `OPENAI_API_KEY` |
| `llm.anthropic.api_key` | `ANTHROPIC_API_KEY` |
| `llm.google.api_key` | `GOOGLE_API_KEY` |
| `auth.jwt.secret_key` | `JWT_SECRET_KEY` |
| `server.port` | `APP_PORT` |

---

## 환경별 설정 예시

### 개발 환경

```yaml
# configs/app.yaml
app:
  environment: "development"
server:
  reload: true
logging:
  level: "DEBUG"
```

### 운영 환경

```yaml
# configs/app.yaml
app:
  environment: "production"
server:
  reload: false
logging:
  level: "INFO"
  format: "json"

# 환경변수 필수
# JWT_SECRET_KEY=xxx
# OPENAI_API_KEY=xxx (또는 다른 provider)
```

---

## 관련 문서

- [LLM 가이드](llm_guide.md) - LLM Provider 상세 설정
- [배포 가이드](deployment.md) - 환경별 배포 설정
- [운영 가이드](operations.md) - 모니터링 설정
