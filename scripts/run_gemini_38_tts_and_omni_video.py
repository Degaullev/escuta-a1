#!/usr/bin/env python3
"""
Upgrades `manaus-demo` (or any `--lesson-id`) using the live Gemini Interactions API (`v1beta`):
1. Audio: `gemini-3.8-flash-tts` (12 dialogue sentences, Ana=Aoede / Pedro=Puck, `speech_metadata.style`
   strictly separated from text) + `gemini-3.8-flash-lite-tts` (23 vocabulary chunks), stitched with
   exact 350ms / 650ms / 1400ms pauses into iOS-safe CBR 128kbps MP3 (`audio.mp3`).
2. Video: `gemini-omni-1.2-flash` (3 scenes in parallel, 6s 720p 16:9 seamless loop using each scene's
   Ana & Pedro illustration as both starting frame and final frame, audio stripped for `<video muted loop>`).
Zero external pip dependencies required (pure Python `urllib.request` + `ffmpeg`).
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

API_BASE = "https://generativelanguage.googleapis.com"
FFMPEG = "/opt/homebrew/bin/ffmpeg" if Path("/opt/homebrew/bin/ffmpeg").is_file() else (shutil.which("ffmpeg") or "ffmpeg")
BRAIN_DIR = Path("/Users/okudayuuya/.gemini/antigravity/brain/b824f334-5ed1-4b74-892b-9f45caaebeff")

SCENE_VIDEO_PROMPTS = {
    "scene-1": (
        "Cinematic Studio Ghibli-inspired animated travel scene on a wooden riverboat in Manaus, Brazil. "
        "Ana (in white sleeveless linen top) smiles and points happily while her wavy dark brown hair sways "
        "gently in the warm river breeze; Pedro (in mustard-yellow collared shirt) smiles and gestures warmly "
        "toward the swirling meeting of glossy black Rio Negro water and golden-ochre Rio Solimões water "
        "shimmering in tropical sunlight as gentle ripples move across the river. Use this image as both the starting frame and the final frame."
    ),
    "scene-2": (
        "Cinematic Studio Ghibli-inspired animated scene from the wooden boat deck looking at the Encontro das Águas. "
        "Ana leans on the wooden railing watching with curiosity while her hair moves softly in the breeze, and Pedro "
        "gestures expressively with his hands explaining why the calm dark Rio Negro water on the left and the fast "
        "swirling golden-ochre Rio Solimões eddies on the right flow side by side without mixing. Use this image as both the starting frame and the final frame."
    ),
    "scene-3": (
        "Vibrant Studio Ghibli-inspired animated scene inside Mercado Municipal Adolpho Lisboa in Manaus, Brazil. "
        "Warm tropical sunlight filters through the stained-glass market arches as marketgoers move softly in the background; "
        "Ana smiles with sparkling eyes holding up two fingers beside Pedro grinning warmly behind glossy purple bowls of "
        "Amazonian açaí, crispy golden fried fish with lime, and farinha on the wooden counter. Use this image as both the starting frame and the final frame."
    ),
}


def redact(msg: str) -> str:
    key = config.GEMINI_API_KEY
    if key and len(key) >= 6:
        msg = msg.replace(key, "[REDACTED]")
    msg = re.sub(r"AIza[0-9A-Za-z_\-]{25,}", "[REDACTED]", msg)
    msg = re.sub(r"AQ\.[0-9A-Za-z_\-]{20,}", "[REDACTED]", msg)
    return msg[:450]


def api_json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 600) -> dict[str, Any]:
    api_key = config.require_api_key()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            if e.code == 429 and attempt < 3:
                m = re.search(r"retry in (\d+)s", err_body, flags=re.IGNORECASE)
                wait_s = (int(m.group(1)) + 3) if m else 45
                print(f"    [RateLimit 429] {wait_s}秒待機して自動リトライします (attempt {attempt + 1})...")
                time.sleep(wait_s)
                continue
            raise RuntimeError(f"HTTP {e.code}: {redact(err_body)}") from None
    raise RuntimeError("Max retries exceeded")


def upload_file_resumable(file_path: Path, mime_type: str) -> tuple[str, str]:
    """Uploads an image to Gemini Files API and returns (normalized_uri, mime_type)."""
    api_key = config.require_api_key()
    raw_bytes = file_path.read_bytes()
    num_bytes = len(raw_bytes)

    start_req = urllib.request.Request(
        f"{API_BASE}/upload/v1beta/files",
        data=json.dumps({"file": {"display_name": file_path.name}}).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(num_bytes),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(start_req, timeout=60) as resp:
        upload_url = resp.headers.get("X-Goog-Upload-URL") or resp.headers.get("x-goog-upload-url")
    if not upload_url:
        raise RuntimeError("Files API から X-Goog-Upload-URL を取得できませんでした。")

    up_req = urllib.request.Request(
        upload_url,
        data=raw_bytes,
        headers={
            "Content-Length": str(num_bytes),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        method="POST",
    )
    with urllib.request.urlopen(up_req, timeout=120) as resp:
        meta_wrap = json.loads(resp.read().decode("utf-8"))

    file_info = meta_wrap.get("file", meta_wrap)
    name = file_info["name"]  # e.g. "files/abc123"
    state = file_info.get("state", "ACTIVE")

    while state == "PROCESSING":
        time.sleep(2)
        info = api_json_request("GET", f"{API_BASE}/v1beta/{name}", timeout=30)
        state = info.get("state", "ACTIVE")
        file_info = info

    if state != "ACTIVE":
        raise RuntimeError(f"Uploaded file state={state}")

    file_id = name.split("/")[-1]
    normalized_uri = f"{API_BASE}/files/{file_id}"
    return normalized_uri, (file_info.get("mimeType") or mime_type)


def download_generated_video(video_uri: str, dest_mp4: Path) -> None:
    api_key = config.require_api_key()
    match = re.search(r"files/([a-zA-Z0-9_\-]+)", video_uri)
    if match:
        dl_url = f"{API_BASE}/v1beta/files/{match.group(1)}:download?alt=media"
    else:
        sep = "&" if "?" in video_uri else "?"
        dl_url = f"{video_uri}{sep}alt=media"

    req = urllib.request.Request(dl_url, headers={"x-goog-api-key": api_key}, method="GET")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_f:
        tmp_raw = Path(tmp_f.name)

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            tmp_raw.write_bytes(resp.read())

        # Strip audio track & optimize faststart for <video muted loop playsinline>
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(tmp_raw),
                "-c:v",
                "copy",
                "-an",
                "-movflags",
                "+faststart",
                str(dest_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    finally:
        tmp_raw.unlink(missing_ok=True)


def synthesize_gemini_38_wav(text_pt: str, voice_name: str, model_id: str) -> bytes:
    """Calls Gemini 3.8 TTS via POST /v1beta/interactions with speech_metadata.style."""
    payload = {
        "model": model_id,
        "store": False,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text_pt.strip(),
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": config.A1_PT_BR_STYLE,
                            }
                        ],
                    }
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {
            "speech_config": [{"voice": voice_name}],
        },
    }
    resp = api_json_request("POST", f"{API_BASE}/v1beta/interactions", payload, timeout=120)
    for step in resp.get("steps", []):
        if step.get("type") == "model_output":
            for item in step.get("content", []):
                if item.get("type") == "audio" and item.get("data"):
                    raw = base64.b64decode(item["data"])
                    if raw[:4] == b"RIFF":
                        return raw
                    # Wrap 24kHz L16 PCM if needed
                    buf = io.BytesIO()
                    with wave.open(buf, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(raw)
                    return buf.getvalue()
    raise RuntimeError(f"TTSレスポンスに音声が含まれていません: {redact(json.dumps(resp)[:200])}")


def trim_mono_24k_wav(wav_bytes: bytes, threshold: int = 200) -> tuple[bytes, float]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in, tempfile.NamedTemporaryFile(
        suffix=".wav", delete=False
    ) as f_out:
        p_in = Path(f_in.name)
        p_out = Path(f_out.name)
    try:
        p_in.write_bytes(wav_bytes)
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(p_in),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-sample_fmt",
                "s16",
                str(p_out),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        with wave.open(str(p_out), "rb") as wf:
            raw = wf.readframes(wf.getnframes())
            sr = wf.getframerate()
        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        n = len(samples)
        first, last = 0, n - 1
        while first < n and abs(samples[first]) < threshold:
            first += 1
        while last > first and abs(samples[last]) < threshold:
            last -= 1
        if first >= last:
            return raw, n / float(sr)
        s = max(0, first - int(sr * 0.035))
        e = min(n, last + int(sr * 0.065))
        trimmed = struct.pack(f"<{e - s}h", *samples[s:e])
        return trimmed, (e - s) / float(sr)
    finally:
        p_in.unlink(missing_ok=True)
        p_out.unlink(missing_ok=True)


def wav_bytes_to_mp3(wav_bytes: bytes, dest_mp3: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        p_in = Path(tmp.name)
    try:
        p_in.write_bytes(wav_bytes)
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(p_in),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-ar",
                "44100",
                str(dest_mp3),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    finally:
        p_in.unlink(missing_ok=True)


def generate_omni_loop_video(scene_id: str, still_path: Path, prompt: str, dest_mp4: Path) -> None:
    mime = "image/webp" if still_path.suffix.lower() == ".webp" else "image/jpeg"
    uri, uploaded_mime = upload_file_resumable(still_path, mime)

    payload = {
        "model": "gemini-omni-1.2-flash",
        "store": True,
        "input": [
            {"type": "image", "uri": uri, "mime_type": uploaded_mime},
            {"type": "image", "uri": uri, "mime_type": uploaded_mime},
            {"type": "text", "text": prompt},
        ],
        "response_format": {
            "type": "video",
            "delivery": "uri",
            "aspect_ratio": "16:9",
            "duration": "6s",
            "resolution": "720p",
        },
    }
    resp = api_json_request("POST", f"{API_BASE}/v1beta/interactions", payload, timeout=600)

    # Handle background/in_progress polling if returned asynchronously
    inter_id = resp.get("id")
    status = resp.get("status", "completed")
    while status in ("queued", "in_progress") and inter_id:
        time.sleep(6)
        resp = api_json_request("GET", f"{API_BASE}/v1beta/interactions/{inter_id}", timeout=60)
        status = resp.get("status", "completed")

    if status != "completed":
        raise RuntimeError(f"Video interaction ended with status={status}")

    video_uri = None
    for step in resp.get("steps", []):
        if step.get("type") == "model_output":
            for item in step.get("content", []):
                if item.get("type") == "video" and item.get("uri"):
                    video_uri = item["uri"]
    if not video_uri:
        raise RuntimeError("レスポンス内に video URI が見つかりませんでした。")

    download_generated_video(video_uri, dest_mp4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lesson-id", default="manaus-demo")
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-chunks", action="store_true")
    args = parser.parse_args()

    lesson_dir = config.LESSONS_DIR / args.lesson_id
    lesson_path = lesson_dir / "lesson.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    media_dir = lesson_dir / "media"
    chunks_dir = media_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    lines = lesson["lines"]
    vocabs = lesson.get("vocabulary", [])
    scenes = lesson.get("scenes", [])

    print(
        f"=== Gemini本番メディア生成開始 ===\n"
        f"  - 会話TTS (`gemini-3.8-flash-tts`): {len(lines)} リクエスト\n"
        f"  - チャンクTTS (`gemini-3.8-flash-lite-tts`): {0 if args.skip_chunks else len(vocabs)} リクエスト\n"
        f"  - AIループ動画 (`gemini-omni-1.2-flash` 720p 6s): {0 if args.skip_video else len(scenes)} リクエスト"
    )

    tmp_wav_cache = lesson_dir / ".tmp_gemini_wavs"
    tmp_wav_cache.mkdir(parents=True, exist_ok=True)
    line_wavs: dict[str, bytes] = {}
    line_speaker = {ln["id"]: ln["speaker"] for ln in lines}

    # Only regenerate chunks older than the current Gemini 3.8 upgrade session
    missing_chunks = [
        voc
        for voc in vocabs
        if not (chunks_dir / f"{voc['id']}.mp3").exists()
        or (time.time() - (chunks_dir / f"{voc['id']}.mp3").stat().st_mtime) > 300
    ]

    with ThreadPoolExecutor(max_workers=6) as pool:
        fut_map: dict[Any, tuple[str, str]] = {}

        # Submit dialogue TTS requests (reusing cached WAVs if already synthesized)
        for ln in lines:
            cached_wav = tmp_wav_cache / f"{ln['id']}.wav"
            if cached_wav.exists() and cached_wav.stat().st_size > 1000:
                line_wavs[ln["id"]] = cached_wav.read_bytes()
                continue
            voice = config.SPEAKER_VOICES.get(ln["speaker"], "Aoede")
            f = pool.submit(synthesize_gemini_38_wav, ln["pt"], voice, config.TTS_MODEL)
            fut_map[f] = ("line", ln["id"])

        # Submit remaining chunk TTS requests
        if not args.skip_chunks:
            for voc in missing_chunks:
                sp = line_speaker.get(voc.get("lineId", ""), "Ana")
                voice = config.SPEAKER_VOICES.get(sp, "Aoede")
                f = pool.submit(
                    synthesize_gemini_38_wav, voc["chunkPt"], voice, config.TTS_LITE_MODEL
                )
                fut_map[f] = ("chunk", voc["id"])

        # Submit 3 Gemini Omni 1.2 Flash video requests concurrently
        if not args.skip_video:
            for sc in scenes:
                sid = sc["id"]
                still_webp = media_dir / f"{sid}.webp"
                if not still_webp.exists():
                    continue
                prompt = SCENE_VIDEO_PROMPTS.get(sid) or (
                    f"{sc.get('visualPrompt', sc.get('title', ''))}. Use this image as both the starting frame and the final frame."
                )
                out_mp4 = media_dir / f"{sid}.mp4"
                f = pool.submit(generate_omni_loop_video, sid, still_webp, prompt, out_mp4)
                fut_map[f] = ("video", sid)

        for fut in as_completed(fut_map):
            kind, item_id = fut_map[fut]
            try:
                res = fut.result()
                if kind == "line":
                    line_wavs[item_id] = res
                    (tmp_wav_cache / f"{item_id}.wav").write_bytes(res)
                    print(f"  [TTS OK] {item_id}")
                elif kind == "chunk":
                    wav_bytes_to_mp3(res, chunks_dir / f"{item_id}.mp3")
                    print(f"  [Chunk TTS OK] {item_id}")
                elif kind == "video":
                    mp4_p = media_dir / f"{item_id}.mp4"
                    print(f"  [Omni 1.2 Video OK] {item_id} ({mp4_p.stat().st_size // 1024} KB)")
            except Exception as exc:
                print(f"  [WARN] {kind}:{item_id} -> {redact(str(exc))}", file=sys.stderr)

    # Assemble CBR 128kbps MP3 if all dialogue lines succeeded
    if len(line_wavs) == len(lines):
        sr = 24000
        combined_pcm = bytearray()
        cursor = 0.0
        prev_sp = None
        prev_sc = None
        scene_bounds: dict[str, list[float]] = {}

        for idx, ln in enumerate(lines):
            if idx > 0:
                if ln["sceneId"] != prev_sc:
                    pause_ms = config.PAUSE_SCENE_SWITCH_MS
                elif ln["speaker"] != prev_sp:
                    pause_ms = config.PAUSE_SPEAKER_SWITCH_MS
                else:
                    pause_ms = config.PAUSE_SAME_SPEAKER_MS
                p_samples = int(sr * (pause_ms / 1000.0))
                combined_pcm += b"\x00\x00" * p_samples
                cursor += p_samples / float(sr)

            pcm, dur = trim_mono_24k_wav(line_wavs[ln["id"]])
            s_sec = round(cursor, 2)
            combined_pcm += pcm
            cursor += dur
            e_sec = round(cursor, 2)
            ln["start"] = s_sec
            ln["end"] = e_sec
            prev_sp = ln["speaker"]
            prev_sc = ln["sceneId"]

            b = scene_bounds.setdefault(ln["sceneId"], [s_sec, e_sec])
            b[0] = min(b[0], s_sec)
            b[1] = max(b[1], e_sec)

        combined_pcm += b"\x00\x00" * int(sr * 0.5)
        total_dur = round(cursor + 0.5, 2)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(bytes(combined_pcm))

        audio_mp3 = lesson_dir / "audio.mp3"
        wav_bytes_to_mp3(buf.getvalue(), audio_mp3)

        for sc in scenes:
            if sc["id"] in scene_bounds:
                sc["startTime"] = scene_bounds[sc["id"]][0]
                sc["endTime"] = scene_bounds[sc["id"]][1]
        lesson["duration"] = total_dur
        lesson_path.write_text(
            json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        cat = json.loads(config.CATALOG_PATH.read_text(encoding="utf-8"))
        for entry in cat.get("lessons", []):
            if entry["id"] == args.lesson_id:
                entry["duration"] = total_dur
        config.CATALOG_PATH.write_text(
            json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"✅ Gemini 3.8 Flash TTS 結合完了: {audio_mp3} ({total_dur}s)")
    else:
        print(
            f"⚠️ 会話TTSが一部未完了 ({len(line_wavs)}/{len(lines)}) のため既存の audio.mp3 を維持しました。"
        )


if __name__ == "__main__":
    main()
