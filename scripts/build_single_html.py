#!/usr/bin/env python3
"""
Escuta A1 — Offline Single-HTML Bundler
Combines `index.html`, `css/styles.css`, `js/*.js`, and `lessons/*/lesson.json`
into `dist/escuta-a1-offline.html` for standalone offline viewing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def build_offline_bundle() -> Path:
    html = (config.PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    css = (config.PROJECT_ROOT / "css" / "styles.css").read_text(encoding="utf-8")

    index_data = json.loads(config.CATALOG_PATH.read_text(encoding="utf-8"))
    lessons_map = {}
    for entry in index_data.get("lessons", []):
        lpath = config.PROJECT_ROOT / entry["path"]
        if lpath.exists():
            lessons_map[entry["id"]] = json.loads(lpath.read_text(encoding="utf-8"))

    embedded_script = (
        "<script>\nwindow.ESCUTA_EMBEDDED_DATA = "
        + json.dumps({"index": index_data, "lessons": lessons_map}, ensure_ascii=False)
        + ";\n</script>"
    )

    js_files = ["srs-storage.js", "audio-player.js", "recorder.js", "app.js"]
    combined_js = "\n".join(
        (config.PROJECT_ROOT / "js" / fname).read_text(encoding="utf-8")
        for fname in js_files
    )

    html = html.replace(
        '<link rel="stylesheet" href="css/styles.css" />',
        f"<style>\n{css}\n</style>",
    )
    for fname in js_files:
        html = html.replace(f'<script src="js/{fname}"></script>', "")

    html = html.replace(
        "</body>",
        f"{embedded_script}\n<script>\n{combined_js}\n</script>\n</body>",
    )

    dist_dir = config.PROJECT_ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    out_file = dist_dir / "escuta-a1-offline.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"[build_single_html] オフライン単一HTMLを生成しました: {out_file}")
    return out_file


if __name__ == "__main__":
    build_offline_bundle()
