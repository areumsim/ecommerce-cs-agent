# 모니터링 설정

Prometheus + Grafana 기반 모니터링 설정입니다.

## 디렉토리 구조

```
monitoring/
├── grafana/
│   └── dashboard.json    # Grafana 대시보드 JSON
├── prometheus/
│   ├── prometheus.yml    # Prometheus 설정
│   └── alerts.yml        # 알림 규칙
└── README.md
```

## 빠른 시작 (Docker Compose)

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  prometheus_data:
  grafana_data:
```

실행:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

## Grafana 대시보드 가져오기

1. Grafana 접속: http://localhost:3000 (admin/admin)
2. Data Sources → Add Prometheus → URL: http://prometheus:9090
3. Dashboards → Import → Upload JSON → `monitoring/grafana/dashboard.json`

## 주요 메트릭

### HTTP 메트릭
- `http_requests_total`: 총 HTTP 요청 수
- `http_request_duration_seconds`: 요청 처리 시간

### 에이전트 메트릭
- `agent_requests_total`: 에이전트 요청 수
- `agent_response_time_seconds`: 에이전트 응답 시간
- `agent_errors_total`: 에이전트 에러 수

### LLM 메트릭
- `llm_requests_total`: LLM API 호출 수
- `llm_latency_seconds`: LLM 응답 시간
- `llm_tokens_used_total`: 토큰 사용량

### 데이터베이스 메트릭
- `db_queries_total`: DB 쿼리 수
- `db_query_duration_seconds`: 쿼리 처리 시간

## 알림 규칙

| 알림 | 조건 | 심각도 |
|------|------|--------|
| ServiceDown | 서비스 1분 이상 다운 | critical |
| HighErrorRate | 5xx 에러율 > 5% | warning |
| HighLatency | P95 > 2초 | warning |
| HighAgentResponseTime | P95 > 30초 | warning |
| HighLLMLatency | P95 > 60초 | warning |
| HighTokenUsage | 시간당 > 100K 토큰 | warning |

## 커스터마이징

### 새 알림 추가
`monitoring/prometheus/alerts.yml`에 규칙 추가:
```yaml
- alert: CustomAlert
  expr: your_metric > threshold
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "알림 제목"
    description: "알림 설명"
```

### 대시보드 수정
1. Grafana에서 대시보드 수정
2. Share → Export → Save to file
3. `monitoring/grafana/dashboard.json` 업데이트
