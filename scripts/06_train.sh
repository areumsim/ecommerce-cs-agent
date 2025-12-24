#!/bin/bash
# Axolotl QLoRA 파인튜닝 스크립트
# 한국어 전자상거래 고객 상담 에이전트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  E-commerce Agent QLoRA Fine-tuning${NC}"
echo -e "${GREEN}========================================${NC}"

# 프로젝트 루트로 이동
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 환경 확인
echo -e "\n${YELLOW}[1/5] 환경 확인${NC}"

# GPU 확인
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}Error: NVIDIA GPU가 필요합니다.${NC}"
    exit 1
fi

echo "GPU 정보:"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv

# CUDA 버전 확인
echo -e "\nCUDA 버전:"
nvcc --version 2>/dev/null || echo "nvcc not found (CUDA toolkit not installed)"

# Axolotl 설치 확인
echo -e "\n${YELLOW}[2/5] Axolotl 설치 확인${NC}"
if ! python -c "import axolotl" 2>/dev/null; then
    echo -e "${YELLOW}Axolotl이 설치되어 있지 않습니다. 설치를 시작합니다...${NC}"
    pip install axolotl
    pip install flash-attn --no-build-isolation 2>/dev/null || echo "Flash Attention 설치 실패 (선택사항)"
fi

# 데이터 확인
echo -e "\n${YELLOW}[3/5] 학습 데이터 확인${NC}"
TRAINING_DIR="$PROJECT_ROOT/data/training"

if [ ! -d "$TRAINING_DIR" ]; then
    echo -e "${RED}Error: 학습 데이터 디렉토리가 없습니다: $TRAINING_DIR${NC}"
    exit 1
fi

echo "학습 데이터 파일:"
for f in "$TRAINING_DIR"/*.jsonl; do
    if [ -f "$f" ]; then
        lines=$(wc -l < "$f")
        echo "  - $(basename "$f"): $lines 샘플"
    fi
done

TOTAL_SAMPLES=$(cat "$TRAINING_DIR"/*.jsonl 2>/dev/null | wc -l)
echo -e "\n총 학습 샘플: ${GREEN}$TOTAL_SAMPLES${NC}개"

if [ "$TOTAL_SAMPLES" -lt 50 ]; then
    echo -e "${YELLOW}Warning: 학습 샘플이 50개 미만입니다. 결과가 좋지 않을 수 있습니다.${NC}"
fi

# 설정 파일 확인
echo -e "\n${YELLOW}[4/5] 설정 파일 확인${NC}"
CONFIG_FILE="$PROJECT_ROOT/configs/axolotl_config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: 설정 파일이 없습니다: $CONFIG_FILE${NC}"
    exit 1
fi

echo "설정 파일: $CONFIG_FILE"

# 출력 디렉토리 생성
OUTPUT_DIR="$PROJECT_ROOT/outputs/ecommerce-agent-qlora"
mkdir -p "$OUTPUT_DIR"
echo "출력 디렉토리: $OUTPUT_DIR"

# 학습 시작
echo -e "\n${YELLOW}[5/5] 학습 시작${NC}"
echo -e "${GREEN}========================================${NC}"

# GPU 설정 (사용자가 지정한 GPU)
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0,1,2,3}
NUM_GPUS=$(echo $CUDA_VISIBLE_DEVICES | tr ',' '\n' | wc -l)
echo "사용 GPU: $CUDA_VISIBLE_DEVICES (${NUM_GPUS}개)"

# CUDA 메모리 최적화 환경 변수
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# 멀티 GPU 학습 (accelerate 사용)
if [ "$NUM_GPUS" -gt 1 ]; then
    echo "멀티 GPU 학습 모드 (${NUM_GPUS} GPUs)"
    accelerate launch --multi_gpu --num_processes=$NUM_GPUS -m axolotl.cli.train "$CONFIG_FILE"
else
    echo "싱글 GPU 학습 모드"
    python -m axolotl.cli.train "$CONFIG_FILE"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  학습 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "모델 저장 위치: $OUTPUT_DIR"
echo -e "\n다음 단계:"
echo -e "  1. 모델 병합: bash scripts/07_merge_lora.sh"
echo -e "  2. 모델 테스트: python scripts/08_test_model.py"
