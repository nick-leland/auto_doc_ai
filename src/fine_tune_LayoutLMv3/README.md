# LayoutLMv3 notebooks
In this directory, you can find notebooks that illustrate how to use LayoutLMv3 both for fine-tuning on custom data as well as inference.

## Synthetic title workflow

Seeded synthetic benchmark summary (`seed=42`):

- Baseline `Tesseract -> LayoutLMv3 (FUNSD)` on the held-out test split: seqeval F1 `0.3888`, token accuracy `0.4750`
- OCR-aware fine-tuned `Tesseract -> LayoutLMv3` on the same split: seqeval F1 `0.7819`, token accuracy `0.8912`
- The successful run trained on OCR-tokenized synthetic pages, not on perfect ground-truth tokens

Saved runs:

- `runs/baselines/layoutlmv3_funsd_tesseract_test_seed42.json`
- `runs/layoutlmv3-funsd-tesseract-seed42/metrics_summary.json`

This repo now includes two runnable scripts for the generated `dataset/` format:

```bash
# OCR baseline + zero-shot LayoutLMv3 baseline on the held-out test split
./.venv/bin/python src/fine_tune_LayoutLMv3/evaluate_baselines.py \
  --dataset-dir dataset \
  --model-dir src/fine_tune_LayoutLMv3/models/layoutlmv3-funsd \
  --split test \
  --ocr-source tesseract

# Same evaluation path using PaddleOCR instead of Tesseract
./.venv/bin/python src/fine_tune_LayoutLMv3/evaluate_baselines.py \
  --dataset-dir dataset \
  --model-dir src/fine_tune_LayoutLMv3/models/layoutlmv3-funsd \
  --split test \
  --ocr-source paddleocr

# Fine-tune the FUNSD checkpoint on the synthetic dataset
./.venv/bin/python src/fine_tune_LayoutLMv3/finetune_layoutlmv3.py \
  --dataset-dir dataset \
  --output-dir runs/layoutlmv3-funsd-synth \
  --num-train-epochs 5

# Re-evaluate the fine-tuned model on the same OCR-backed test split
./.venv/bin/python src/fine_tune_LayoutLMv3/evaluate_baselines.py \
  --dataset-dir dataset \
  --model-dir runs/layoutlmv3-funsd-synth/best_model \
  --split test \
  --ocr-source tesseract

# Run a single-page local Tesseract -> LayoutLMv3 baseline pipeline
./.venv/bin/python src/fine_tune_LayoutLMv3/run_tesseract_layoutlmv3_baseline.py \
  --image dataset/images_clean/title_0000_front.png

# Run a single-page local Tesseract -> fine-tuned LayoutLMv3 pipeline
./.venv/bin/python src/fine_tune_LayoutLMv3/run_tesseract_layoutlmv3_finetuned.py \
  --image dataset/images_clean/title_0000_front.png

# Evaluate a real-world validation folder locally against the baseline model
./.venv/bin/python src/fine_tune_LayoutLMv3/evaluate_local_validation_baseline.py \
  --data-dir real_validation/

# Evaluate the same folder locally against the OCR-aware fine-tuned model
./.venv/bin/python src/fine_tune_LayoutLMv3/evaluate_local_validation_finetuned.py \
  --data-dir real_validation/

# Launch a local browser-based annotation tool for a validation folder
./.venv/bin/python src/fine_tune_LayoutLMv3/annotate_validation_set.py \
  --data-dir real_validation/
```

Notes:

- `evaluate_baselines.py` reports OCR quality on its own and LayoutLMv3 quality on the same split.
- `--ocr-source` accepts `tesseract`, `paddleocr`, or `ground_truth`.
- The synthetic labels are mapped into a FUNSD-style tag space: `HEADER`, `QUESTION`, `ANSWER`, and `O`.
- The local FUNSD checkpoint does not ship semantic `id2label` names, so the scripts assume the standard FUNSD BIO order when evaluating and fine-tuning.
- `paddleocr` is optional and is not currently installed in this environment.
- `tesseract` runs locally through the system `tesseract` binary; no external OCR API is used by these scripts.

## Real-world validation folder

Use this structure for private, local-only validation data:

```text
real_validation/
  images/
    page_0001.png
    page_0002.jpg
  labels/
    page_0001.json
    page_0002.json
```

Each label file can be either:

- a synthetic-style annotation JSON from `dataset/annotations/`
- or a simple token-label JSON:

```json
{
  "image_size": [1200, 1560],
  "tokens": [
    {"text": "CERTIFICATE", "bbox": [62, 22, 261, 65], "label": "B-HEADER"},
    {"text": "TITLE", "bbox": [811, 22, 943, 65], "label": "I-HEADER"}
  ]
}
```

A ready-to-copy template lives at `src/fine_tune_LayoutLMv3/real_validation_label_template.json`.

Notes:

- `bbox` values may be normalized `[0..1000]` or absolute pixel coordinates if `image_size` is provided.
- Labels should use the FUNSD-style tag space used in this repo: `O`, `B-HEADER`, `I-HEADER`, `B-QUESTION`, `I-QUESTION`, `B-ANSWER`, `I-ANSWER`.
- `--predictions-dir` will save one local JSON prediction file per image for review.
- `annotate_validation_set.py` runs a local web app on `127.0.0.1` only, seeds boxes from local Tesseract, and saves edited labels into `labels/<image_stem>.json`.

## Important note

LayoutLMv3 models are capable of getting > 90% F1 on FUNSD. This is thanks to the use of segment position embeddings, as opposed to word-level position embeddings, inspired by [StructuralLM](https://arxiv.org/abs/2105.11210). This means that words belonging to the same "segment" (let's say, an address) get the same bounding box coordinates, and thus the same 2D position embeddings. 

Most OCR engines (like Google's Tesseract) are able to identify segments as explained in [this thread](https://github.com/microsoft/unilm/issues/838) by the LayoutLMv3 author.

For the FUNSD dataset, segments were created based on the labels as seen [here](https://huggingface.co/datasets/nielsr/funsd-layoutlmv3/blob/main/funsd-layoutlmv3.py#L140).

It's always advised to use segment position embeddings over word-level position embeddings, as it gives quite a boost in performance.

## Training tips

Note that LayoutLMv3 is identical to LayoutLMv2 in terms of training/inference, except that:
* images need to be resized and normalized, such that they are `pixel_values` of shape `(batch_size, num_channels, heigth, width)`. The channels need to be in RGB format. This was not the case for LayoutLMv2, which expected the channels in BGR format (due to its Detectron2 visual backbone), and normalized the images internally.
* tokenization of text is based on RoBERTa, hence byte-level Byte-Pair-Encoding. This in contrast to LayoutLMv2, which used BERT-like WordPiece tokenization.

Because of this, I've created a new `LayoutLMv3Processor`, which combines a `LayoutLMv3ImageProcessor` (for the image modality) and a `LayoutLMv3TokenizerFast` (for the text modality) into one. Usage is identical to its predecessor [`LayoutLMv2Processor`](https://huggingface.co/docs/transformers/model_doc/layoutlmv2#usage-layoutlmv2processor).

The full documentation can be found [here](https://huggingface.co/transformers/model_doc/layoutlmv3.html).

The models on the hub can be found [here](https://huggingface.co/models?search=layoutlmv3).
