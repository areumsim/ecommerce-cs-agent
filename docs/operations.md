# 운영 및 배포 가이드

Ecommerce Agent의 설치, 배포, 운영에 대한 통합 문서입니다.

**최종 업데이트**: 2026-01-19
**데이터 저장소**: Apache Jena Fuseki (RDF Triple Store)

---

## 목차

1. [빠른 시작](#빠른-시작)
2. [포트 및 요청 흐름](#포트-및-요청-흐름)
3. [배포 가이드](#배포-가이드)
4. [모니터링](#모니터링)
5. [스토리지](#스토리지)
6. [보안](#보안)
7. [문제 해결](#문제-해결)

---

# 빠른 시작

## 1) Fuseki 실행

```bash
# Docker로 Fuseki 실행
docker run -d --name ar_fuseki \
  -p 31010:3030 \
  -e ADMIN_PASSWORD=admin123 \
  --network ar-poc-network \
  stain/jena-fuseki:4.10.0

# 데이터셋 생성
curl -X POST 'http://ar_fuseki:3030/$/datasets' \
  -u admin:admin123 \
  -d 'dbType=tdb2&dbName=ecommerce'
```

## 2) 의존성 설치

```bash
pip install -r requirements.txt
```

## 3) 데이터 로드

```bash
# 온톨로지 + 인스턴스 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

## 4) 트리플 수 확인

```bash
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'
# 예상 결과: ~32,000 트리플
```

## 5) API/UI 실행

```bash
uvicorn api:app --reload     # API (port 8000)
python ui.py                  # UI (port 7860)
```

## 6) 헬스체크

```bash
curl http://localhost:8000/health
# {"status": "healthy", "backend": "fuseki", "triple_count": 32000, ...}
```

## 7) UI 탭 구성

Gradio UI (`http://localhost:7860`)의 주요 탭:

| 탭 | 기능 |
|----|------|
| 💬 고객 상담 | 대화형 CS 인터페이스 |
| 🔧 관리자 | 고객/주문/티켓 관리, 통계 |
| 📊 데이터-지식그래프 | RDF 시각화 (스키마, 인스턴스, 유사도) |
| 🔧 RDF 데이터 | SPARQL 쿼리, 트리플 관리, 엔티티 브라우저 |

**🔧 RDF 데이터 탭 기능:**
- **📝 SPARQL 쿼리**: SELECT 쿼리 실행, 예시 쿼리 버튼 제공
- **➕ 트리플 관리**: 트리플 추가/삭제 (URI 접두사 `ecom:` 지원)
- **🔍 엔티티 브라우저**: Customer, Product, Order, Ticket 조회

---

# 포트 및 요청 흐름

## 포트 요약

| 서비스 | 기본 포트 | 설정 위치 |
|--------|----------|-----------|
| API (FastAPI) | 8000 | `configs/app.yaml` → `server.port` |
| UI (Gradio) | 7860 | `configs/app.yaml` → `server.ui_port` |
| **Fuseki (SPARQL)** | 3030 (내부), 31010 (외부) | `docker run -p` |
| Prometheus | 9090 | `docker-compose.yml` |
| Grafana | 3000 | `docker-compose.yml` |
| Local LLM (vLLM) | 8080 | (선택) |

## 환경변수 오버라이드

```bash
# API
APP_HOST=0.0.0.0
APP_PORT=8000

# UI
UI_HOST=0.0.0.0
UI_PORT=7860
```

## 시작/중지

```bash
# 시작 (로컬)
python scripts/serve_api.py   # API
python ui.py                   # UI

# 시작 (Docker Compose)
docker-compose up -d
APP_PORT=9000 UI_PORT=7000 docker-compose up -d

# 중지
pkill -f "uvicorn api:app" || true
pkill -f "python ui.py" || true
```

## 포트 포워딩

```bash
# SSH
ssh -L 8000:localhost:8000 -L 7860:localhost:7860 -L 31010:localhost:31010 <user>@<host>

# Docker
docker run -p 8000:8000 -p 7860:7860 -p 31010:31010 ...

# Codespaces/Remote IDE
# 포트 8000, 7860, 31010 포워딩 설정
```

## 요청 흐름

```
Browser ─── HTTP 8000 ──→ API (FastAPI)
   │                         │
   └─── HTTP 7860 ──→ UI (Gradio) ─── HTTP 8000 ──→ API
                                                      │
                                          ┌───────────┼───────────┐
                                          ▼           ▼           ▼
                                     RDF Repo      RAG Index   vLLM (8080)
                                          │
                                          ▼ SPARQL over HTTP
                                     Fuseki (3030)
```

## Chat 파이프라인

```
Browser/UI
    │
    ▼ POST /chat {user_id, message}
   API
    │
    ▼ classify_intent(message)
Classifier (LLM/Keyword)
    │
    ▼ intent, sub_intent, payload
Orchestrator
    │
    ├─ order → order_tools (list/detail/status/cancel) → RDF Repository
    ├─ claim → ticket service → RDF Repository
    └─ policy → retriever.search(query) → RAG Index
    │
    ▼ (LLM enabled)
LLM: generate_response(context)
    │
    ▼
API → 200 JSON
```

---

# 배포 가이드

## 사전 요구사항

- Python 3.10+
- pip 또는 uv 패키지 매니저
- Docker (Fuseki 실행)
- (선택) NVIDIA GPU + CUDA (LLM 로컬 실행 시)

## 환경변수

### 필수 환경변수

```bash
# LLM 프로바이더 설정
LLM_PROVIDER=openai          # openai | anthropic | local
OPENAI_API_KEY=sk-xxx        # OpenAI API 키

# JWT 설정 (프로덕션 필수)
JWT_SECRET_KEY=your-secret-key-min-32-chars

# 환경 설정
APP_ENV=production           # development | staging | production
```

### 선택 환경변수

```bash
# 서버 설정
APP_HOST=0.0.0.0
APP_PORT=8000

# 로깅
LOG_LEVEL=INFO               # DEBUG | INFO | WARNING | ERROR

# Anthropic (선택)
ANTHROPIC_API_KEY=sk-ant-xxx
```

## 로컬 개발 환경

### 1. Fuseki 실행

```bash
docker run -d --name ar_fuseki \
  -p 31010:3030 \
  -e ADMIN_PASSWORD=admin123 \
  --network ar-poc-network \
  stain/jena-fuseki:4.10.0
```

### 2. 의존성 설치

```bash
# pip 사용
pip install -r requirements.txt

# 또는 uv 사용
uv pip install -r requirements.txt
```

### 3. 데이터 로드

```bash
# 데이터셋 생성
curl -X POST 'http://localhost:31010/$/datasets' \
  -u admin:admin123 \
  -d 'dbType=tdb2&dbName=ecommerce'

# 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://localhost:31010/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 4. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 또는
python -m uvicorn api:app --reload
```

## Docker 배포

### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 실행
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  fuseki:
    image: stain/jena-fuseki:4.10.0
    ports:
      - "31010:3030"
    environment:
      - ADMIN_PASSWORD=admin123
    volumes:
      - fuseki_data:/fuseki
    networks:
      - app-network

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - fuseki
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  fuseki_data:

networks:
  app-network:
```

### 빌드 및 실행

```bash
# 빌드
docker build -t ecommerce-agent .

# 실행
docker run -d \
  -p 8000:8000 \
  -e JWT_SECRET_KEY=your-secret-key \
  -e OPENAI_API_KEY=sk-xxx \
  ecommerce-agent

# Docker Compose
docker compose up -d
```

## 프로덕션 배포

### 1. Gunicorn 설정

```bash
# gunicorn 설치
pip install gunicorn

# 실행
gunicorn api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### 2. Systemd 서비스

```ini
# /etc/systemd/system/ecommerce-agent.service
[Unit]
Description=Ecommerce Agent API
After=network.target docker.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ecommerce-agent
Environment=APP_ENV=production
Environment=JWT_SECRET_KEY=your-secret-key
ExecStart=/opt/ecommerce-agent/venv/bin/gunicorn api:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable ecommerce-agent
sudo systemctl start ecommerce-agent
```

### 3. Nginx 리버스 프록시

```nginx
# /etc/nginx/sites-available/ecommerce-agent
upstream ecommerce_agent {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://ecommerce_agent;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

# 모니터링

## 헬스체크 엔드포인트

| 엔드포인트 | 용도 | 응답 예시 |
|-----------|------|----------|
| `/healthz` | Liveness probe | `{"status": "ok"}` |
| `/health` | 상세 컴포넌트 상태 | `{"status": "healthy", "backend": "fuseki", "triple_count": 32000}` |
| `/ready` | Readiness probe | `{"status": "ready", "triple_count": 32000}` |
| `/metrics` | Prometheus 메트릭 | Prometheus 형식 |

## Prometheus 메트릭

주요 메트릭:
- `http_requests_total`: 총 HTTP 요청 수
- `http_request_duration_seconds`: 요청 처리 시간
- `agent_requests_total`: 에이전트 요청 수
- `agent_errors_total`: 에이전트 오류 수
- `llm_requests_total`: LLM API 호출 수
- `llm_latency_seconds`: LLM 응답 시간
- `llm_tokens_used_total`: 토큰 사용량
- `sparql_queries_total`: SPARQL 쿼리 수

Prometheus 설정:
```yaml
scrape_configs:
  - job_name: 'ecommerce-agent'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

설정 파일 위치: `monitoring/prometheus/prometheus.yml`

## Grafana 대시보드

대시보드 파일: `monitoring/grafana/dashboard.json`

대시보드 패널:
- **Overview**: 요청/초, P95 지연, 에러율, 활성 사용자
- **HTTP Metrics**: 엔드포인트별 요청 및 지연
- **Agent Metrics**: 의도별 요청, 응답 시간, 에러
- **LLM Metrics**: 모델별 요청, 지연, 토큰 사용량
- **SPARQL Metrics**: 쿼리 지연, 트리플 수

설정 방법:
```bash
# Docker Compose로 모니터링 스택 실행
docker-compose -f docker-compose.monitoring.yml up -d

# Grafana 접속: http://localhost:3000 (admin/admin)
# 대시보드 Import: monitoring/grafana/dashboard.json
```

## 알림 규칙

알림 파일: `monitoring/prometheus/alerts.yml`

| 알림 | 조건 | 심각도 |
|------|------|--------|
| ServiceDown | 1분 이상 다운 | critical |
| FusekiDown | Fuseki 연결 실패 | critical |
| HighErrorRate | 5xx > 5% | warning |
| HighLatency | P95 > 2초 | warning |
| HighLLMLatency | P95 > 60초 | warning |

## 로깅

로그 위치: `./log/app.log`

JSON 형식 로그:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "message": "요청 처리 완료",
  "request_id": "abc123",
  "user_id": "user_001"
}
```

로그 조회:
```bash
# 실시간 모니터링
tail -f log/app.log | jq .

# 에러만 필터링
cat log/app.log | jq 'select(.level == "ERROR")'
```

로그 로테이션 설정 (`configs/app.yaml`):
```yaml
logging:
  level: "INFO"
  format: "json"
  file: "./log/app.log"
  rotation:
    max_bytes: 10485760  # 10MB
    backup_count: 5
```

---

# 스토리지

## Apache Jena Fuseki (Primary Data Store)

> **현재 상태**: UI + API 모두 Fuseki 단일 백엔드 사용

| 항목 | 값 |
|------|-----|
| **백엔드** | Apache Jena Fuseki 4.10.0 |
| **데이터셋** | `/ecommerce` (TDB2) |
| **엔드포인트** | `http://ar_fuseki:3030/ecommerce` |
| **인증** | admin / admin123 |
| **트리플 수** | ~32,000 |

### 설정

```yaml
# configs/rdf.yaml
rdf:
  backend: "fuseki"  # fuseki | rdflib
fuseki:
  endpoint: "http://ar_fuseki:3030/ecommerce"
  user: "admin"
  password: "admin123"
```

### Fuseki 관리

```bash
# 상태 확인
curl -s http://ar_fuseki:3030/$/ping

# 트리플 수 확인
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'

# 엔티티별 개수
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT ?type (COUNT(?s) as ?count) WHERE { ?s a ?type } GROUP BY ?type ORDER BY DESC(?count)'

# 데이터셋 삭제 (주의!)
curl -X DELETE 'http://ar_fuseki:3030/$/datasets/ecommerce' -u admin:admin123

# 데이터셋 재생성
curl -X POST 'http://ar_fuseki:3030/$/datasets' \
  -u admin:admin123 \
  -d 'dbType=tdb2&dbName=ecommerce'
```

### 데이터 재로드

```bash
# 1. TTL 재생성 (필요 시)
python scripts/12_generate_mock_ttl.py

# 2. 전체 데이터 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 백업

```bash
# N-Quads 형식으로 백업
curl -o backup.nq 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Accept: application/n-quads'

# Turtle 형식으로 백업
curl -o backup.ttl 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Accept: text/turtle'

# 일일 백업 스크립트
DATE=$(date +%Y%m%d)
curl -o backups/fuseki_$DATE.nq 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Accept: application/n-quads'
```

### 복원

```bash
# 백업에서 복원
curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Content-Type: application/n-quads' \
  --data-binary @backup.nq
```

## RAG Index (정책 검색)

| 항목 | 값 |
|------|-----|
| **위치** | `data/processed/` |
| **파일** | `policies_index.jsonl`, `policies_vectors.faiss` |
| **문서 수** | 63개 |

### 인덱스 재구축

```bash
python scripts/04_build_index.py
```

## 레거시 스토리지 (미사용)

> **주의**: 다음 스토리지는 더 이상 사용되지 않습니다. Fuseki로 마이그레이션 완료.

| 스토리지 | 상태 | 비고 |
|---------|------|------|
| SQLite (`data/ecommerce.db`) | ❌ 미사용 | Fuseki로 대체 |
| CSV (`data/mock_csv/`) | ❌ 미사용 | TTL로 대체 |
| NetworkX | ❌ 미사용 | RDF로 대체 |

---

# 보안

## 시크릿 관리

- API 키/토큰은 코드에 포함 금지
- 환경변수 또는 시크릿 매니저 사용
- 노출 시 즉시 폐기/교체

## 필수 환경변수

```bash
JWT_SECRET_KEY=your-secret-key-min-32-chars
OPENAI_API_KEY=sk-xxx
```

## Fuseki 보안

```bash
# 프로덕션에서 기본 비밀번호 변경
ADMIN_PASSWORD=your-strong-password

# 네트워크 격리
# Fuseki는 내부 네트워크에서만 접근 가능하도록 설정
docker network create --internal fuseki-internal
```

## 보안 체크리스트

- [ ] JWT_SECRET_KEY 설정 (32자 이상)
- [ ] Fuseki 관리자 비밀번호 변경
- [ ] CORS 허용 도메인 제한 (`api.py`에서 수정)
- [ ] HTTPS 적용 (Nginx/로드밸런서)
- [ ] 방화벽 설정 (8000, 31010 포트 제한)
- [ ] Fuseki 외부 접근 차단 (내부 네트워크만)
- [ ] 로그 모니터링 설정
- [ ] 정기 백업 스케줄링

---

# 정기 작업

| 작업 | 주기 | 명령 |
|------|------|------|
| 로그 정리 | 일일 | `find log/ -mtime +30 -delete` |
| Fuseki 백업 | 일일 | `./scripts/backup_fuseki.sh` |
| 인덱스 재구축 | 주간 | `python scripts/04_build_index.py` |
| 의존성 업데이트 | 월간 | `pip install -U -r requirements.txt` |

---

# 스케일링

워커 수 조정:
```bash
gunicorn api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

권장: CPU 코어 수 * 2 + 1

Fuseki 스케일링:
- TDB2는 단일 인스턴스 권장 (동시성 지원)
- 대규모 환경에서는 Fuseki 클러스터 또는 Virtuoso 고려

---

# 문제 해결

## 서버 시작 실패

```bash
# 포트 사용 중인지 확인
lsof -i :8000

# 로그 확인
tail -f log/app.log
```

## Fuseki 연결 실패

```bash
# Fuseki 상태 확인
curl -s http://ar_fuseki:3030/$/ping

# Docker 컨테이너 상태
docker ps | grep fuseki

# 컨테이너 로그
docker logs ar_fuseki

# 네트워크 확인
docker network inspect ar-poc-network
```

## 트리플 수 0 (데이터 없음)

```bash
# 데이터 로드 확인
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }'

# 데이터 재로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

## 메모리 부족

```bash
# 워커 수 줄이기
gunicorn api:app --workers 2 ...

# Fuseki 메모리 설정
docker run -d --name ar_fuseki \
  -e JVM_ARGS="-Xmx2g" \
  ...
```

## 포트 사용 중

```bash
# 기존 서비스 종료 또는 대체 포트 사용
kill $(lsof -t -i:8000)
# 또는
APP_PORT=9000 python scripts/serve_api.py
```

## UI 표시 안됨

```bash
# UI 로그 확인
tail -f logs/ui.log

# UI 포트 포워딩 확인
curl http://localhost:7860
```

## LLM 경로 문제

```bash
# vLLM 상태 확인
curl http://localhost:8080/v1/models

# Provider 키 확인
echo $OPENAI_API_KEY
```

## SPARQL 쿼리 에러

```bash
# 쿼리 직접 테스트
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT * WHERE { ?s ?p ?o } LIMIT 10'

# 로그에서 SPARQL 에러 확인
grep -i "sparql" log/app.log | tail -20
```

## 일반 트러블슈팅

- Fuseki 연결 실패 → Docker 네트워크 확인, 엔드포인트 URL 확인
- 트리플 0개 → 데이터 로드 명령 재실행
- SPARQL 타임아웃 → 쿼리 최적화, LIMIT 추가
- src 모듈 임포트 실패 → PYTHONPATH=. 또는 스크립트 경로 보강 적용

자세한 내용은 [troubleshooting.md](./troubleshooting.md) 참조.
