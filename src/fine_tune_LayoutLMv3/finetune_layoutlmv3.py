from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup

from experiment_utils import (
    ID2LABEL,
    LABEL2ID,
    LayoutLMTokenDataset,
    compute_trainer_metrics,
    load_examples,
    load_model,
    load_processor,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune LayoutLMv3 on the synthetic title dataset without Trainer/accelerate.",
    )
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("src/fine_tune_LayoutLMv3/models/layoutlmv3-funsd"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/layoutlmv3-funsd-synth"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--ocr-source",
        choices=["ground_truth", "tesseract", "paddleocr"],
        default="ground_truth",
        help="Token source used for training/evaluation examples.",
    )
    parser.add_argument(
        "--ocr-cache-dir",
        type=Path,
        default=None,
        help="Optional cache directory for OCR-derived tokens and boxes.",
    )
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-val-samples", type=int, default=None)
    parser.add_argument("--max-test-samples", type=int, default=None)
    parser.add_argument("--num-train-epochs", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--train-batch-size", type=int, default=2)
    parser.add_argument("--eval-batch-size", type=int, default=2)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--device", type=str, default=None)
    return parser.parse_args()


def collate_batch(items: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
    return {
        key: torch.stack([item[key] for item in items], dim=0)
        for key in items[0]
    }


def evaluate_dataloader(
    model,
    dataloader: DataLoader,
    device: str,
) -> tuple[dict[str, float], float]:
    model.eval()
    logits_list = []
    labels_list = []
    losses = []

    with torch.no_grad():
        for batch in dataloader:
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            losses.append(float(outputs.loss.detach().cpu()))
            logits_list.append(outputs.logits.detach().cpu().numpy())
            labels_list.append(batch["labels"].detach().cpu().numpy())

    logits = np.concatenate(logits_list, axis=0)
    labels = np.concatenate(labels_list, axis=0)
    metrics = compute_trainer_metrics((logits, labels))
    metrics["loss"] = float(np.mean(losses)) if losses else 0.0
    return metrics, metrics["loss"]


def save_model_bundle(model, processor, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model.config.id2label = ID2LABEL
    model.config.label2id = LABEL2ID
    model.save_pretrained(output_dir)
    processor.save_pretrained(output_dir)


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    ocr_cache_dir = args.ocr_cache_dir
    if ocr_cache_dir is None and args.ocr_source != "ground_truth":
        ocr_cache_dir = args.dataset_dir / "ocr_cache" / args.ocr_source

    train_examples = load_examples(
        dataset_dir=args.dataset_dir,
        split="train",
        seed=args.seed,
        max_samples=args.max_train_samples,
        ocr_source=args.ocr_source,
        ocr_cache_dir=ocr_cache_dir,
    )
    val_examples = load_examples(
        dataset_dir=args.dataset_dir,
        split="val",
        seed=args.seed,
        max_samples=args.max_val_samples,
        ocr_source=args.ocr_source,
        ocr_cache_dir=ocr_cache_dir,
    )
    test_examples = load_examples(
        dataset_dir=args.dataset_dir,
        split="test",
        seed=args.seed,
        max_samples=args.max_test_samples,
        ocr_source=args.ocr_source,
        ocr_cache_dir=ocr_cache_dir,
    )

    if not train_examples:
        raise SystemExit("Training split is empty.")
    if not val_examples:
        raise SystemExit("Validation split is empty.")

    processor = load_processor(args.model_dir)
    model = load_model(args.model_dir)
    model.config.id2label = ID2LABEL
    model.config.label2id = LABEL2ID

    train_dataset = LayoutLMTokenDataset(train_examples, processor)
    val_dataset = LayoutLMTokenDataset(val_examples, processor)
    test_dataset = LayoutLMTokenDataset(test_examples, processor)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.train_batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(args.seed),
        collate_fn=collate_batch,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.eval_batch_size,
        shuffle=False,
        collate_fn=collate_batch,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=args.eval_batch_size,
        shuffle=False,
        collate_fn=collate_batch,
    )

    if args.device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    model.to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    total_steps = max(len(train_loader) * args.num_train_epochs, 1)
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_steps,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    best_dir = args.output_dir / "best_model"
    best_val_f1 = -math.inf
    global_step = 0

    for epoch in range(1, args.num_train_epochs + 1):
        model.train()
        running_loss = 0.0

        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)

            global_step += 1
            running_loss += float(loss.detach().cpu())

            if global_step % args.logging_steps == 0:
                avg_loss = running_loss / args.logging_steps
                print(
                    f"epoch={epoch} step={global_step} "
                    f"train_loss={avg_loss:.4f}"
                )
                running_loss = 0.0

        val_metrics, _ = evaluate_dataloader(model, val_loader, device)
        print(
            f"epoch={epoch} val_seqeval_f1={val_metrics['seqeval_f1']:.4f} "
            f"val_token_accuracy={val_metrics['token_accuracy']:.4f}"
        )

        if val_metrics["seqeval_f1"] > best_val_f1:
            best_val_f1 = val_metrics["seqeval_f1"]
            save_model_bundle(model, processor, best_dir)

    final_dir = args.output_dir / "final_model"
    save_model_bundle(model, processor, final_dir)

    best_model = load_model(best_dir)
    best_model.to(device)

    val_metrics, _ = evaluate_dataloader(best_model, val_loader, device)
    test_metrics, _ = evaluate_dataloader(best_model, test_loader, device)

    summary = {
        "device": device,
        "seed": args.seed,
        "ocr_source": args.ocr_source,
        "ocr_cache_dir": str(ocr_cache_dir) if ocr_cache_dir is not None else None,
        "train_examples": len(train_examples),
        "val_examples": len(val_examples),
        "test_examples": len(test_examples),
        "best_model_dir": str(best_dir),
        "final_model_dir": str(final_dir),
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
    }

    with open(args.output_dir / "metrics_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
