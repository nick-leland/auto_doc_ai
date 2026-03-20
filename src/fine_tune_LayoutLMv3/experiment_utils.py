from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pytesseract
import torch
from PIL import Image
from datasets import Dataset
from pytesseract import Output
from seqeval.metrics import f1_score as seqeval_f1_score
from seqeval.metrics import precision_score as seqeval_precision_score
from seqeval.metrics import recall_score as seqeval_recall_score
from transformers import AutoModelForTokenClassification, AutoProcessor


FUNSD_LABELS = [
    "O",
    "B-HEADER",
    "I-HEADER",
    "B-QUESTION",
    "I-QUESTION",
    "B-ANSWER",
    "I-ANSWER",
]
LABEL2ID = {label: idx for idx, label in enumerate(FUNSD_LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}

HEADER_FIELDS = {"doc_title"}
HEADER_BLOCKS = {"header"}
_PADDLE_OCR = None


def list_annotation_files(dataset_dir: Path) -> list[Path]:
    return sorted((dataset_dir / "annotations").glob("*.json"))


def list_doc_ids(dataset_dir: Path) -> list[str]:
    doc_ids = {path.name.replace("_front.json", "").replace("_back.json", "") for path in list_annotation_files(dataset_dir)}
    return sorted(doc_ids)


def split_doc_ids(
    dataset_dir: Path,
    train_ratio: float = 0.7,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> dict[str, set[str]]:
    doc_ids = list_doc_ids(dataset_dir)
    rng = np.random.default_rng(seed)
    shuffled = list(doc_ids)
    rng.shuffle(shuffled)

    total = len(shuffled)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    return {
        "train": set(shuffled[:train_end]),
        "val": set(shuffled[train_end:val_end]),
        "test": set(shuffled[val_end:]),
    }


def _field_lookup(annotation_doc: dict) -> dict[str, dict]:
    return {field["field_name"]: field for field in annotation_doc["annotations"]["fields"]}


def _base_entity_type(word: dict, field: dict) -> str:
    if word["category"] == "value":
        return "ANSWER"

    if field["style"] != "label_only":
        return "QUESTION"

    if (
        field["field_name"] in HEADER_FIELDS
        or field["block_type"] in HEADER_BLOCKS
    ):
        return "HEADER"

    return "O"


def build_funsd_word_labels(annotation_doc: dict) -> list[str]:
    words = annotation_doc["annotations"]["words"]
    field_by_name = _field_lookup(annotation_doc)

    labels: list[str] = []
    prev_key: tuple[str, str, str] | None = None

    for word in words:
        field = field_by_name[word["field_name"]]
        entity_type = _base_entity_type(word, field)
        if entity_type == "O":
            labels.append("O")
            prev_key = None
            continue

        key = (word["field_name"], word["category"], entity_type)
        prefix = "I" if key == prev_key else "B"
        labels.append(f"{prefix}-{entity_type}")
        prev_key = key

    return labels


def _normalize_label_token(label: str) -> str:
    label = str(label).strip().upper()
    if label in LABEL2ID:
        return label
    if label in {"HEADER", "QUESTION", "ANSWER"}:
        return f"B-{label}"
    if label == "OTHER":
        return "O"
    if label == "O":
        return "O"
    raise ValueError(f"Unsupported label value: {label}")


def _normalize_token_bbox(
    token: dict,
    image_size: tuple[int, int] | None,
) -> list[int]:
    if "normalized_bbox" in token:
        return [int(v) for v in token["normalized_bbox"]]

    if "bbox" not in token:
        raise ValueError("Token entry must include `bbox` or `normalized_bbox`.")

    bbox = [float(v) for v in token["bbox"]]
    if all(0 <= v <= 1000 for v in bbox):
        return [int(v) for v in bbox]

    if image_size is None:
        raise ValueError("Absolute pixel bboxes require image size context.")

    width, height = image_size
    return normalize_bbox(bbox, width, height)


def load_truth_labeled_tokens(
    label_path: Path,
    image_path: Path | None = None,
) -> dict[str, list]:
    with open(label_path) as fh:
        payload = json.load(fh)

    image_size: tuple[int, int] | None = None
    if "image_size" in payload:
        image_size = tuple(payload["image_size"])
    elif "original_size" in payload:
        image_size = tuple(payload["original_size"])
    elif image_path is not None and image_path.exists():
        with Image.open(image_path) as image:
            image_size = image.size

    if "annotations" in payload and "words" in payload["annotations"]:
        words = payload["annotations"]["words"]
        labels = build_funsd_word_labels(payload)
        return {
            "words": [word["text"] for word in words],
            "bboxes": [
                [int(v) for v in word["normalized_bbox"]]
                if "normalized_bbox" in word
                else _normalize_token_bbox(word, image_size)
                for word in words
            ],
            "labels": labels,
        }

    token_entries = payload.get("tokens") or payload.get("predictions")
    if token_entries is None:
        raise ValueError(
            f"Unsupported label file format for {label_path}. Expected synthetic annotation JSON "
            "or a simple token-label JSON with `tokens`."
        )

    words: list[str] = []
    bboxes: list[list[int]] = []
    labels: list[str] = []
    for token in token_entries:
        words.append(str(token.get("text", "")))
        bboxes.append(_normalize_token_bbox(token, image_size))
        labels.append(_normalize_label_token(token["label"]))

    return {
        "words": words,
        "bboxes": bboxes,
        "labels": labels,
    }


def _cache_ocr_result(
    image_path: Path,
    ocr_source: str,
    cache_dir: Path | None,
) -> tuple[list[str], list[list[int]], tuple[int, int]]:
    if cache_dir is None:
        return run_ocr(image_path, ocr_source)

    cache_path = cache_dir / f"{image_path.stem}.json"
    if cache_path.exists():
        with open(cache_path) as fh:
            payload = json.load(fh)
        return payload["words"], payload["bboxes"], tuple(payload["image_size"])

    words, bboxes, image_size = run_ocr(image_path, ocr_source)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as fh:
        json.dump(
            {
                "image_path": str(image_path),
                "ocr_source": ocr_source,
                "words": words,
                "bboxes": bboxes,
                "image_size": list(image_size),
            },
            fh,
            indent=2,
        )
    return words, bboxes, image_size


def load_examples(
    dataset_dir: Path,
    split: str,
    seed: int = 42,
    max_samples: int | None = None,
    ocr_source: str = "ground_truth",
    ocr_cache_dir: Path | None = None,
) -> list[dict]:
    split_ids = split_doc_ids(dataset_dir, seed=seed)[split]
    examples: list[dict] = []

    for ann_path in list_annotation_files(dataset_dir):
        side = "front" if ann_path.stem.endswith("_front") else "back"
        doc_id = ann_path.stem.rsplit("_", 1)[0]
        if doc_id not in split_ids:
            continue

        with open(ann_path) as fh:
            annotation_doc = json.load(fh)

        words = annotation_doc["annotations"]["words"]
        labels = build_funsd_word_labels(annotation_doc)
        image_path = dataset_dir / annotation_doc["image_file"]

        if ocr_source == "ground_truth":
            example_words = [word["text"] for word in words]
            example_bboxes = [word["normalized_bbox"] for word in words]
            example_labels = labels
        else:
            example_words, example_bboxes, image_size = _cache_ocr_result(
                image_path=image_path,
                ocr_source=ocr_source,
                cache_dir=ocr_cache_dir,
            )
            if not example_words:
                continue
            example_labels = assign_labels_to_ocr_tokens(
                example_bboxes,
                [word["normalized_bbox"] for word in words],
                labels,
                image_size=image_size,
            )

        examples.append({
            "doc_id": doc_id,
            "side": side,
            "image_path": image_path,
            "words": example_words,
            "bboxes": example_bboxes,
            "abs_bboxes": [word["bbox"] for word in words],
            "labels": example_labels,
        })

        if max_samples is not None and len(examples) >= max_samples:
            break

    examples.sort(key=lambda item: (item["doc_id"], item["side"]))
    return examples


def load_processor(model_dir: Path):
    return AutoProcessor.from_pretrained(str(model_dir), apply_ocr=False)


def load_model(model_dir: Path):
    model = AutoModelForTokenClassification.from_pretrained(str(model_dir))
    model.config.id2label = ID2LABEL
    model.config.label2id = LABEL2ID
    return model


def encode_word_labels(word_ids: list[int | None], word_label_ids: list[int]) -> list[int]:
    encoded = []
    prev_word_id = None
    for word_id in word_ids:
        if word_id is None:
            encoded.append(-100)
        elif word_id != prev_word_id:
            encoded.append(word_label_ids[word_id])
        else:
            encoded.append(-100)
        prev_word_id = word_id
    return encoded


class LayoutLMTokenDataset(torch.utils.data.Dataset):
    def __init__(self, examples: list[dict], processor):
        self.examples = examples
        self.processor = processor

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        example = self.examples[idx]
        image = Image.open(example["image_path"]).convert("RGB")
        word_label_ids = [LABEL2ID[label] for label in example["labels"]]

        encoding = self.processor(
            images=image,
            text=example["words"],
            boxes=example["bboxes"],
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        word_ids = encoding.word_ids(batch_index=0)
        encoding["labels"] = torch.tensor(
            encode_word_labels(word_ids, word_label_ids),
            dtype=torch.long,
        ).unsqueeze(0)

        return {key: value.squeeze(0) for key, value in encoding.items()}


def compute_trainer_metrics(eval_pred) -> dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)

    true_sequences = []
    pred_sequences = []
    correct = 0
    total = 0
    tp = fp = fn = 0

    for pred_row, label_row in zip(preds, labels):
        true_seq = []
        pred_seq = []
        for pred_id, label_id in zip(pred_row, label_row):
            if label_id == -100:
                continue
            pred_label = ID2LABEL[int(pred_id)]
            true_label = ID2LABEL[int(label_id)]
            pred_seq.append(pred_label)
            true_seq.append(true_label)
            total += 1
            correct += int(pred_label == true_label)
            pred_is_entity = pred_label != "O"
            true_is_entity = true_label != "O"
            tp += int(pred_is_entity and true_is_entity and pred_label == true_label)
            fp += int(pred_is_entity and (not true_is_entity or pred_label != true_label))
            fn += int(true_is_entity and (not pred_is_entity or pred_label != true_label))

        if true_seq:
            true_sequences.append(true_seq)
            pred_sequences.append(pred_seq)

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
    }


def normalize_text_token(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", token.lower())


def levenshtein_distance(seq_a: list[str] | str, seq_b: list[str] | str) -> int:
    len_a = len(seq_a)
    len_b = len(seq_b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a

    prev = list(range(len_b + 1))
    for i in range(1, len_a + 1):
        curr = [i] + [0] * len_b
        for j in range(1, len_b + 1):
            cost = 0 if seq_a[i - 1] == seq_b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev = curr
    return prev[-1]


def run_tesseract(image_path: Path) -> tuple[list[str], list[list[int]], tuple[int, int]]:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    data = pytesseract.image_to_data(image, output_type=Output.DICT)

    words: list[str] = []
    bboxes: list[list[int]] = []

    for idx, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        conf = float(data["conf"][idx]) if data["conf"][idx] not in {"-1", ""} else -1.0
        if conf < 0:
            continue

        left = int(data["left"][idx])
        top = int(data["top"][idx])
        w = int(data["width"][idx])
        h = int(data["height"][idx])
        if w <= 0 or h <= 0:
            continue

        words.append(text)
        bboxes.append(normalize_bbox([left, top, left + w, top + h], width, height))

    return words, bboxes, (width, height)


def _get_paddleocr():
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        paddle_root = Path("/tmp/auto_doc_ai_paddle")
        os.environ.setdefault("HOME", str(paddle_root / "home"))
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(paddle_root / "paddlex"))
        os.environ.setdefault("PADDLE_HOME", str(paddle_root / "paddle"))
        os.environ.setdefault("XDG_CACHE_HOME", str(paddle_root / "xdg_cache"))
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        for env_name in ("HOME", "PADDLE_PDX_CACHE_HOME", "PADDLE_HOME", "XDG_CACHE_HOME"):
            Path(os.environ[env_name]).mkdir(parents=True, exist_ok=True)

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR backend requested, but `paddleocr` is not installed in the project environment."
            ) from exc

        _PADDLE_OCR = PaddleOCR(
            device="cpu",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            lang="en",
        )
    return _PADDLE_OCR


def _quad_to_bbox(points: list[list[float]], width: int, height: int) -> list[int]:
    xs = [pt[0] for pt in points]
    ys = [pt[1] for pt in points]
    return normalize_bbox([min(xs), min(ys), max(xs), max(ys)], width, height)


def _extract_paddle_lines(obj: Any) -> list[dict]:
    lines: list[dict] = []
    if obj is None:
        return lines
    if isinstance(obj, dict):
        if "rec_texts" in obj and "rec_boxes" in obj:
            for text, box in zip(obj["rec_texts"], obj["rec_boxes"]):
                lines.append({"text": text, "points": box})
            return lines
        for value in obj.values():
            lines.extend(_extract_paddle_lines(value))
        return lines
    if isinstance(obj, list):
        if len(obj) == 2 and isinstance(obj[0], (list, tuple)) and isinstance(obj[1], (list, tuple)):
            maybe_text = obj[1][0] if obj[1] else None
            if isinstance(maybe_text, str):
                lines.append({"text": maybe_text, "points": obj[0]})
                return lines
        for item in obj:
            lines.extend(_extract_paddle_lines(item))
    return lines


def run_paddleocr(image_path: Path) -> tuple[list[str], list[list[int]], tuple[int, int]]:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    ocr = _get_paddleocr()
    result = ocr.predict(str(image_path))
    raw_lines = _extract_paddle_lines(result)

    words: list[str] = []
    bboxes: list[list[int]] = []
    for line in raw_lines:
        text = str(line["text"]).strip()
        if not text:
            continue
        points = line["points"]
        if hasattr(points, "tolist"):
            points = points.tolist()
        if not points:
            continue
        words.append(text)
        bboxes.append(_quad_to_bbox(points, width, height))

    return words, bboxes, (width, height)


def run_ocr(image_path: Path, ocr_source: str) -> tuple[list[str], list[list[int]], tuple[int, int]]:
    if ocr_source == "tesseract":
        return run_tesseract(image_path)
    if ocr_source == "paddleocr":
        return run_paddleocr(image_path)
    raise ValueError(f"Unsupported OCR source: {ocr_source}")


def normalize_bbox(bbox: list[float], width: int, height: int) -> list[int]:
    x1, y1, x2, y2 = bbox
    return [
        max(0, min(1000, int(1000 * x1 / max(width, 1)))),
        max(0, min(1000, int(1000 * y1 / max(height, 1)))),
        max(0, min(1000, int(1000 * x2 / max(width, 1)))),
        max(0, min(1000, int(1000 * y2 / max(height, 1)))),
    ]


def denormalize_bbox(bbox: list[int], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    return (
        width * x1 / 1000.0,
        height * y1 / 1000.0,
        width * x2 / 1000.0,
        height * y2 / 1000.0,
    )


def _intersection(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def assign_labels_to_ocr_tokens(
    ocr_bboxes: list[list[int]],
    gt_bboxes: list[list[int]],
    gt_labels: list[str],
    image_size: tuple[int, int],
    min_score: float = 0.1,
) -> list[str]:
    width, height = image_size
    gt_boxes = [denormalize_bbox(bbox, width, height) for bbox in gt_bboxes]
    ocr_boxes = [denormalize_bbox(bbox, width, height) for bbox in ocr_bboxes]

    assigned = []
    for ocr_box in ocr_boxes:
        best_label = "O"
        best_score = 0.0
        ocr_area = max((ocr_box[2] - ocr_box[0]) * (ocr_box[3] - ocr_box[1]), 1.0)
        center_x = (ocr_box[0] + ocr_box[2]) / 2.0
        center_y = (ocr_box[1] + ocr_box[3]) / 2.0

        for gt_box, gt_label in zip(gt_boxes, gt_labels):
            inter = _intersection(ocr_box, gt_box)
            if inter <= 0:
                continue
            overlap = inter / ocr_area
            if gt_box[0] <= center_x <= gt_box[2] and gt_box[1] <= center_y <= gt_box[3]:
                overlap += 0.5
            if overlap > best_score:
                best_score = overlap
                best_label = gt_label

        assigned.append(best_label if best_score >= min_score else "O")

    return assigned


def compute_ocr_metrics(examples: list[dict], ocr_source: str = "tesseract") -> dict[str, float]:
    total_word_distance = 0
    total_word_count = 0
    total_char_distance = 0
    total_char_count = 0
    gt_token_counter: Counter[str] = Counter()
    ocr_token_counter: Counter[str] = Counter()

    for example in examples:
        ocr_words, _, _ = run_ocr(example["image_path"], ocr_source)
        gt_words = [normalize_text_token(word) for word in example["words"]]
        pred_words = [normalize_text_token(word) for word in ocr_words]
        gt_words = [word for word in gt_words if word]
        pred_words = [word for word in pred_words if word]

        total_word_distance += levenshtein_distance(gt_words, pred_words)
        total_word_count += len(gt_words)

        gt_chars = list(" ".join(gt_words))
        pred_chars = list(" ".join(pred_words))
        total_char_distance += levenshtein_distance(gt_chars, pred_chars)
        total_char_count += len(gt_chars)

        gt_token_counter.update(gt_words)
        ocr_token_counter.update(pred_words)

    overlap = sum((gt_token_counter & ocr_token_counter).values())
    precision = overlap / max(sum(ocr_token_counter.values()), 1)
    recall = overlap / max(sum(gt_token_counter.values()), 1)

    return {
        "ocr_source": ocr_source,
        "word_error_rate": total_word_distance / max(total_word_count, 1),
        "char_error_rate": total_char_distance / max(total_char_count, 1),
        "bag_token_precision": precision,
        "bag_token_recall": recall,
        "bag_token_f1": 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall),
    }


def predict_word_labels(
    processor,
    model,
    image_path: Path,
    words: list[str],
    boxes: list[list[int]],
    device: str,
) -> list[str]:
    image = Image.open(image_path).convert("RGB")
    encoding = processor(
        images=image,
        text=words,
        boxes=boxes,
        truncation=True,
        padding="max_length",
        return_tensors="pt",
    )

    word_ids = encoding.word_ids(batch_index=0)
    inputs = {key: value.to(device) for key, value in encoding.items()}

    model.eval()
    with torch.no_grad():
        logits = model(**inputs).logits[0].detach().cpu().numpy()

    predictions: list[str | None] = [None] * len(words)
    seen: set[int] = set()
    for token_idx, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen:
            continue
        seen.add(word_id)
        predictions[word_id] = ID2LABEL[int(np.argmax(logits[token_idx]))]

    return [pred if pred is not None else "O" for pred in predictions]


def evaluate_model_on_examples(
    examples: list[dict],
    model_dir: Path,
    ocr_source: str = "tesseract",
    device: str | None = None,
) -> dict[str, float]:
    processor = load_processor(model_dir)
    model = load_model(model_dir)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    true_sequences = []
    pred_sequences = []
    correct = total = 0
    tp = fp = fn = 0

    for example in examples:
        if ocr_source == "ground_truth":
            words = example["words"]
            boxes = example["bboxes"]
            true_labels = example["labels"]
        else:
            words, boxes, image_size = run_ocr(example["image_path"], ocr_source)
            true_labels = assign_labels_to_ocr_tokens(
                boxes,
                example["bboxes"],
                example["labels"],
                image_size=image_size,
            )

        if not words:
            continue

        pred_labels = predict_word_labels(
            processor=processor,
            model=model,
            image_path=example["image_path"],
            words=words,
            boxes=boxes,
            device=device,
        )

        true_sequences.append(true_labels)
        pred_sequences.append(pred_labels)

        for pred_label, true_label in zip(pred_labels, true_labels):
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
        "ocr_source": ocr_source,
        "token_accuracy": correct / max(total, 1),
        "entity_precision": precision,
        "entity_recall": recall,
        "entity_f1": f1,
        "seqeval_precision": seqeval_precision_score(true_sequences, pred_sequences),
        "seqeval_recall": seqeval_recall_score(true_sequences, pred_sequences),
        "seqeval_f1": seqeval_f1_score(true_sequences, pred_sequences),
        "num_examples": len(true_sequences),
    }


def examples_to_hf_dataset(examples: list[dict]) -> Dataset:
    return Dataset.from_list([
        {
            "doc_id": example["doc_id"],
            "side": example["side"],
            "image_path": str(example["image_path"]),
            "words": example["words"],
            "bboxes": example["bboxes"],
            "labels": example["labels"],
        }
        for example in examples
    ])
