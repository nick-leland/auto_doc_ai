from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment_utils import (
    compute_ocr_metrics,
    evaluate_model_on_examples,
    load_examples,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate OCR and LayoutLMv3 baselines on a held-out dataset split.",
    )
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("src/fine_tune_LayoutLMv3/models/layoutlmv3-funsd"),
    )
    parser.add_argument("--split", choices=["train", "val", "test"], default="test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument(
        "--ocr-source",
        choices=["tesseract", "paddleocr", "ground_truth"],
        default="tesseract",
        help="Token source for LayoutLMv3 evaluation.",
    )
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    examples = load_examples(
        dataset_dir=args.dataset_dir,
        split=args.split,
        seed=args.seed,
        max_samples=args.max_samples,
    )

    if not examples:
        raise SystemExit(f"No examples found for split={args.split} in {args.dataset_dir}")

    ocr_backend = "tesseract" if args.ocr_source == "ground_truth" else args.ocr_source
    ocr_metrics = compute_ocr_metrics(examples, ocr_source=ocr_backend)
    layoutlm_metrics = evaluate_model_on_examples(
        examples=examples,
        model_dir=args.model_dir,
        ocr_source=args.ocr_source,
        device=args.device,
    )

    result = {
        "dataset_dir": str(args.dataset_dir),
        "model_dir": str(args.model_dir),
        "split": args.split,
        "num_examples": len(examples),
        "ocr_metrics": ocr_metrics,
        "layoutlm_metrics": layoutlm_metrics,
    }

    print(json.dumps(result, indent=2))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fh:
            json.dump(result, fh, indent=2)


if __name__ == "__main__":
    main()
