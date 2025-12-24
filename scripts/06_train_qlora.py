#!/usr/bin/env python3
"""QLoRA 파인튜닝 스크립트 (HuggingFace Trainer 사용)."""

import json
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)


def load_training_data(data_dir: str) -> list:
    """학습 데이터 로드 (Alpaca 형식)."""
    data = []
    data_path = Path(data_dir)

    for jsonl_file in data_path.glob("*.jsonl"):
        print(f"Loading: {jsonl_file}")
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line.strip())
                # Alpaca 형식
                if "instruction" in item:
                    text = f"### Instruction:\n{item['instruction']}\n\n"
                    if item.get("input"):
                        text += f"### Input:\n{item['input']}\n\n"
                    text += f"### Response:\n{item['output']}"
                    data.append({"text": text})
                # ShareGPT/Chat 형식
                elif "messages" in item:
                    messages = item["messages"]
                    text = ""
                    for msg in messages:
                        role = msg.get("role", msg.get("from", ""))
                        content = msg.get("content", msg.get("value", ""))
                        if role in ("system", "human", "user"):
                            text += f"### Instruction:\n{content}\n\n"
                        elif role in ("assistant", "gpt"):
                            text += f"### Response:\n{content}\n\n"
                    data.append({"text": text.strip()})

    print(f"Total samples loaded: {len(data)}")
    return data


def tokenize_function(examples, tokenizer, max_length=512):
    """텍스트 토큰화."""
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="pt",
    )


def main():
    # 설정 (CLI 인자 추가)
    import argparse
    ap = argparse.ArgumentParser(description="QLoRA fine-tuning")
    ap.add_argument("--base-model", default="beomi/Llama-3-Open-Ko-8B", help="HF repo id or local path")
    ap.add_argument("--data-dir", default="data/training", help="Training data directory (jsonl files)")
    ap.add_argument("--output-dir", default="outputs/ecommerce-agent-qlora", help="Output directory for LoRA adapter")
    ap.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    ap.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    ap.add_argument("--batch", type=int, default=2, help="Per-device train batch size")
    ap.add_argument("--max-length", type=int, default=512, help="Sequence length")
    args = ap.parse_args()

    BASE_MODEL = args.base_model
    DATA_DIR = args.data_dir
    OUTPUT_DIR = args.output_dir

    print("=" * 60)
    print("  E-commerce Agent QLoRA Fine-tuning")
    print("=" * 60)

    # GPU 확인
    if not torch.cuda.is_available():
        print("Error: CUDA GPU required")
        sys.exit(1)

    print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA: {torch.version.cuda}")

    # 학습 데이터 로드
    print("\n[1/5] Loading training data...")
    raw_data = load_training_data(DATA_DIR)
    dataset = Dataset.from_list(raw_data)

    # 토크나이저 로드
    print("\n[2/5] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 데이터 토큰화
    print("\n[3/5] Tokenizing data...")
    def tokenize_fn(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )

    tokenized_dataset = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])
    tokenized_dataset = tokenized_dataset.train_test_split(test_size=0.1, seed=42)

    # 4bit 양자화 설정
    print("\n[4/5] Loading model with QLoRA...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    # 모델 로드
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA 설정
    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 학습 설정
    print("\n[5/5] Starting training...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        fp16=True,
        gradient_checkpointing=True,
        report_to="none",  # wandb 비활성화
        seed=42,
    )

    # 데이터 콜레이터
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    # Trainer 생성
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["test"],
        data_collator=data_collator,
    )

    # 학습 시작
    trainer.train()

    # 모델 저장
    print("\nSaving model...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("  Training Complete!")
    print("=" * 60)
    print(f"Model saved to: {OUTPUT_DIR}")
    print("\nNext steps:")
    print("  1. Merge LoRA: bash scripts/07_merge_lora.sh")
    print("  2. Test model: python scripts/08_test_finetuned_model.py")


if __name__ == "__main__":
    main()
