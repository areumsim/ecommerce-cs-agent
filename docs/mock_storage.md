# CSV 기반 Mock 저장소 가이드

## 개요
- PoC 단계에서 DB 대신 CSV 파일로 주문/클레임 등 트랜잭션 데이터를 관리합니다.
- 서비스 계층은 저장소 인터페이스에 의존하여, 향후 SQL 저장소로 전환 시 코드 변경을 최소화합니다.

## 파일 경로 및 스키마
- 기본 경로: `data/mock_csv/`
- 스키마(헤더):
  - `users.csv`: `user_id,name,email,created_at,preferences_json`
  - `products_cache.csv`: `product_id,title,brand,category,price,image_url,avg_rating,stock_quantity`
  - `orders.csv`: `order_id,user_id,status,order_date,delivery_date,total_amount,shipping_address,created_at`
  - `order_items.csv`: `id,order_id,product_id,quantity,unit_price`
  - `cart.csv`: `id,user_id,product_id,quantity,added_at`
  - `wishlist.csv`: `id,user_id,product_id,added_at`
  - `support_tickets.csv`: `ticket_id,user_id,order_id,issue_type,description,status,priority,created_at,resolved_at`
  - `conversations.csv`: `id,session_id,user_id,messages_json,created_at,updated_at`

## 동작 원칙
- 인터페이스: `src/mock_system/storage/interfaces.py`
- 구현: `src/mock_system/storage/csv_repository.py`
  - 최초 로드 시 인메모리 캐시 및 인덱스(ID→행 인덱스) 구성
  - 쓰기 시 임시파일(tmp) 작성 후 `os.replace`로 교체(간단한 원자성)
  - JSON 필드는 문자열로 저장(`*_json`), 날짜는 ISO8601 권장
- 제약:
  - 다중 동시 쓰기를 지원하지 않으므로, 단일-라이터 규칙을 지켜주세요.
  - FK 무결성은 애플리케이션 레벨에서 검증합니다(시드 생성 시 교차 확인 권장).

## 전환 계획(SQL)
- 동일 인터페이스를 구현한 `sql_repository.py` 추가
- CSV→DB 마이그레이션 스크립트 작성(무결성/중복 검사)
- 설정 스위치: `configs/mock.yaml`의 `storage_backend`를 `sql`로 전환

## 테스트 팁
- 소량 시드로 E2E 플로우를 빠르게 검증한 후, 점차 데이터를 보강하세요.
- 백업/복구: 필요 시 `data/mock_csv/` 디렉토리 스냅샷으로 관리합니다.

