# 운영 가이드

Ecommerce Agent 운영 및 모니터링 가이드

## 모니터링

### 헬스체크 엔드포인트

| 엔드포인트 | 용도 | 응답 예시 |
|-----------|------|----------|
| `/healthz` | Liveness probe | `{"status": "ok"}` |
| `/health` | 상세 컴포넌트 상태 | `{"status": "healthy", "components": {...}}` |
| `/ready` | Readiness probe | `{"status": "ready"}` |
| `/metrics` | Prometheus 메트릭 | Prometheus 형식 |

### Prometheus 메트릭

주요 메트릭:
- `http_requests_total`: 총 HTTP 요청 수
- `http_request_duration_seconds`: 요청 처리 시간
- `agent_requests_total`: 에이전트 요청 수
- `agent_errors_total`: 에이전트 오류 수
- `llm_requests_total`: LLM API 호출 수
- `llm_latency_seconds`: LLM 응답 시간
- `llm_tokens_used_total`: 토큰 사용량
- `db_queries_total`: DB 쿼리 수

Prometheus 설정:
```yaml
scrape_configs:
  - job_name: 'ecommerce-agent'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

설정 파일 위치: `monitoring/prometheus/prometheus.yml`

### Grafana 대시보드

대시보드 파일: `monitoring/grafana/dashboard.json`

대시보드 패널:
- **Overview**: 요청/초, P95 지연, 에러율, 활성 사용자
- **HTTP Metrics**: 엔드포인트별 요청 및 지연
- **Agent Metrics**: 의도별 요청, 응답 시간, 에러
- **LLM Metrics**: 모델별 요청, 지연, 토큰 사용량
- **Database Metrics**: 테이블별 쿼리 및 지연

설정 방법:
```bash
# Docker Compose로 모니터링 스택 실행
docker-compose -f docker-compose.monitoring.yml up -d

# Grafana 접속: http://localhost:3000 (admin/admin)
# 대시보드 Import: monitoring/grafana/dashboard.json
```

### 알림 규칙

알림 파일: `monitoring/prometheus/alerts.yml`

주요 알림:
| 알림 | 조건 | 심각도 |
|------|------|--------|
| ServiceDown | 1분 이상 다운 | critical |
| HighErrorRate | 5xx > 5% | warning |
| HighLatency | P95 > 2초 | warning |
| HighLLMLatency | P95 > 60초 | warning |

### 로깅

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

## 스토리지

### SQLite 데이터베이스 (권장)
- 위치: `data/ecommerce.db`
- 마이그레이션: `python scripts/05_migrate_to_sqlite.py`
- 헬스체크: `/health`에서 DB 상태 확인
- 동시성: WAL 모드로 읽기/쓰기 동시 지원

설정 (`configs/app.yaml`):
```yaml
storage:
  backend: "sqlite"
  sqlite:
    database: "data/ecommerce.db"
    timeout: 30
```

### CSV 스토리지 (레거시)

CSV 파일 기반 스토리지는 동시성 제한이 있습니다.

**단일 라이터 규칙**:
- CSV 파일은 **동시 쓰기를 지원하지 않습니다**
- 단일 프로세스/스레드에서만 쓰기 작업 수행
- 읽기는 여러 프로세스에서 동시 가능

**제한 사항**:
- 다중 워커 환경에서 데이터 손상 가능
- 대용량 데이터에서 성능 저하
- SQLite로 마이그레이션 권장

**마이그레이션**:
```bash
# CSV → SQLite 마이그레이션
python scripts/05_migrate_to_sqlite.py

# 설정 변경
# configs/app.yaml에서 backend: "sqlite"로 변경
```

### 백업
```bash
# 일일 백업 (SQLite)
cp data/ecommerce.db backups/ecommerce.db.$(date +%Y%m%d)

# 일일 백업 (CSV)
tar -czf backups/csv_data.tar.gz data/*.csv

# 인덱스 백업
tar -czf backups/index.tar.gz data/processed/
```

## 보안

### 시크릿 관리
- API 키/토큰은 코드에 포함 금지
- 환경변수 또는 시크릿 매니저 사용
- 노출 시 즉시 폐기/교체

### 필수 환경변수
```bash
JWT_SECRET_KEY=your-secret-key-min-32-chars
OPENAI_API_KEY=sk-xxx
```

## 정기 작업

| 작업 | 주기 | 명령 |
|------|------|------|
| 로그 정리 | 일일 | `find log/ -mtime +30 -delete` |
| 백업 | 일일 | `./backup.sh` |
| 인덱스 재구축 | 주간 | `python scripts/04_build_index.py` |
| 의존성 업데이트 | 월간 | `pip install -U -r requirements.txt` |

## 스케일링

워커 수 조정:
```bash
gunicorn api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

권장: CPU 코어 수 * 2 + 1

## 문제 해결

자세한 내용은 [troubleshooting.md](./troubleshooting.md) 참조.

