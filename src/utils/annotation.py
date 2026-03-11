"""
Annotation generator for document layout datasets.

Converts render metadata + field values into multi-format annotations
suitable for OCR, LayoutLMv3, key-value extraction, and document
structure understanding tasks.

Output format is task-agnostic at the base level, with converters
for specific training formats.
"""

from __future__ import annotations


def _estimate_word_bboxes(
    text: str,
    bbox: tuple[float, float, float, float],
) -> list[dict]:
    """Split text into words and estimate per-word bounding boxes.

    Uses proportional character-width estimation within the field bbox.
    This is approximate but consistent — the actual rendered text may
    vary slightly due to font metrics, but for training data the
    spatial relationship is what matters.
    """
    words = text.split()
    if not words:
        return []

    x1, y1, x2, y2 = bbox
    total_w = x2 - x1

    # Estimate relative width of each word (by character count + spaces)
    total_chars = sum(len(w) for w in words) + len(words) - 1
    if total_chars <= 0:
        total_chars = 1

    result = []
    cursor_x = x1

    for i, word in enumerate(words):
        # Width proportional to character count
        char_count = len(word)
        if i < len(words) - 1:
            char_count += 1  # account for space after word
        word_w = total_w * (char_count / total_chars)

        result.append({
            "text": word,
            "bbox": [
                round(cursor_x, 1),
                round(y1, 1),
                round(cursor_x + word_w, 1),
                round(y2, 1),
            ],
        })
        cursor_x += word_w

    return result


def _normalize_bbox(
    bbox: list[float],
    img_w: int,
    img_h: int,
    target_range: int = 1000,
) -> list[int]:
    """Normalize bbox to [0, target_range] as required by LayoutLMv3."""
    x1, y1, x2, y2 = bbox
    return [
        max(0, min(target_range, int(x1 / img_w * target_range))),
        max(0, min(target_range, int(y1 / img_h * target_range))),
        max(0, min(target_range, int(x2 / img_w * target_range))),
        max(0, min(target_range, int(y2 / img_h * target_range))),
    ]


def build_annotations(
    metadata: dict,
    values: dict,
    img_w: int,
    img_h: int,
    transform_bbox=None,
) -> dict:
    """Build multi-format annotations from render metadata.

    Args:
        metadata: Layout metadata from render_layout() — has block/field bboxes.
        values: The field values dict used to fill the document.
        img_w, img_h: Image dimensions (after augmentation).
        transform_bbox: Optional callable(x1,y1,x2,y2) -> (x1,y1,x2,y2)
            for mapping original bboxes through augmentation transforms.

    Returns a dict with:
        - "words": flat list of word-level annotations (for OCR / LayoutLMv3)
        - "fields": field-level annotations (for key-value extraction)
        - "blocks": block-level structure (for document understanding)
    """
    if transform_bbox is None:
        transform_bbox = lambda x1, y1, x2, y2: (x1, y1, x2, y2)

    all_words = []
    all_fields = []
    all_blocks = []

    for block in metadata.get("blocks", []):
        block_type = block.get("block_type", "")
        variant_id = block.get("variant_id", "")
        block_bbox = block.get("bbox", {})

        block_entry = {
            "block_type": block_type,
            "variant_id": variant_id,
            "bbox": _transform_meta_bbox(block_bbox, transform_bbox),
            "fields": [],
        }

        for field in block.get("fields", []):
            field_name = field["name"]
            field_label = field["label"]
            field_style = field["style"]
            field_type = field.get("field_type", "text")

            label_rect = field.get("label_rect", {})
            value_rect = field.get("value_rect", {})

            # Transform bboxes through augmentation
            label_bbox = _transform_meta_bbox(label_rect, transform_bbox)
            value_bbox = _transform_meta_bbox(value_rect, transform_bbox)

            # Get the actual value text
            value_text = values.get(field_name, "")

            field_entry = {
                "field_name": field_name,
                "field_type": field_type,
                "style": field_style,
                "block_type": block_type,
                "label": {
                    "text": field_label,
                    "bbox": label_bbox,
                    "normalized_bbox": _normalize_bbox(label_bbox, img_w, img_h),
                },
            }

            # Label words
            if field_label:
                label_words = _estimate_word_bboxes(field_label, label_bbox)
                for w in label_words:
                    w["normalized_bbox"] = _normalize_bbox(w["bbox"], img_w, img_h)
                    w["category"] = "label"
                    w["field_name"] = field_name
                    w["block_type"] = block_type
                    w["field_type"] = field_type
                all_words.extend(label_words)
                field_entry["label"]["words"] = label_words

            # Value (only for fillable fields with actual content)
            if field_style != "label_only" and value_text:
                field_entry["value"] = {
                    "text": value_text,
                    "bbox": value_bbox,
                    "normalized_bbox": _normalize_bbox(value_bbox, img_w, img_h),
                }

                value_words = _estimate_word_bboxes(value_text, value_bbox)
                for w in value_words:
                    w["normalized_bbox"] = _normalize_bbox(w["bbox"], img_w, img_h)
                    w["category"] = "value"
                    w["field_name"] = field_name
                    w["block_type"] = block_type
                    w["field_type"] = field_type
                all_words.extend(value_words)
                field_entry["value"]["words"] = value_words
            elif field_style == "label_only":
                field_entry["value"] = None
            else:
                field_entry["value"] = {
                    "text": "",
                    "bbox": value_bbox,
                    "normalized_bbox": _normalize_bbox(value_bbox, img_w, img_h),
                }

            all_fields.append(field_entry)
            block_entry["fields"].append(field_entry)

        all_blocks.append(block_entry)

    return {
        "words": all_words,
        "fields": all_fields,
        "blocks": all_blocks,
    }


