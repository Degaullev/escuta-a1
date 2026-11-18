#!/usr/bin/env python3
"""
Escuta A1 — Local Management & Static Viewer Server
- Serves the static web app (with HTTP Range support for iOS Safari MP3/MP4 seeking)
- Exposes `/api/health`, `/api/generate`, and `/api/jobs/<id>` so the "✨ AI作成" button
  can orchestrate `generate_script -> synthesize_audio -> audit_quality -> generate_visuals`
  directly from the browser on localhost.
- Works out-of-the-box with Python standard library (zero pip install required to preview!)
  and also exports a FastAPI `app` object if `uvicorn scripts.server:app` is preferred.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _sanitize_lesson_id(raw_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_id.strip()).strip("-").lower()
    return cleaned or f"lesson-{uuid.uuid4().hex[:6]}"


def _run_pipeline_job(job_id: str, params: dict[str, Any]) -> None:
    def log(msg: str) -> None:
        with JOBS_LOCK:
            JOBS[job_id]["logs"].append(msg)

    try:
        topic = str(params.get("topic", "")).strip()
        lesson_id = _sanitize_lesson_id(str(params.get("lessonId", "")))
        line_count = max(3, int(params.get("lineCount", 9)))
        scene_count = max(1, min(6, round(line_count / 4) or 2))
        dry_run = bool(params.get("dryRun", False))
        limit = int(params.get("limit", 0))
        with_visuals = bool(params.get("withVisuals", False))
        with_video = bool(params.get("withVideo", False))

        py = sys.executable
        scripts_dir = Path(__file__).resolve().parent

        steps: list[tuple[str, list[str]]] = [
            (
                "① 台本・記号接地データ生成 (generate_script.py)",
                [
                    py,
                    str(scripts_dir / "generate_script.py"),
                    "--topic",
                    topic,
                    "--lesson-id",
                    lesson_id,
                    "--scenes",
                    str(scene_count),
                    "--lines",
                    str(line_count),
                ]
                + (["--dry-run"] if dry_run else []),
            ),
            (
                "② Gemini 3.8 TTS 音声合成 (synthesize_audio.py)",
                [
                    py,
                    str(scripts_dir / "synthesize_audio.py"),
                    "--lesson-id",
                    lesson_id,
                ]
                + (["--limit", str(limit)] if limit > 0 else [])
                + (["--dry-run"] if dry_run else []),
            ),
            (
                "③ Whisper＋Gemini 二重品質監査 (audit_quality.py)",
                [
                    py,
                    str(scripts_dir / "audit_quality.py"),
                    "--lesson-id",
                    lesson_id,
                ]
                + (["--limit", str(limit)] if limit > 0 else [])
                + (["--dry-run"] if dry_run else []),
            ),
        ]

        if with_visuals or with_video:
            vis_cmd = [
                py,
                str(scripts_dir / "generate_visuals.py"),
                "--lesson-id",
                lesson_id,
            ]
            if with_video:
                vis_cmd.append("--with-video")
            if dry_run:
                vis_cmd.append("--dry-run")
            steps.append(("④ 一貫キャラ画像・情景動画生成 (generate_visuals.py)", vis_cmd))

        for title, cmd in steps:
            log(f"▶ {title}")
            proc = subprocess.Popen(
                cmd,
                cwd=str(config.PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log("  " + line.rstrip())
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"{title} が終了コード {code} で失敗しました。")

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["lessonId"] = lesson_id
        log(f"✅ すべての工程が完了しました！ (lessons/{lesson_id}/lesson.json)")
    except Exception as exc:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
        log(f"❌ エラー: {exc}")


class EscutaHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Serves static files with HTTP Range support + `/api/*` endpoints."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(config.PROJECT_ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Guard against BrokenPipeError if background task log pipe closes
        try:
            sys.stderr.write(f"[server] {self.address_string()} - {fmt % args}\n")
        except OSError:
            pass

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            has_key = bool(
                config.GEMINI_API_KEY
                and config.GEMINI_API_KEY != "your_gemini_api_key_here"
            )
            self._send_json(
                200,
                {
                    "ok": True,
                    "mode": "local-admin",
                    "apiKeyConfigured": has_key,
                    "models": {
                        "text": config.TEXT_MODEL,
                        "tts": config.TTS_MODEL,
                        "video": config.VIDEO_MODEL,
                    },
                },
            )
            return

        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/api/jobs/", 1)[1]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self._send_json(404, {"error": "Job not found"})
            else:
                self._send_json(200, job)
            return

        # Support HTTP Range requests for iOS Safari <audio> / <video> seeking
        range_header = self.headers.get("Range")
        if range_header:
            local_path = Path(self.translate_path(parsed.path))
            if local_path.is_file():
                self._serve_range_file(local_path, range_header)
                return

        super().do_GET()

    def _serve_range_file(self, file_path: Path, range_header: str) -> None:
        size = file_path.stat().st_size
        match = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not match:
            super().do_GET()
            return

        start = int(match.group(1)) if match.group(1) else 0
        end = int(match.group(2)) if match.group(2) else size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return

        length = end - start + 1
        ctype, _ = mimetypes.guess_type(str(file_path))
        self.send_response(206)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        with file_path.open("rb") as f:
            f.seek(start)
            self.wfile.write(f.read(length))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config-key":
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._send_json(403, {"error": "APIキー変更はMac本体(localhost)からのみ可能です"})
                return
            content_len = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
            params = json.loads(raw_body)
            api_key = str(params.get("apiKey", "")).strip().strip('"').strip("'")
            if api_key.startswith("GEMINI_API_KEY="):
                api_key = api_key.split("=", 1)[1].strip().strip('"').strip("'")
            if not api_key:
                self._send_json(400, {"error": "APIキーが空です"})
                return
            if api_key.startswith("/") or api_key.startswith("http") or len(api_key) < 25:
                self._send_json(
                    400,
                    {
                        "error": "ファイルパスやURLではなく、Google AI Studioで発行した『AIza...』で始まるAPIキーを貼り付けてください。"
                    },
                )
                return

            env_lines: list[str] = []
            if config.ENV_PATH.exists():
                for ln in config.ENV_PATH.read_text(encoding="utf-8").splitlines():
                    if not ln.strip().startswith("GEMINI_API_KEY="):
                        env_lines.append(ln)
            env_lines.insert(0, f"GEMINI_API_KEY={api_key}")
            config.ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            try:
                os.chmod(config.ENV_PATH, 0o600)
            except OSError:
                pass
            os.environ["GEMINI_API_KEY"] = api_key
            config.GEMINI_API_KEY = api_key
            masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "登録済"
            self._send_json(200, {"ok": True, "masked": masked})
            return

        if parsed.path == "/api/generate":
            content_len = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_len).decode("utf-8") if content_len else "{}"
            params = json.loads(raw_body)

            job_id = uuid.uuid4().hex[:10]
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "jobId": job_id,
                    "status": "running",
                    "logs": ["ローカル生成ジョブを受け付けました..."],
                }

            worker = threading.Thread(
                target=_run_pipeline_job, args=(job_id, params), daemon=True
            )
            worker.start()
            self._send_json(202, {"jobId": job_id, "status": "running"})
            return

        self._send_json(404, {"error": "Unknown API endpoint"})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    os.chdir(config.PROJECT_ROOT)
    mimetypes.add_type("image/webp", ".webp")
    mimetypes.add_type("audio/mpeg", ".mp3")
    mimetypes.add_type("video/mp4", ".mp4")

    httpd = ReusableThreadingHTTPServer((host, port), EscutaHTTPRequestHandler)
    print(f"============================================================")
    print(f" Escuta A1 (Gemini Edition) ローカルサーバー起動")
    print(f" URL: http://{host}:{port}")
    print(f" ルート: {config.PROJECT_ROOT}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nサーバーを停止しました。")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Escuta A1 ローカル管理＆ビューアーサーバー")
    parser.add_argument("--host", default="127.0.0.1", help="バインドホスト（スマホLAN確認時は 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="ポート番号（デフォルト: 8000）")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
