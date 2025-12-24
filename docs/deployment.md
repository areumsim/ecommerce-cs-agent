# 배포 가이드

Ecommerce Agent 배포 가이드

## 사전 요구사항

- Python 3.10+
- pip 또는 uv 패키지 매니저
- SQLite3
- (선택) Docker
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

### 1. 의존성 설치

```bash
# pip 사용
pip install -r requirements.txt

# 또는 uv 사용
uv pip install -r requirements.txt
```

### 2. 데이터베이스 초기화

```bash
# SQLite 데이터베이스 생성
python scripts/05_migrate_to_sqlite.py
```

### 3. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 또는
python -m uvicorn api:app --reload
```

### 4. 헬스체크

```bash
curl http://localhost:8000/healthz
# {"status": "ok"}
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
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./log:/app/log
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
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
  -v $(pwd)/data:/app/data \
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
After=network.target

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

## 데이터베이스 마이그레이션

### SQLite 초기화

```bash
# 마이그레이션 스크립트 실행
python scripts/05_migrate_to_sqlite.py
```

### 백업

```bash
# SQLite 백업
cp data/ecommerce.db data/ecommerce.db.backup

# 타임스탬프 백업
cp data/ecommerce.db data/ecommerce.db.$(date +%Y%m%d_%H%M%S)
```

## 모니터링

### Prometheus 메트릭

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'ecommerce-agent'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 헬스체크 엔드포인트

| 엔드포인트 | 용도 |
|-----------|------|
| `/healthz` | 간단한 헬스체크 (liveness) |
| `/health` | 상세 헬스체크 (컴포넌트 상태) |
| `/ready` | 준비 상태 (readiness) |
| `/metrics` | Prometheus 메트릭 |

## 로그 관리

### 로그 위치

```
./log/app.log        # 애플리케이션 로그
./log/app.log.1      # 로테이션된 로그
```

### 로그 로테이션

`configs/app.yaml` 설정:

```yaml
logging:
  level: "INFO"
  format: "json"
  file: "./log/app.log"
  rotation:
    max_bytes: 10485760  # 10MB
    backup_count: 5
```

## 보안 체크리스트

- [ ] JWT_SECRET_KEY 설정 (32자 이상)
- [ ] CORS 허용 도메인 제한 (`api.py`에서 수정)
- [ ] HTTPS 적용 (Nginx/로드밸런서)
- [ ] 방화벽 설정 (8000 포트 제한)
- [ ] 로그 모니터링 설정
- [ ] 정기 백업 스케줄링

## 문제 해결

### 서버 시작 실패

```bash
# 포트 사용 중인지 확인
lsof -i :8000

# 로그 확인
tail -f log/app.log
```

### 데이터베이스 오류

```bash
# SQLite 파일 권한 확인
ls -la data/ecommerce.db

# 데이터베이스 무결성 검사
sqlite3 data/ecommerce.db "PRAGMA integrity_check;"
```

### 메모리 부족

```bash
# 워커 수 줄이기
gunicorn api:app --workers 2 ...
```
