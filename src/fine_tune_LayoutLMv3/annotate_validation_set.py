from __future__ import annotations

import argparse
import json
import mimetypes
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from experiment_utils import (
    denormalize_bbox,
    load_truth_labeled_tokens,
    normalize_bbox,
    run_ocr,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}
STATIC_DIR = Path(__file__).resolve().parent / "annotator_static"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a local annotation server for real-world validation images.",
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def list_images(images_dir: Path) -> list[Path]:
    return sorted(
        path for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _inverse_rotate_point(
    x: float,
    y: float,
    original_width: int,
    original_height: int,
    rotation: int,
) -> tuple[float, float]:
    rotation = rotation % 360
    if rotation == 0:
        return x, y
    if rotation == 90:
        return y, original_height - x
    if rotation == 180:
        return original_width - x, original_height - y
    if rotation == 270:
        return original_width - y, x
    raise ValueError(f"Unsupported rotation: {rotation}")


def _map_rotated_bbox_to_original(
    bbox: list[int],
    rotated_size: tuple[int, int],
    original_size: tuple[int, int],
    rotation: int,
) -> list[int]:
    rotated_width, rotated_height = rotated_size
    original_width, original_height = original_size
    x1, y1, x2, y2 = denormalize_bbox(bbox, rotated_width, rotated_height)
    corners = [
        (x1, y1),
        (x2, y1),
        (x1, y2),
        (x2, y2),
    ]
    mapped = [
        _inverse_rotate_point(x, y, original_width, original_height, rotation)
        for x, y in corners
    ]
    xs = [point[0] for point in mapped]
    ys = [point[1] for point in mapped]
    return normalize_bbox(
        [min(xs), min(ys), max(xs), max(ys)],
        original_width,
        original_height,
    )


def _run_tesseract_with_rotation(
    image_path: Path,
    rotation: int,
) -> tuple[list[str], list[list[int]], tuple[int, int]]:
    from PIL import Image

    with Image.open(image_path) as image:
        original_size = image.size
        if rotation % 360 == 0:
            words, boxes, _ = run_ocr(image_path, "tesseract")
            return words, boxes, original_size

        rotated = image.rotate(-rotation, expand=True)
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
            rotated.save(temp_file.name)
            words, rotated_boxes, rotated_size = run_ocr(Path(temp_file.name), "tesseract")

    boxes = [
        _map_rotated_bbox_to_original(
            bbox,
            rotated_size=rotated_size,
            original_size=original_size,
            rotation=rotation,
        )
        for bbox in rotated_boxes
    ]
    return words, boxes, original_size


def build_default_label_doc(image_path: Path, rotation: int = 0) -> dict:
    words, boxes, image_size = _run_tesseract_with_rotation(image_path, rotation)
    return {
        "doc_id": image_path.stem,
        "image_size": list(image_size),
        "rotation": rotation,
        "tokens": [
            {"text": word, "bbox": box, "label": "O"}
            for word, box in zip(words, boxes)
        ],
    }


def build_editable_label_doc(label_path: Path, image_path: Path) -> dict:
    with open(label_path) as fh:
        payload = json.load(fh)
    truth = load_truth_labeled_tokens(label_path, image_path=image_path)
    with ImageSize(image_path) as image_size:
        return {
            "doc_id": image_path.stem,
            "image_size": list(image_size),
            "rotation": int(payload.get("rotation", 0)) % 360,
            "tokens": [
                {
                    "text": word,
                    "bbox": bbox,
                    "label": label,
                }
                for word, bbox, label in zip(
                    truth["words"],
                    truth["bboxes"],
                    truth["labels"],
                )
            ],
        }


class ImageSize:
    def __init__(self, image_path: Path):
        self.image_path = image_path
        self._size: tuple[int, int] | None = None

    def __enter__(self) -> tuple[int, int]:
        from PIL import Image

        with Image.open(self.image_path) as image:
            self._size = image.size
        return self._size

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def make_handler(data_dir: Path):
    images_dir = data_dir / "images"
    labels_dir = data_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict | list, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_bytes(self, payload: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _safe_name(self, raw_name: str) -> str:
            name = Path(unquote(raw_name)).name
            if not name:
                raise ValueError("Missing file name.")
            return name

        def _read_static(self, relative_path: str) -> tuple[bytes, str]:
            file_path = STATIC_DIR / relative_path
            if not file_path.exists():
                raise FileNotFoundError(relative_path)
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            return file_path.read_bytes(), content_type

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/":
                body, content_type = self._read_static("index.html")
                self._send_bytes(body, content_type)
                return
            if path == "/app.js":
                body, content_type = self._read_static("app.js")
                self._send_bytes(body, content_type)
                return
            if path == "/styles.css":
                body, content_type = self._read_static("styles.css")
                self._send_bytes(body, content_type)
                return
            if path == "/api/images":
                payload = []
                for image_path in list_images(images_dir):
                    label_path = labels_dir / f"{image_path.stem}.json"
                    payload.append(
                        {
                            "name": image_path.name,
                            "label_exists": label_path.exists(),
                        }
                    )
                self._send_json(payload)
                return
            if path.startswith("/api/image/"):
                try:
                    name = self._safe_name(path.removeprefix("/api/image/"))
                    image_path = images_dir / name
                    if not image_path.exists():
                        raise FileNotFoundError(name)
                    content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
                    self._send_bytes(image_path.read_bytes(), content_type)
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                return
            if path.startswith("/api/label/"):
                try:
                    name = self._safe_name(path.removeprefix("/api/label/"))
                    image_path = images_dir / name
                    if not image_path.exists():
                        raise FileNotFoundError(f"Image not found: {image_path}")
                    label_path = labels_dir / f"{Path(name).stem}.json"
                    query = parse_qs(parsed.query)
                    reload_ocr = query.get("reload", ["0"])[0] == "1"
                    rotation = int(query.get("rotation", ["0"])[0]) % 360
                    if label_path.exists() and not reload_ocr:
                        payload = build_editable_label_doc(label_path, image_path)
                    else:
                        payload = build_default_label_doc(image_path, rotation=rotation)
                    self._send_json(payload)
                except Exception as exc:  # noqa: BLE001
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith("/api/label/"):
                self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
                return

            try:
                name = self._safe_name(path.removeprefix("/api/label/"))
                image_path = images_dir / name
                if not image_path.exists():
                    raise FileNotFoundError(f"Image not found: {image_path}")

                content_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))

                output_doc = {
                    "doc_id": payload.get("doc_id") or image_path.stem,
                    "image_size": payload.get("image_size"),
                    "rotation": int(payload.get("rotation", 0)) % 360,
                    "tokens": payload.get("tokens", []),
                }
                label_path = labels_dir / f"{image_path.stem}.json"
                with open(label_path, "w") as fh:
                    json.dump(output_doc, fh, indent=2)

                self._send_json({"ok": True, "label_path": str(label_path)})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.data_dir))
    print(f"Annotation server: http://{args.host}:{args.port}")
    print(f"Data directory: {args.data_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
