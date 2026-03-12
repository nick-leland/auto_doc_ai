from __future__ import annotations

import argparse
import json
from pathlib import Path

from seqeval.metrics import f1_score as seqeval_f1_score
from seqeval.metrics import precision_score as seqeval_precision_score
from seqeval.metrics import recall_score as seqeval_recall_score

from experiment_utils import (
    assign_labels_to_ocr_tokens,
    compute_ocr_metrics,
    load_model,
    load_processor,
    load_truth_labeled_tokens,
    predict_word_labels,
    run_ocr,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a local OCR -> LayoutLMv3 pipeline on a real-world validation folder.",
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--ocr-source", choices=["tesseract", "paddleocr"], default="tesseract")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--predictions-dir", type=Path, default=None)
    return parser.parse_args()


def compute_sequence_metrics(
    true_sequences: list[list[str]],
    pred_sequences: list[list[str]],
) -> dict[str, float]:
    correct = total = 0
    tp = fp = fn = 0

    for true_labels, pred_labels in zip(true_sequences, pred_sequences):
        for true_label, pred_label in zip(true_labels, pred_labels):
            total += 1
            correct += int(pred_label == true_label)
            pred_is_entity = pred_label != "O"
            true_is_entity = true_label != "O"
            tp += int(pred_is_entity and true_is_entity and pred_label == true_label)
            fp += int(pred_is_entity and (not true_is_entity or pred_label != true_label))
            fn += int(true_is_entity and (not pred_is_entity or pred_label != true_label))

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    return {
        "token_accuracy": correct / max(total, 1),
        "entity_precision": precision,
        "entity_recall": recall,
        "entity_f1": f1,
        "seqeval_precision": seqeval_precision_score(true_sequences, pred_sequences),
        "seqeval_recall": seqeval_recall_score(true_sequences, pred_sequences),
        "seqeval_f1": seqeval_f1_score(true_sequences, pred_sequences),
        "num_examples": len(true_sequences),
    }


def list_validation_images(images_dir: Path) -> list[Path]:
    return sorted(
        path for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def main() -> None:
    args = parse_args()
    images_dir = args.data_dir / "images"
    labels_dir = args.data_dir / "labels"
    if not images_dir.exists():
        raise SystemExit(f"Missing images directory: {images_dir}")
    if not labels_dir.exists():
        raise SystemExit(f"Missing labels directory: {labels_dir}")

    images = list_validation_images(images_dir)
    if not images:
        raise SystemExit(f"No images found in {images_dir}")

    processor = load_processor(args.model_dir)
    model = load_model(args.model_dir)
    device = args.device
    if device is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    examples_for_ocr_metrics: list[dict] = []
    true_sequences: list[list[str]] = []
    pred_sequences: list[list[str]] = []
    per_image_results: list[dict] = []
    skipped: list[dict] = []

    if args.predictions_dir is not None:
        args.predictions_dir.mkdir(parents=True, exist_ok=True)

    for image_path in images:
        label_path = labels_dir / f"{image_path.stem}.json"
        if not label_path.exists():
            skipped.append({"image": str(image_path), "reason": "missing_label_json"})
            continue

        truth = load_truth_labeled_tokens(label_path, image_path=image_path)
        examples_for_ocr_metrics.append({
            "image_path": image_path,
            "words": truth["words"],
        })

        ocr_words, ocr_boxes, image_size = run_ocr(image_path, args.ocr_source)
        if not ocr_words:
            skipped.append({"image": str(image_path), "reason": "no_ocr_tokens"})
            continue

        true_labels = assign_labels_to_ocr_tokens(
            ocr_boxes,
            truth["bboxes"],
            truth["labels"],
            image_size=image_size,
        )
        pred_labels = predict_word_labels(
            processor=processor,
            model=model,
            image_path=image_path,
            words=ocr_words,
            boxes=ocr_boxes,
            device=device,
        )

        true_sequences.append(true_labels)
        pred_sequences.append(pred_labels)

        prediction_doc = {
            "image": str(image_path),
            "label_file": str(label_path),
            "ocr_source": args.ocr_source,
            "model_dir": str(args.model_dir),
            "predictions": [
                {
                    "text": word,
                    "bbox": box,
                    "pred_label": pred_label,
                    "true_label": true_label,
                }
                for word, box, pred_label, true_label in zip(
                    ocr_words,
                    ocr_boxes,
                    pred_labels,
                    true_labels,
                )
            ],
        }
        per_image_results.append(prediction_doc)

        if args.predictions_dir is not None:
            output_path = args.predictions_dir / f"{image_path.stem}.json"
            with open(output_path, "w") as fh:
                json.dump(prediction_doc, fh, indent=2)

    if not true_sequences:
        raise SystemExit("No validation examples were evaluated.")

    result = {
        "data_dir": str(args.data_dir),
        "model_dir": str(args.model_dir),
        "ocr_source": args.ocr_source,
        "device": device,
        "num_images": len(images),
        "num_evaluated": len(true_sequences),
        "num_skipped": len(skipped),
        "skipped": skipped,
        "ocr_metrics": compute_ocr_metrics(examples_for_ocr_metrics, ocr_source=args.ocr_source),
        "layoutlm_metrics": compute_sequence_metrics(true_sequences, pred_sequences),
    }

    print(json.dumps(result, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as fh:
            json.dump(result, fh, indent=2)


if __name__ == "__main__":
    main()