def _transform_meta_bbox(
    rect: dict,
    transform_bbox,
) -> list[float]:
    """Convert metadata rect dict {x,y,w,h} to [x1,y1,x2,y2] and apply transform."""
    x = rect.get("x", 0)
    y = rect.get("y", 0)
    w = rect.get("w", 0)
    h = rect.get("h", 0)
    x1, y1, x2, y2 = transform_bbox(x, y, x + w, y + h)
    return [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]


# ---------------------------------------------------------------------------
# Format converters
# ---------------------------------------------------------------------------

def to_layoutlmv3(
    annotations: dict,
    image_path: str,
    img_w: int,
    img_h: int,
) -> dict:
    """Convert annotations to LayoutLMv3 training format.

    Returns:
        {
            "image_path": str,
            "words": [str, ...],
            "bboxes": [[x1,y1,x2,y2], ...],  # normalized 0-1000
            "labels": [str, ...],  # semantic label per word
        }
    """
    words = []
    bboxes = []
    labels = []

    for w in annotations["words"]:
        words.append(w["text"])
        bboxes.append(w["normalized_bbox"])
        # Label format: B-{field_name} for first word, I-{field_name} for rest
        # Category prefix: L_ for label, V_ for value
        prefix = "L" if w["category"] == "label" else "V"
        labels.append(f"{prefix}_{w['field_name']}")

    return {
        "image_path": image_path,
        "width": img_w,
        "height": img_h,
        "words": words,
        "bboxes": bboxes,
        "labels": labels,
    }


def to_ocr(annotations: dict) -> list[dict]:
    """Convert annotations to OCR training format.

    Returns list of text regions:
        [{"text": str, "bbox": [x1,y1,x2,y2], "category": "label"|"value"}, ...]
    """
    regions = []
    for w in annotations["words"]:
        regions.append({
            "text": w["text"],
            "bbox": w["bbox"],
            "category": w["category"],
        })
    return regions


def to_key_value(annotations: dict) -> list[dict]:
    """Convert annotations to key-value extraction format.

    Returns list of key-value pairs with bounding boxes:
        [{"key": str, "key_bbox": [...], "value": str, "value_bbox": [...],
          "field_name": str, "block_type": str}, ...]
    """
    pairs = []
    for field in annotations["fields"]:
        if field["value"] is None:
            continue  # label-only, no key-value pair

        pairs.append({
            "key": field["label"]["text"],
            "key_bbox": field["label"]["bbox"],
            "value": field["value"]["text"],
            "value_bbox": field["value"]["bbox"],
            "field_name": field["field_name"],
            "field_type": field["field_type"],
            "block_type": field["block_type"],
        })
    return pairs
