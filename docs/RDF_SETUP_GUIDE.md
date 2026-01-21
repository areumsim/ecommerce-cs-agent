# RDF/Fuseki 설정 가이드

이 문서는 Apache Jena Fuseki 트리플 스토어를 설정하고 데이터를 로드하는 방법을 설명합니다.

## 전제 조건

- Docker 설치됨
- 프로젝트 디렉토리: `/workspace/arsim/ecommerce-cs-agent`
- 네트워크: `ar-poc-network` (컨테이너 간 통신용)

## 1. Fuseki 컨테이너 실행

```bash
docker run -d --name ar_fuseki \
  -p 31010:3030 \
  -e ADMIN_PASSWORD=admin123 \
  -v /home/user/arsim/ecommerce-cs-agent/ontology:/staging:ro \
  --network ar-poc-network \
  stain/jena-fuseki:4.10.0
```

### 포트 정보
- **31010**: 외부 접근 포트
- **3030**: 컨테이너 내부 포트
- **관리 UI**: `http://localhost:31010`
- **인증**: admin / admin123

## 2. 데이터셋 생성

Fuseki 관리 UI (`http://localhost:31010`) 또는 API로 데이터셋 생성:

```bash
curl -X POST 'http://ar_fuseki:3030/$/datasets' \
  -u admin:admin123 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'dbType=tdb2&dbName=ecommerce'
```

## 3. 데이터 로드

### 방법 A: 전체 데이터 한 번에 로드

```bash
cd /workspace/arsim/ecommerce-cs-agent

for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  echo "Loading $f..."
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

### 방법 B: 개별 파일 로드

```bash
# 온톨로지 스키마
curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Content-Type: text/turtle' \
  --data-binary @ontology/ecommerce.ttl

# SHACL 규칙
curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Content-Type: text/turtle' \
  --data-binary @ontology/shacl/ecommerce-shapes.ttl

# 인스턴스 데이터
for f in customers products orders tickets similarities embeddings; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @ontology/instances/${f}.ttl
done
```

## 4. 데이터 확인

### 트리플 수 확인
```bash
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }' \
  -H 'Accept: application/json'
```

### 엔티티 타입별 개수
```bash
curl -s -G 'http://ar_fuseki:3030/ecommerce/sparql' \
  --data-urlencode 'query=
    SELECT ?type (COUNT(?s) as ?count)
    WHERE { ?s a ?type }
    GROUP BY ?type
    ORDER BY DESC(?count)
  ' \
  -H 'Accept: application/json'
```

## 5. 애플리케이션 설정

### configs/rdf.yaml
```yaml
rdf:
  backend: "fuseki"
fuseki:
  endpoint: "http://ar_fuseki:3030/ecommerce"
  user: "admin"
  password: "admin123"
```

## 6. 데이터 재생성

CSV 데이터가 변경된 경우:

```bash
# 1. TTL 파일 재생성
python scripts/12_generate_mock_ttl.py --limit 0

# 2. Fuseki 데이터셋 초기화
curl -X DELETE 'http://ar_fuseki:3030/$/datasets/ecommerce' -u admin:admin123
curl -X POST 'http://ar_fuseki:3030/$/datasets' \
  -u admin:admin123 \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'dbType=tdb2&dbName=ecommerce'

# 3. 데이터 다시 로드
for f in ontology/ecommerce.ttl ontology/shacl/*.ttl ontology/instances/*.ttl; do
  curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
    -u admin:admin123 \
    -H 'Content-Type: text/turtle' \
    --data-binary @"$f"
done
```

## 7. 예상 데이터 수량

| 파일 | 트리플 수 | 내용 |
|------|----------|------|
| ecommerce.ttl | 174 | 온톨로지 스키마 |
| ecommerce-shapes.ttl | 208 | SHACL 검증 규칙 |
| customers.ttl | 800 | 100명 고객 |
| products.ttl | 13,428 | 1,492개 상품 |
| orders.ttl | 11,134 | 491개 주문 + 1,240개 주문 항목 |
| tickets.ttl | 1,895 | 60개 티켓 |
| similarities.ttl | 4,416 | 상품 유사도 관계 |
| embeddings.ttl | 200 | 100개 상품 벡터 임베딩 |
| **총계** | **~32,255** | - |

## 8. 트러블슈팅

### Fuseki 연결 실패
```bash
# 컨테이너 상태 확인
docker ps | grep fuseki

# 로그 확인
docker logs ar_fuseki

# 네트워크 확인
docker network inspect ar-poc-network
```

### 데이터 로드 실패
```bash
# TTL 문법 검증
rapper -i turtle -c ontology/instances/products.ttl
```

### 메모리 부족
```bash
# Fuseki 메모리 증가
docker run -d --name ar_fuseki \
  -e JVM_ARGS="-Xmx4g" \
  ... (other options)
```

## 9. 백업 및 복원

### 백업
```bash
curl -o backup.nq 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Accept: application/n-quads'
```

### 복원
```bash
# 데이터셋 초기화 후
curl -X POST 'http://ar_fuseki:3030/ecommerce/data' \
  -u admin:admin123 \
  -H 'Content-Type: application/n-quads' \
  --data-binary @backup.nq
```

## 10. 참고

- **Fuseki 문서**: https://jena.apache.org/documentation/fuseki2/
- **SPARQL 참조**: https://www.w3.org/TR/sparql11-query/
- **SHACL 참조**: https://www.w3.org/TR/shacl/
