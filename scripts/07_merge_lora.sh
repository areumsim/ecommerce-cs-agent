#!/bin/bash
# LoRA 어댑터를 기본 모델에 병합하는 스크립트

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  LoRA Adapter Merge${NC}"
echo -e "${GREEN}========================================${NC}"

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 경로 설정
BASE_MODEL="beomi/Llama-3-Open-Ko-8B"
LORA_PATH="$PROJECT_ROOT/outputs/ecommerce-agent-qlora"
OUTPUT_PATH="$PROJECT_ROOT/outputs/ecommerce-agent-merged"

echo -e "\n${YELLOW}설정:${NC}"
echo "  기본 모델: $BASE_MODEL"
echo "  LoRA 경로: $LORA_PATH"
echo "  출력 경로: $OUTPUT_PATH"

# LoRA 어댑터 확인
if [ ! -d "$LORA_PATH" ]; then
    echo -e "${YELLOW}Error: LoRA 어댑터가 없습니다. 먼저 학습을 실행하세요.${NC}"
    exit 1
fi

# 출력 디렉토리 생성
mkdir -p "$OUTPUT_PATH"

# 병합 실행
echo -e "\n${YELLOW}LoRA 어댑터 병합 중...${NC}"

python << 'EOF'
import os
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

# 경로 설정
base_model_name = "beomi/Llama-3-Open-Ko-8B"
lora_path = os.environ.get("LORA_PATH", "outputs/ecommerce-agent-qlora")
output_path = os.environ.get("OUTPUT_PATH", "outputs/ecommerce-agent-merged")

print(f"기본 모델 로드: {base_model_name}")
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True,
)

tokenizer = AutoTokenizer.from_pretrained(base_model_name)

print(f"LoRA 어댑터 로드: {lora_path}")
model = PeftModel.from_pretrained(base_model, lora_path)

print("모델 병합 중...")
model = model.merge_and_unload()

print(f"병합된 모델 저장: {output_path}")
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)

print("완료!")
EOF

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  병합 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "병합된 모델: $OUTPUT_PATH"
