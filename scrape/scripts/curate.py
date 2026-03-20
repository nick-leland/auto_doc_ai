"""
Image curation tool — Tinder-style swipe through scraped images.

Usage:
    python curate.py [path/to/scraped_vehicle_titles]

Controls:
    → (Right arrow) or D = Keep (good image)
    ← (Left arrow) or A  = Reject (bad image, moved to _rejected/)
    Z                     = Undo last action
    Q                     = Quit and save progress

Opens in your browser at http://localhost:8505
"""

import csv
import json
import os
import shutil
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, quote
import webbrowser

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PORT = 8505
REJECTED_DIR = "_rejected"
PROGRESS_FILE = ".curate_progress.json"


def find_all_images(base_dir: str) -> list[dict]:
    """Find all images in state subdirectories."""
    images = []
    base = Path(base_dir)
    for state_dir in sorted(base.iterdir()):
        if not state_dir.is_dir() or state_dir.name.startswith(("_", ".")):
            continue
        for img_file in sorted(state_dir.iterdir()):
            if img_file.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}:
                images.append({
                    "path": str(img_file),
                    "rel": str(img_file.relative_to(base)),
                    "state": state_dir.name.replace("_", " "),
                    "filename": img_file.name,
                })
    return images


def load_progress(base_dir: str) -> dict:
    p = Path(base_dir) / PROGRESS_FILE
    if p.exists():
        return json.loads(p.read_text())
    return {"index": 0, "kept": [], "rejected": []}


def save_progress(base_dir: str, progress: dict):
    p = Path(base_dir) / PROGRESS_FILE
    p.write_text(json.dumps(progress, indent=2))


HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Vehicle Title Curator</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #1a1a1a; color: #fff; font-family: -apple-system, system-ui, sans-serif;
    display: flex; flex-direction: column; height: 100vh; overflow: hidden;
    user-select: none;
}
.header {
    padding: 12px 20px; background: #222; display: flex; justify-content: space-between;
    align-items: center; border-bottom: 1px solid #333; flex-shrink: 0;
}
.header h1 { font-size: 18px; font-weight: 600; }
.stats { font-size: 14px; color: #999; display: flex; gap: 16px; }
.stats span { color: #fff; }
.progress-bar {
    height: 3px; background: #333; flex-shrink: 0;
}
.progress-fill { height: 100%; background: #4ade80; transition: width 0.3s; }
.main {
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 20px; position: relative; overflow: hidden;
}
.state-label {
    font-size: 14px; color: #999; margin-bottom: 8px;
}
.image-container {
    max-width: 90vw; max-height: calc(100vh - 200px); position: relative;
    transition: transform 0.3s ease, opacity 0.3s ease;
}
.image-container img {
    max-width: 100%; max-height: calc(100vh - 200px); object-fit: contain;
    border-radius: 8px; box-shadow: 0 4px 24px rgba(0,0,0,0.5);
}
.image-container.swipe-left {
    transform: translateX(-120%) rotate(-15deg); opacity: 0;
}
.image-container.swipe-right {
    transform: translateX(120%) rotate(15deg); opacity: 0;
}
.controls {
    padding: 16px 20px; background: #222; border-top: 1px solid #333;
    display: flex; justify-content: center; gap: 20px; align-items: center;
    flex-shrink: 0;
}
.btn {
    border: none; border-radius: 50%; width: 64px; height: 64px; cursor: pointer;
    font-size: 28px; display: flex; align-items: center; justify-content: center;
    transition: transform 0.15s;
}
.btn:hover { transform: scale(1.1); }
.btn:active { transform: scale(0.95); }
.btn-reject { background: #ef4444; color: white; }
.btn-undo { background: #555; color: white; width: 48px; height: 48px; font-size: 20px; }
.btn-keep { background: #22c55e; color: white; }
.hint { font-size: 12px; color: #666; }
.overlay {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    font-size: 72px; font-weight: 800; opacity: 0; pointer-events: none;
    transition: opacity 0.2s;
}
.overlay.show { opacity: 0.7; }
.overlay.keep { color: #22c55e; }
.overlay.reject { color: #ef4444; }
.done {
    text-align: center; padding: 40px;
}
.done h2 { font-size: 32px; margin-bottom: 16px; }
.done p { color: #999; font-size: 18px; }
</style>
</head>
<body>

<div class="header">
    <h1>Vehicle Title Curator</h1>
    <div class="stats">
        <div><span id="current">0</span> / <span id="total">0</span></div>
        <div>Kept: <span id="kept" style="color:#22c55e">0</span></div>
        <div>Rejected: <span id="rejected" style="color:#ef4444">0</span></div>
    </div>
</div>
<div class="progress-bar"><div class="progress-fill" id="progress"></div></div>

<div class="main" id="main">
    <div class="state-label" id="state-label"></div>
    <div class="image-container" id="img-container">
        <img id="img" src="" alt="">
    </div>
    <div class="overlay keep" id="overlay-keep">KEEP</div>
    <div class="overlay reject" id="overlay-reject">NOPE</div>
</div>

<div class="controls">
    <div style="text-align:center">
        <button class="btn btn-reject" onclick="reject()" title="Reject (← or A)">✕</button>
        <div class="hint">← A</div>
    </div>
    <div style="text-align:center">
        <button class="btn btn-undo" onclick="undo()" title="Undo (Z)">↩</button>
        <div class="hint">Z</div>
    </div>
    <div style="text-align:center">
        <button class="btn btn-keep" onclick="keep()" title="Keep (→ or D)">♥</button>
        <div class="hint">→ D</div>
    </div>
</div>

<script>
let images = [];
let index = 0;
let keptCount = 0;
let rejectedCount = 0;
let busy = false;

async function init() {
    const resp = await fetch('/api/state');
    const data = await resp.json();
    images = data.images;
    index = data.index;
    keptCount = data.kept;
    rejectedCount = data.rejected;
    document.getElementById('total').textContent = images.length;
    showCurrent();
}

function showCurrent() {
    document.getElementById('current').textContent = index + 1;
    document.getElementById('kept').textContent = keptCount;
    document.getElementById('rejected').textContent = rejectedCount;
    document.getElementById('progress').style.width =
        ((index / images.length) * 100) + '%';

    if (index >= images.length) {
        document.getElementById('main').innerHTML =
            '<div class="done"><h2>All done!</h2><p>' + keptCount + ' kept, ' +
            rejectedCount + ' rejected out of ' + images.length + '</p>' +
            '<p style="margin-top:12px">You can close this tab. Progress is saved.</p></div>';
        return;
    }

    const img = images[index];
    document.getElementById('state-label').textContent = img.state + ' — ' + img.filename;
    document.getElementById('img').src = '/image/' + encodeURIComponent(img.rel);

    const container = document.getElementById('img-container');
    container.className = 'image-container';
}

async function keep() {
    if (busy || index >= images.length) return;
    busy = true;
    await flash('keep');
    await fetch('/api/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'keep', index: index})
    });
    keptCount++;
    index++;
    showCurrent();
    busy = false;
}

async function reject() {
    if (busy || index >= images.length) return;
    busy = true;
    await flash('reject');
    await fetch('/api/action', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'reject', index: index})
    });
    rejectedCount++;
    index++;
    showCurrent();
    busy = false;
}

async function undo() {
    if (busy || index <= 0) return;
    busy = true;
    const resp = await fetch('/api/undo', {method: 'POST'});
    const data = await resp.json();
    index = data.index;
    keptCount = data.kept;
    rejectedCount = data.rejected;
    showCurrent();
    busy = false;
}

function flash(type) {
    return new Promise(resolve => {
        const container = document.getElementById('img-container');
        const overlay = document.getElementById('overlay-' + type);
        overlay.classList.add('show');
        container.classList.add(type === 'keep' ? 'swipe-right' : 'swipe-left');
        setTimeout(() => {
            overlay.classList.remove('show');
            resolve();
        }, 250);
    });
}

document.addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') keep();
    else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') reject();
    else if (e.key === 'z' || e.key === 'Z') undo();
    else if (e.key === 'q' || e.key === 'Q') window.close();
});

init();
</script>
</body>
</html>"""


class CurateHandler(SimpleHTTPRequestHandler):
    base_dir = ""
    images = []
    progress = {}

    def log_message(self, format, *args):
        pass  # silence request logs

    def do_GET(self):
        if self.path == "/":
            self._send_html(HTML_PAGE)
        elif self.path == "/api/state":
            data = {
                "images": self.__class__.images,
                "index": self.__class__.progress["index"],
                "kept": len(self.__class__.progress["kept"]),
                "rejected": len(self.__class__.progress["rejected"]),
            }
            self._send_json(data)
        elif self.path.startswith("/image/"):
            rel = unquote(self.path[7:])
            filepath = Path(self.__class__.base_dir) / rel
            if filepath.exists():
                self.send_response(200)
                ext = filepath.suffix.lower()
                ct = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp",
                    ".bmp": "image/bmp",
                }.get(ext, "application/octet-stream")
                self.send_header("Content-Type", ct)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(filepath.read_bytes())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/action":
            idx = body["index"]
            action = body["action"]
            img = self.__class__.images[idx]

            if action == "reject":
                # Move file to _rejected/State/
                src = Path(img["path"])
                if src.exists():
                    rej_dir = Path(self.__class__.base_dir) / REJECTED_DIR / Path(img["rel"]).parent.name
                    rej_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(rej_dir / img["filename"]))
                self.__class__.progress["rejected"].append(img["rel"])
            else:
                self.__class__.progress["kept"].append(img["rel"])

            self.__class__.progress["index"] = idx + 1
            save_progress(self.__class__.base_dir, self.__class__.progress)
            self._send_json({"ok": True})

        elif self.path == "/api/undo":
            prog = self.__class__.progress
            if prog["index"] > 0:
                prog["index"] -= 1
                idx = prog["index"]
                img = self.__class__.images[idx]

                # Check if it was rejected (need to move back)
                if prog["rejected"] and prog["rejected"][-1] == img["rel"]:
                    prog["rejected"].pop()
                    rej_path = Path(self.__class__.base_dir) / REJECTED_DIR / Path(img["rel"]).parent.name / img["filename"]
                    if rej_path.exists():
                        orig_path = Path(img["path"])
                        orig_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(rej_path), str(orig_path))
                elif prog["kept"] and prog["kept"][-1] == img["rel"]:
                    prog["kept"].pop()

                save_progress(self.__class__.base_dir, self.__class__.progress)

            self._send_json({
                "index": prog["index"],
                "kept": len(prog["kept"]),
                "rejected": len(prog["rejected"]),
            })
        else:
            self.send_error(404)

    def _send_html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "scraped_vehicle_titles"

    if not Path(base_dir).exists():
        print(f"Directory not found: {base_dir}")
        sys.exit(1)

    images = find_all_images(base_dir)
    progress = load_progress(base_dir)

    print(f"Found {len(images)} images across {len(set(i['state'] for i in images))} states")
    if progress["index"] > 0:
        print(f"Resuming from image {progress['index']+1} ({len(progress['kept'])} kept, {len(progress['rejected'])} rejected)")

    CurateHandler.base_dir = base_dir
    CurateHandler.images = images
    CurateHandler.progress = progress

    server = HTTPServer(("localhost", PORT), CurateHandler)
    url = f"http://localhost:{PORT}"
    print(f"\nOpening {url} in your browser...")
    print("Controls: → keep, ← reject, Z undo, Q quit")
    print("Press Ctrl+C to stop.\n")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\nSaved. {len(progress['kept'])} kept, {len(progress['rejected'])} rejected.")
        save_progress(base_dir, progress)
        server.server_close()


if __name__ == "__main__":
    main()
