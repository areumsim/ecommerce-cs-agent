#!/usr/bin/env python3
from __future__ import annotations

"""Download a base model snapshot from Hugging Face to a local directory.

Usage:
  python scripts/00_download_base_model.py \
    --repo-id beomi/Llama-3-Open-Ko-8B \
    --target models/beomi-Llama-3-Open-Ko-8B [--revision main]

Notes:
  - Requires `huggingface_hub` (pip install huggingface_hub)
  - Set HF_TOKEN env if the model requires authentication
  - Files are cached in HF cache; this script ensures a local copy exists
"""

import argparse
from pathlib import Path
import os
import sys

try:
    from huggingface_hub import snapshot_download
except Exception as e:
    print("[ERR] Missing dependency: huggingface_hub.\n"
          "      pip install huggingface_hub\n"
          f"      Details: {e}")
    sys.exit(1)


def main() -> None:
    p = argparse.ArgumentParser(description="Download HF model snapshot")
    p.add_argument("--repo-id", required=True, help="HF repo id (e.g., beomi/Llama-3-Open-Ko-8B)")
    p.add_argument("--revision", default="main", help="Git revision/tag (default: main)")
    p.add_argument("--target", required=True, help="Local target dir to place snapshot")
    args = p.parse_args()

    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    print(f"[HF] Downloading repo={args.repo_id} rev={args.revision}")
    local_path = snapshot_download(
        repo_id=args.repo_id,
        revision=args.revision,
        local_dir=str(target),
        local_dir_use_symlinks=False,  # materialize files under target
        resume_download=True,
    )
    print(f"[OK] Snapshot ready at: {local_path}")


if __name__ == "__main__":
    main()

