#!/usr/bin/env python3
"""파인튜닝된 모델 테스트 스크립트."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))


def load_model(model_path: str, use_4bit: bool = True):
    """모델 로드."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print(f"모델 로드 중: {model_path}")

    if use_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=quantization_config,
            device_map="auto",
            trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    return model, tokenizer


def generate_response(
    model,
    tokenizer,
    instruction: str,
    user_input: str,
    max_new_tokens: int = 256,
    temperature: float = 0.7,
) -> str:
    """응답 생성."""
    # Alpaca 프롬프트 형식
    prompt = f"""### Instruction:
{instruction}

### Input:
{user_input}

### Response:
"""

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=0.9,
        do_sample=True,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Response 부분만 추출
    if "### Response:" in response:
        response = response.split("### Response:")[-1].strip()

    return response


def run_tests(model, tokenizer):
    """테스트 케이스 실행."""
    test_cases = [
        ("고객 문의에 답변하세요.", "환불 정책이 어떻게 되나요?"),
        ("고객 문의에 답변하세요.", "배송은 얼마나 걸려요?"),
        ("고객 문의에 답변하세요.", "주문 취소하고 싶어요"),
        ("고객 문의에 답변하세요.", "불량 상품을 받았어요"),
        ("고객 문의에 답변하세요.", "포인트는 언제 적립되나요?"),
        ("고객 문의에 답변하세요.", "클레임 접수하고 싶어요"),
    ]

    print("\n" + "=" * 60)
    print("파인튜닝 모델 테스트")
    print("=" * 60)

    for instruction, user_input in test_cases:
        print(f"\n[질문] {user_input}")
        response = generate_response(model, tokenizer, instruction, user_input)
        print(f"[응답] {response}")
        print("-" * 40)


def interactive_mode(model, tokenizer):
    """대화형 모드."""
    print("\n" + "=" * 60)
    print("대화형 모드 (종료: 'quit' 또는 'exit')")
    print("=" * 60)

    instruction = "고객 문의에 답변하세요."

    while True:
        try:
            user_input = input("\n[질문] ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("종료합니다.")
                break
            if not user_input:
                continue

            response = generate_response(model, tokenizer, instruction, user_input)
            print(f"[응답] {response}")

        except KeyboardInterrupt:
            print("\n종료합니다.")
            break


def main():
    parser = argparse.ArgumentParser(description="파인튜닝 모델 테스트")
    parser.add_argument(
        "--model-path",
        type=str,
        default="outputs/ecommerce-agent-merged",
        help="모델 경로",
    )
    parser.add_argument(
        "--lora-path",
        type=str,
        help="LoRA 어댑터 경로 (병합된 모델 대신 사용)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="대화형 모드",
    )
    parser.add_argument(
        "--no-4bit",
        action="store_true",
        help="4bit 양자화 비활성화",
    )
    args = parser.parse_args()

    # 모델 로드
    model_path = args.model_path
    if args.lora_path:
        # LoRA 어댑터 사용
        from peft import PeftModel

        base_model, tokenizer = load_model(
            "beomi/Llama-3-Open-Ko-8B",
            use_4bit=not args.no_4bit,
        )
        model = PeftModel.from_pretrained(base_model, args.lora_path)
    else:
        model, tokenizer = load_model(model_path, use_4bit=not args.no_4bit)

    # 테스트 실행
    if args.interactive:
        interactive_mode(model, tokenizer)
    else:
        run_tests(model, tokenizer)


if __name__ == "__main__":
    main()
