# Archived Files

아래 파일들은 더 이상 활발히 사용되지 않거나, 현재 아키텍처(RDF 기반)와 맞지 않아 아카이브되었습니다.

## 이동 날짜
2026-01-16

## 아카이브 사유

### Root
| 파일 | 사유 |
|------|------|
| `TODO.md` | 오래된 진행 상황 추적 파일. AGENTS.md와 README.md로 대체됨 |

### docs/
| 파일 | 크기 | 사유 |
|------|------|------|
| `DATA_FLOW_GUIDE.md` | 88KB | 상세하지만 RDF 이전 아키텍처 기준. 필요시 업데이트 후 복구 |
| `TECHNOLOGY_GUIDE.md` | 395KB | 교육용 문서지만 매우 길고 일부 내용이 구식일 수 있음 |

### scripts/
| 파일 | 사유 |
|------|------|
| `02_preprocess.py` | `02_full_preprocess_stream.py`와 중복 |
| `05_prepare_training.py` | 학습 데이터 준비 - 특수 용도 |
| `06_train_qlora.py` | QLoRA 학습 스크립트 - 특수 용도 |
| `10_generate_qa.py` | QA 데이터셋 생성 - 특수 용도 |
| `10_migrate_to_neo4j.py` | Neo4j 마이그레이션 - RDF로 대체됨 |

### configs/
| 파일 | 사유 |
|------|------|
| `neo4j.yaml` | Neo4j 설정 - RDF로 대체됨 (`configs/rdf.yaml` 사용) |
| `axolotl_config.yaml` | Axolotl 학습 설정 - 특수 용도 |

## 복구 방법

필요한 파일이 있으면 다시 원래 위치로 이동하세요:
```bash
mv _archive/docs/TECHNOLOGY_GUIDE.md docs/
```

## 참고
- 학습(Training) 관련 스크립트는 모델 파인튜닝 시 필요할 수 있음
- TECHNOLOGY_GUIDE.md는 신입 개발자 교육에 유용할 수 있음
