# ==============================================
# Stage 1: Builder
# ==============================================
FROM python:3.10-slim as builder

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ==============================================
# Stage 2: Production
# ==============================================
FROM python:3.10-slim

WORKDIR /app

# 런타임 의존성만 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 빌더에서 파이썬 패키지 복사
COPY --from=builder /root/.local /root/.local

# 앱 코드 복사
COPY . .

# PATH 설정
ENV PATH=/root/.local/bin:$PATH

# 환경 변수 기본값
ENV APP_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 데이터 디렉토리 생성
RUN mkdir -p /app/data /app/logs

# 포트 노출
EXPOSE 8000
EXPOSE 7860

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# 실행
CMD ["python", "scripts/serve_api.py"]
