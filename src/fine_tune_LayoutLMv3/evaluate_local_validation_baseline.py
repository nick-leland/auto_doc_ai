from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluate_local_validation import main as run_validation_main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the local Tesseract -> baseline LayoutLMv3 pipeline on a validation folder.",
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--ocr-source", choices=["tesseract", "paddleocr"], default="tesseract")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--predictions-dir", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    argv = [
        sys.argv[0],
        "--data-dir",
        str(args.data_dir),
        "--model-dir",
        "src/fine_tune_LayoutLMv3/models/layoutlmv3-funsd",
        "--ocr-source",
        args.ocr_source,
    ]
    if args.device is not None:
        argv.extend(["--device", args.device])
    if args.output is not None:
        argv.extend(["--output", str(args.output)])
    if args.predictions_dir is not None:
        argv.extend(["--predictions-dir", str(args.predictions_dir)])
    sys.argv = argv
    run_validation_main()
