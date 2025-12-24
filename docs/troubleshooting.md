# 트러블슈팅 가이드

일반적인 문제와 해결 방법

## 서버 시작 문제

### 포트 이미 사용 중

**증상:**
```
ERROR: [Errno 98] Address already in use
```

**해결:**
```bash
# 포트 사용 프로세스 확인
lsof -i :8000

# 프로세스 종료
kill -9 <PID>

# 또는 다른 포트로 실행
uvicorn api:app --port 8001
```

### 모듈 임포트 오류

**증상:**
```
ModuleNotFoundError: No module named 'src'
```

**해결:**
```bash
# 프로젝트 루트에서 실행 확인
cd /path/to/ar_agent

# PYTHONPATH 설정
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 또는 패키지 재설치
pip install -e .
```

### 의존성 누락

**증상:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**해결:**
```bash
pip install -r requirements.txt
```

---

## 인증 문제

### 토큰 만료

**증상:**
```json
{"detail": "유효하지 않은 토큰입니다"}
```

**해결:**
1. 리프레시 토큰으로 갱신
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token"}'
```

2. 재로그인

### JWT 시크릿 키 오류

**증상:**
```
WARNING: Using default JWT secret key
```

**해결:**
```bash
# 환경변수 설정
export JWT_SECRET_KEY="your-secret-key-at-least-32-characters"
```

### 비밀번호 해싱 오류

**증상:**
```
ValueError: Invalid salt
```

**해결:**
```bash
# bcrypt 재설치
pip uninstall bcrypt passlib
pip install bcrypt passlib
```

---

## 데이터베이스 문제

### SQLite 파일 없음

**증상:**
```json
{"status": "degraded", "components": {"database": {"status": "down", "reason": "file not found"}}}
```

**해결:**
```bash
# 데이터베이스 초기화
python scripts/05_migrate_to_sqlite.py
```

### 데이터베이스 잠금

**증상:**
```
sqlite3.OperationalError: database is locked
```

**해결:**
```bash
# 다른 프로세스 확인
fuser data/ecommerce.db

# 잠금 해제 (주의: 데이터 손실 가능)
rm data/ecommerce.db-journal
```

### 데이터베이스 손상

**증상:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**해결:**
```bash
# 무결성 검사
sqlite3 data/ecommerce.db "PRAGMA integrity_check;"

# 백업에서 복원
cp data/ecommerce.db.backup data/ecommerce.db

# 또는 재초기화
rm data/ecommerce.db
python scripts/05_migrate_to_sqlite.py
```

---

## LLM API 문제

### API 키 오류

**증상:**
```
RuntimeError: OpenAI API 오류: 401 - Unauthorized
```

**해결:**
```bash
# API 키 확인
echo $OPENAI_API_KEY

# 올바른 키 설정
export OPENAI_API_KEY="sk-..."
```

### Rate Limit 초과

**증상:**
```
RuntimeError: OpenAI API 오류: 429 - Rate limit exceeded
```

**해결:**
1. 잠시 대기 후 재시도
2. API 사용량 확인
3. Rate limit 증가 요청

### 타임아웃

**증상:**
```
asyncio.TimeoutError: Connection timeout
```

**해결:**
```yaml
# configs/llm.yaml에서 타임아웃 증가
openai:
  timeout: 60  # 기본 30초 → 60초
```

---

## RAG 검색 문제

### 검색 결과 없음

**증상:**
```json
{"query": "환불", "hits": []}
```

**해결:**
1. 인덱스 확인
```bash
ls -la data/chroma_index/
```

2. 인덱스 재구축
```bash
python scripts/04_build_index.py
```

### ChromaDB 오류

**증상:**
```
chromadb.errors.InvalidCollectionException
```

**해결:**
```bash
# ChromaDB 초기화
rm -rf data/chroma_index/
python scripts/04_build_index.py
```

---

## 메모리 문제

### 메모리 부족

**증상:**
```
MemoryError
```

**해결:**
```bash
# 워커 수 줄이기
gunicorn api:app --workers 1

# 또는 스왑 메모리 추가
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 메모리 누수

**증상:**
- 시간이 지남에 따라 메모리 사용량 증가

**해결:**
```bash
# 주기적 재시작 설정 (systemd)
# WatchdogSec=3600
# Restart=always
```

---

## 로깅 문제

### 로그 파일 없음

**증상:**
- `./log/app.log` 파일이 생성되지 않음

**해결:**
```bash
# 디렉토리 생성
mkdir -p log

# 권한 확인
chmod 755 log
```

### 로그 로테이션 안됨

**증상:**
- 로그 파일이 계속 커짐

**해결:**
```yaml
# configs/app.yaml 확인
logging:
  file: "./log/app.log"
  rotation:
    max_bytes: 10485760
    backup_count: 5
```

---

## 네트워크 문제

### CORS 오류

**증상:**
```
Access to XMLHttpRequest at 'http://localhost:8000' from origin 'http://localhost:3000' has been blocked by CORS policy
```

**해결:**
```python
# api.py에서 CORS 설정 확인
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 허용할 도메인
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 연결 거부

**증상:**
```
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**해결:**
1. 서버 실행 확인
```bash
ps aux | grep uvicorn
```

2. 호스트 바인딩 확인
```bash
# 모든 인터페이스에서 수신
uvicorn api:app --host 0.0.0.0 --port 8000
```

---

## 성능 문제

### 느린 응답

**원인 및 해결:**

1. **LLM API 지연**
   - 타임아웃 설정 조정
   - 캐싱 적용 검토

2. **데이터베이스 쿼리**
   - 인덱스 추가
   - 쿼리 최적화

3. **동시 요청**
   - 워커 수 증가
   - 로드 밸런서 적용

### 높은 CPU 사용량

**해결:**
```bash
# CPU 사용 프로세스 확인
top -H -p $(pgrep -f uvicorn)

# 워커 수 조정
gunicorn api:app --workers 2  # CPU 코어 수에 맞게
```

---

## 디버깅 팁

### 상세 로그 활성화

```bash
export LOG_LEVEL=DEBUG
uvicorn api:app --reload
```

### 요청/응답 로깅

```python
# 미들웨어 추가
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    print(f"Response: {response.status_code}")
    return response
```

### 테스트 실행

```bash
# 특정 테스트만 실행
pytest tests/test_api.py -v

# 실패 시 상세 출력
pytest tests/ -v --tb=long
```

---

## 도움 요청

문제가 해결되지 않으면:

1. 로그 파일 수집 (`./log/app.log`)
2. 환경 정보 수집 (`pip freeze`, Python 버전)
3. 재현 단계 정리
4. GitHub Issues에 보고
