from __future__ import annotations

import argparse
from pathlib import Path

from run_tesseract_layoutlmv3 import main as run_pipeline_main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local Tesseract -> OCR-aware fine-tuned LayoutLMv3 pipeline on a single page image.",
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    import sys

    argv = [
        sys.argv[0],
        "--image",
        str(args.image),
        "--model-dir",
        "runs/layoutlmv3-funsd-tesseract-seed42/best_model",
    ]
    if args.device is not None:
        argv.extend(["--device", args.device])
    if args.output is not None:
        argv.extend(["--output", str(args.output)])
    sys.argv = argv
    run_pipeline_main()
