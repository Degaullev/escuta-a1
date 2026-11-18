#!/usr/bin/env python3
"""
Builds natural Brazilian Portuguese (pt-BR) neural audio for a lesson (dialogue + 23 vocabulary chunks)
using `edge_tts` (ThalitaMultilingualNeural for Ana, AntonioNeural for Pedro) + FFmpeg CBR 128kbps MP3,
recording exact sentence timestamps into `lesson.json`.
"""
from __future__ import annotations

import asyncio
import json
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import edge_tts  # type: ignore

PROJECT_ROOT = Path("/Users/okudayuuya/.gemini/antigravity/scratch/escuta-a1")
FFMPEG = "/opt/homebrew/bin/ffmpeg"
SAMPLE_RATE = 24000

VOICE_MAP = {
    "Ana": "pt-BR-ThalitaMultilingualNeural",
    "Pedro": "pt-BR-AntonioNeural",
}

PAUSE_SAME_MS = 350
PAUSE_SWITCH_MS = 650
PAUSE_SCENE_MS = 1400


def trim_wav_pcm(wav_path: Path, threshold: int = 220) -> tuple[bytes, float]:
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        sr = wf.getframerate()
    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    n = len(samples)
    first = 0
    last = n - 1
    while first < n and abs(samples[first]) < threshold:
        first += 1
    while last > first and abs(samples[last]) < threshold:
        last -= 1
    if first >= last:
        return raw, n / float(sr)
    pad_head = int(sr * 0.035)
    pad_tail = int(sr * 0.065)
    s = max(0, first - pad_head)
    e = min(n, last + pad_tail)
    trimmed = struct.pack(f"<{e - s}h", *samples[s:e])
    return trimmed, (e - s) / float(sr)


async def synth_to_mp3(text: str, voice: str, rate: str, out_mp3: Path, sem: asyncio.Semaphore) -> None:
    async with sem:
        comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await comm.save(str(out_mp3))


async def build_lesson_audio(lesson_id: str = "manaus-demo") -> None:
    lesson_dir = PROJECT_ROOT / "lessons" / lesson_id
    lesson_path = lesson_dir / "lesson.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))

    chunks_dir = lesson_dir / "media" / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(5)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Synthesize all 12 dialogue lines in parallel
        line_tasks = []
        for ln in lesson["lines"]:
            voice = VOICE_MAP.get(ln["speaker"], VOICE_MAP["Ana"])
            raw_mp3 = tmp / f"{ln['id']}.mp3"
            line_tasks.append(synth_to_mp3(ln["pt"], voice, "-12%", raw_mp3, sem))

        # 2. Synthesize all 23 vocabulary chunks in parallel for popup & SRS cards
        line_speaker = {ln["id"]: ln["speaker"] for ln in lesson["lines"]}
        chunk_tasks = []
        for voc in lesson.get("vocabulary", []):
            sp = line_speaker.get(voc.get("lineId", ""), "Ana")
            voice = VOICE_MAP.get(sp, VOICE_MAP["Ana"])
            chunk_mp3 = chunks_dir / f"{voc['id']}.mp3"
            voc["audioUrl"] = f"lessons/{lesson_id}/media/chunks/{voc['id']}.mp3"
            chunk_tasks.append(synth_to_mp3(voc["chunkPt"], voice, "-10%", chunk_mp3, sem))

        await asyncio.gather(*line_tasks, *chunk_tasks)

        # 3. Convert each line MP3 -> 24kHz mono WAV, trim silence, stitch with exact pauses
        combined_pcm = bytearray()
        cursor = 0.0
        prev_speaker = None
        prev_scene = None
        scene_bounds: dict[str, list[float]] = {}

        for idx, ln in enumerate(lesson["lines"]):
            raw_mp3 = tmp / f"{ln['id']}.mp3"
            wav_file = tmp / f"{ln['id']}.wav"
            subprocess.run(
                [
                    FFMPEG,
                    "-y",
                    "-i",
                    str(raw_mp3),
                    "-ac",
                    "1",
                    "-ar",
                    str(SAMPLE_RATE),
                    "-sample_fmt",
                    "s16",
                    str(wav_file),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

            if idx > 0:
                if ln["sceneId"] != prev_scene:
                    pause_ms = PAUSE_SCENE_MS
                elif ln["speaker"] != prev_speaker:
                    pause_ms = PAUSE_SWITCH_MS
                else:
                    pause_ms = PAUSE_SAME_MS
                pause_samples = int(SAMPLE_RATE * (pause_ms / 1000.0))
                combined_pcm += b"\x00\x00" * pause_samples
                cursor += pause_samples / float(SAMPLE_RATE)

            pcm, dur = trim_wav_pcm(wav_file)
            start_s = round(cursor, 2)
            combined_pcm += pcm
            cursor += dur
            end_s = round(cursor, 2)

            ln["start"] = start_s
            ln["end"] = end_s
            prev_speaker = ln["speaker"]
            prev_scene = ln["sceneId"]

            b = scene_bounds.setdefault(ln["sceneId"], [start_s, end_s])
            b[0] = min(b[0], start_s)
            b[1] = max(b[1], end_s)

        # Add gentle 0.5s tail pad
        combined_pcm += b"\x00\x00" * int(SAMPLE_RATE * 0.5)
        total_duration = round(cursor + 0.5, 2)

        combined_wav = tmp / "combined.wav"
        with wave.open(str(combined_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(bytes(combined_pcm))

        out_mp3 = lesson_dir / "audio.mp3"
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(combined_wav),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-minrate",
                "128k",
                "-maxrate",
                "128k",
                "-ar",
                "44100",
                str(out_mp3),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    for sc in lesson["scenes"]:
        if sc["id"] in scene_bounds:
            sc["startTime"] = scene_bounds[sc["id"]][0]
            sc["endTime"] = scene_bounds[sc["id"]][1]
    lesson["duration"] = total_duration

    lesson_path.write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Update catalog duration
    cat_path = PROJECT_ROOT / "lessons" / "index.json"
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    for entry in cat.get("lessons", []):
        if entry["id"] == lesson_id:
            entry["duration"] = total_duration
    cat_path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS: {out_mp3} ({total_duration}s) + {len(chunk_tasks)} chunk MP3s generated!")


if __name__ == "__main__":
    asyncio.run(build_lesson_audio("manaus-demo"))
