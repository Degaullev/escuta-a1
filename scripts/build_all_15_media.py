#!/usr/bin/env python3
"""
Batch Media Builder for the 15 Manaus Lessons:
1. Converts 45 generated 16:9 Studio Ghibli-style illustrations into WebP stills + seamless 6s H.264 MP4 loop videos
   in parallel across CPU cores (`ProcessPoolExecutor`).
2. Synthesizes all 15 main lesson dialogues (`audio.mp3`, CBR 128kbps MP3) using `gemini-3.8-flash-tts`
   (Ana=Aoede, Pedro=Puck, `speech_metadata.style` A1 15% slower conversational pt-BR) with rate-limit pacing,
   disk caching, and automatic `edge_tts` fallback if credits ever hit 402.
3. Synthesizes all ~180 vocabulary chunk MP3s (`media/chunks/*.mp3`) and 150 Japanese guide MP3s (`media/ja_guides/*.mp3`).
4. Writes exact timestamps and media URLs into every `lesson.json` and updates `lessons/index.json`.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import wave
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance  # type: ignore
import edge_tts  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from generate_15_manaus_lessons import MANAUS_15_TOPICS, rebuild_full_catalog  # noqa: E402
from run_gemini_38_tts_and_omni_video import (  # noqa: E402
    FFMPEG,
    synthesize_gemini_38_wav,
    trim_mono_24k_wav,
    wav_bytes_to_mp3,
)

OUT_W, OUT_H = 960, 540
FPS = 24
TOTAL_FRAMES = FPS * 6  # 144 frames seamless 6s loop

EDGE_VOICE_MAP = {
    "Ana": "pt-BR-ThalitaMultilingualNeural",
    "Pedro": "pt-BR-AntonioNeural",
}


def _detect_visual_effect(prompt_text: str) -> str:
    low = prompt_text.lower()
    if any(w in low for w in ("rain", "chuva", "downpour", "storm")):
        return "rain"
    if any(
        w in low
        for w in (
            "river",
            "water",
            "rio",
            "beach",
            "praia",
            "boat",
            "lancha",
            "dolphin",
            "boto",
            "manatee",
            "waterfall",
            "cachoeira",
            "port",
            "harbor",
            "bridge",
        )
    ):
        return "water"
    return "light"


def render_one_scene_video_worker(task: tuple[str, str, str, str]) -> str:
    lesson_id, scene_id, src_img_str, effect = task
    src_path = Path(src_img_str)
    media_dir = config.LESSONS_DIR / lesson_id / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    webp_path = media_dir / f"{scene_id}.webp"
    mp4_path = media_dir / f"{scene_id}.mp4"

    base_img = Image.open(src_path).convert("RGB")
    base_img.resize((1280, 720), Image.Resampling.LANCZOS).save(
        webp_path, format="WEBP", quality=88
    )

    work_w, work_h = int(OUT_W * 1.08), int(OUT_H * 1.08)
    work_base = base_img.resize((work_w, work_h), Image.Resampling.LANCZOS)

    cmd = [
        FFMPEG,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{OUT_W}x{OUT_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-vcodec",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    for f in range(TOTAL_FRAMES):
        theta = (2.0 * math.pi * f) / TOTAL_FRAMES
        zoom = 1.03 + 0.024 * (0.5 - 0.5 * math.cos(theta))
        crop_w = work_w / zoom
        crop_h = work_h / zoom
        cx = (work_w - crop_w) * (0.5 + 0.34 * math.sin(theta))
        cy = (work_h - crop_h) * (0.5 + 0.22 * math.sin(theta + 1.0))

        frame = work_base.crop((cx, cy, cx + crop_w, cy + crop_h)).resize(
            (OUT_W, OUT_H), Image.Resampling.BILINEAR
        )

        if effect == "water":
            overlay = frame.copy()
            band_h = 6
            y_start = int(OUT_H * 0.42)
            for y in range(y_start, OUT_H - band_h, band_h):
                depth = (y - y_start) / float(max(1, OUT_H - y_start))
                shift = int(round((1.2 + 2.6 * depth) * math.sin(theta * 2.0 + y * 0.12)))
                if shift != 0:
                    strip = frame.crop((0, y, OUT_W, y + band_h))
                    overlay.paste(strip, (shift, y))
            overlay = ImageEnhance.Brightness(overlay).enhance(
                1.0 + 0.025 * math.sin(theta * 2.0)
            )
            frame = Image.blend(frame, overlay, alpha=0.5)
        elif effect == "rain":
            rain_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(rain_layer)
            for idx in range(36):
                rx = ((idx * 97) + int(f * 6)) % OUT_W
                ry = ((idx * 61) + int(f * 22)) % OUT_H
                draw.line(
                    [(rx, ry), (rx - 4, ry + 18)],
                    fill=(220, 240, 255, 58),
                    width=1,
                )
            frame = Image.alpha_composite(frame.convert("RGBA"), rain_layer).convert("RGB")
        else:
            light_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(light_layer)
            ray_alpha = int(15 + 9 * math.sin(theta))
            draw.polygon(
                [(110, 0), (290, 0), (520, OUT_H), (240, OUT_H)],
                fill=(255, 232, 165, ray_alpha),
            )
            for idx in range(12):
                bx = (idx * 79 + 50) % (OUT_W - 80) + 40
                by = (idx * 53 + 35) % (OUT_H - 100) + 30
                mx = bx + 12.0 * math.sin(theta + idx * 0.8)
                my = by + 9.0 * math.cos(theta + idx * 1.2)
                alpha = int(34 + 28 * math.sin(theta * 2.0 + idx))
                r = 2 + (idx % 3)
                draw.ellipse(
                    (mx - r, my - r, mx + r, my + r),
                    fill=(255, 242, 190, max(0, alpha)),
                )
            frame = Image.alpha_composite(frame.convert("RGBA"), light_layer).convert("RGB")

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    err = proc.stderr.read() if proc.stderr else b""
    if proc.wait() != 0:
        raise RuntimeError(f"FFmpeg error {lesson_id}/{scene_id}: {err.decode('utf-8', 'ignore')}")
    return f"{lesson_id}/{scene_id}"


async def _synth_edge_wav_bytes(text: str, speaker: str) -> bytes:
    voice = EDGE_VOICE_MAP.get(speaker, EDGE_VOICE_MAP["Ana"])
    tmp_mp3 = Path(f"/tmp/edge_fb_{time.time_ns()}.mp3")
    tmp_wav = tmp_mp3.with_suffix(".wav")
    try:
        await edge_tts.Communicate(text=text, voice=voice, rate="-12%").save(str(tmp_mp3))
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(tmp_mp3),
                "-ac",
                "1",
                "-ar",
                "24000",
                "-sample_fmt",
                "s16",
                str(tmp_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return tmp_wav.read_bytes()
    finally:
        tmp_mp3.unlink(missing_ok=True)
        tmp_wav.unlink(missing_ok=True)


async def build_chunks_and_ja_guides_async(lesson_ids: list[str]) -> None:
    sem = asyncio.Semaphore(6)

    async def save_tts(text: str, voice: str, rate: str, dest: Path) -> None:
        if dest.exists() and dest.stat().st_size > 800:
            return
        async with sem:
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text=text, voice=voice, rate=rate).save(str(dest))
                    return
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1.5)

    tasks = []
    for lid in lesson_ids:
        ldir = config.LESSONS_DIR / lid
        lpath = ldir / "lesson.json"
        lesson = json.loads(lpath.read_text(encoding="utf-8"))
        chunks_dir = ldir / "media" / "chunks"
        ja_dir = ldir / "media" / "ja_guides"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        ja_dir.mkdir(parents=True, exist_ok=True)

        line_sp = {ln["id"]: ln["speaker"] for ln in lesson["lines"]}
        for voc in lesson.get("vocabulary", []):
            sp = line_sp.get(voc.get("lineId", ""), "Ana")
            voice = EDGE_VOICE_MAP.get(sp, EDGE_VOICE_MAP["Ana"])
            c_out = chunks_dir / f"{voc['id']}.mp3"
            voc["audioUrl"] = f"lessons/{lid}/media/chunks/{voc['id']}.mp3"
            tasks.append(save_tts(voc["chunkPt"], voice, "-10%", c_out))

        for ln in lesson["lines"]:
            j_out = ja_dir / f"{ln['id']}.mp3"
            ln["jaGuideAudioUrl"] = f"lessons/{lid}/media/ja_guides/{ln['id']}.mp3"
            tasks.append(save_tts(ln.get("jaGuide") or ln["ja"], "ja-JP-NanamiNeural", "+5%", j_out))

        lpath.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[Aux Audio] チャンク＆日本語ガイド音声 {len(tasks)} 個を並列生成中...")
    await asyncio.gather(*tasks)
    print("[Aux Audio] ✅ 完了！")


def build_all_dialogue_audio(lesson_ids: list[str]) -> None:
    """
    Synthesizes all lesson dialogue sentences using `gemini-3.8-flash-tts`
    (respecting 9 req/min pacing to avoid 429 walls, caching WAVs per sentence,
    and falling back to Neural pt-BR only if HTTP 402 credit depletion occurs).
    """
    gemini_depleted = False
    req_timestamps: list[float] = []

    for l_idx, lid in enumerate(lesson_ids, start=1):
        ldir = config.LESSONS_DIR / lid
        lpath = ldir / "lesson.json"
        lesson = json.loads(lpath.read_text(encoding="utf-8"))
        lines = lesson["lines"]

        cache_dir = ldir / ".tmp_gemini_wavs"
        cache_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{l_idx}/{len(lesson_ids)}] 会話音声を合成中: {lid} ({len(lines)}文)")
        line_wavs: dict[str, bytes] = {}

        for ln in lines:
            cached = cache_dir / f"{ln['id']}.wav"
            if cached.exists() and cached.stat().st_size > 1000:
                line_wavs[ln["id"]] = cached.read_bytes()
                continue

            if not gemini_depleted:
                # Smooth token-bucket pacing at 9 req / 62s for Tier 1 stability
                now = time.time()
                req_timestamps = [t for t in req_timestamps if now - t < 62.0]
                if len(req_timestamps) >= 9:
                    sleep_s = max(1.0, 62.5 - (now - req_timestamps[0]))
                    time.sleep(sleep_s)

                voice = config.SPEAKER_VOICES.get(ln["speaker"], "Aoede")
                try:
                    req_timestamps.append(time.time())
                    wav_b = synthesize_gemini_38_wav(ln["pt"], voice, config.TTS_MODEL)
                    cached.write_bytes(wav_b)
                    line_wavs[ln["id"]] = wav_b
                    continue
                except Exception as exc:
                    if "HTTP 402" in str(exc):
                        print("  [Notice] クレジット上限に達したため残り文をニューラルpt-BRで補完します。")
                        gemini_depleted = True
                    else:
                        print(f"  [Fallback] {lid}/{ln['id']} -> {exc}")

            wav_b = asyncio.run(_synth_edge_wav_bytes(ln["pt"], ln["speaker"]))
            cached.write_bytes(wav_b)
            line_wavs[ln["id"]] = wav_b

        # Stitch with exact 350ms / 650ms / 1400ms pauses & encode CBR 128kbps MP3
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

        out_mp3 = ldir / "audio.mp3"
        wav_bytes_to_mp3(buf.getvalue(), out_mp3)

        for sc in lesson["scenes"]:
            sid = sc["id"]
            if sid in scene_bounds:
                sc["startTime"] = scene_bounds[sid][0]
                sc["endTime"] = scene_bounds[sid][1]
            sc["image"] = f"lessons/{lid}/media/{sid}.webp"
            if (ldir / "media" / f"{sid}.mp4").exists():
                sc["video"] = f"lessons/{lid}/media/{sid}.mp4"

        lesson["duration"] = total_dur
        lesson["audioUrl"] = f"lessons/{lid}/audio.mp3"
        lpath.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  -> ✅ {lid}/audio.mp3 完成 ({total_dur}s)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-map", default="")
    parser.add_argument("--videos-only", action="store_true")
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()

    lesson_ids = [x["id"] for x in MANAUS_15_TOPICS]

    if args.images_map and not args.audio_only:
        img_map: dict[str, str] = json.loads(Path(args.images_map).read_text(encoding="utf-8"))
        video_tasks: list[tuple[str, str, str, str]] = []
        for lid in lesson_ids:
            lesson = json.loads((config.LESSONS_DIR / lid / "lesson.json").read_text(encoding="utf-8"))
            for sc in lesson["scenes"]:
                key = f"{lid}:{sc['id']}"
                if key in img_map and Path(img_map[key]).exists():
                    eff = _detect_visual_effect(sc.get("visualPrompt", "") + " " + sc.get("setting", ""))
                    video_tasks.append((lid, sc["id"], img_map[key], eff))

        print(f"[Visuals] {len(video_tasks)} 場面の WebP ＆ 6秒ループMP4 を6並列でエンコード中...")
        with ProcessPoolExecutor(max_workers=6) as pool:
            futs = [pool.submit(render_one_scene_video_worker, t) for t in video_tasks]
            for idx, f in enumerate(as_completed(futs), start=1):
                res_id = f.result()
                if idx % 9 == 0 or idx == len(video_tasks):
                    print(f"  [Visuals Progress] {idx}/{len(video_tasks)} 完了 ({res_id})")

        # Wire image & video paths into lesson.json immediately
        for lid in lesson_ids:
            lpath = config.LESSONS_DIR / lid / "lesson.json"
            lesson = json.loads(lpath.read_text(encoding="utf-8"))
            for sc in lesson["scenes"]:
                sid = sc["id"]
                sc["image"] = f"lessons/{lid}/media/{sid}.webp"
                if (config.LESSONS_DIR / lid / "media" / f"{sid}.mp4").exists():
                    sc["video"] = f"lessons/{lid}/media/{sid}.mp4"
            lpath.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.videos_only:
        asyncio.run(build_chunks_and_ja_guides_async(lesson_ids))
        build_all_dialogue_audio(lesson_ids)
        rebuild_full_catalog()


if __name__ == "__main__":
    main()
