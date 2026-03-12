from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from experiment_utils import load_model, load_processor, predict_word_labels, run_ocr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local Tesseract -> LayoutLMv3 pipeline on a single page image.",
    )
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image.exists():
        raise SystemExit(f"Image not found: {args.image}")

    processor = load_processor(args.model_dir)
    model = load_model(args.model_dir)

    if args.device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    model.to(device)

    words, boxes, image_size = run_ocr(args.image, "tesseract")
    labels = predict_word_labels(
        processor=processor,
        model=model,
        image_path=args.image,
        words=words,
        boxes=boxes,
        device=device,
    )

    result = {
        "image": str(args.image),
        "model_dir": str(args.model_dir),
        "ocr_source": "tesseract",
        "device": device,
        "image_size": list(image_size),
        "predictions": [
            {
                "text": word,
                "bbox": box,
                "label": label,
            }
            for word, box, label in zip(words, boxes, labels)
        ],
    }

    print(json.dumps(result, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fh:
            json.dump(result, fh, indent=2)


if __name__ == "__main__":
    main()
