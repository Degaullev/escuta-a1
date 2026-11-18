#!/usr/bin/env python3
"""
Escuta A1 — Step 2 of Pipeline: Gemini 3.8 TTS & Exact Timestamp CBR MP3 Builder
- Synthesizes sentence-by-sentence WAVs for Ana & Pedro
- Strictly separates acting/speed instructions into `speech_metadata.style`
- Normalizes leading/trailing silence, inserts 350ms / 650ms / 1400ms pauses
- Writes exact `start` / `end` timestamps back to `lesson.json`
- Encodes iOS Safari seek-safe CBR 128kbps MP3 via FFmpeg
"""
from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def _pcm_or_wav_to_wav_bytes(audio_bytes: bytes, mime_type: str = "") -> bytes:
    """Ensures returned Gemini audio bytes are wrapped as standard 16-bit mono WAV."""
    if audio_bytes[:4] == b"RIFF":
        return audio_bytes

    sample_rate = config.SAMPLE_RATE_HZ
    if "rate=" in mime_type:
        try:
            rate_part = mime_type.split("rate=")[1].split(";")[0].strip()
            sample_rate = int(rate_part)
        except ValueError:
            pass

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    return buf.getvalue()


def _find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if Path(candidate).is_file():
            return candidate
    return None


def _generate_dry_run_wav(duration_sec: float, freq_hz: float = 0.0) -> bytes:
    """Creates a clean 24kHz 16-bit mono WAV for local --dry-run testing."""
    sr = config.SAMPLE_RATE_HZ
    n_samples = max(1, int(sr * duration_sec))
    tone_len = int(sr * 0.10)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(n_samples):
            if freq_hz > 0 and i < tone_len:
                env = math.sin(math.pi * i / tone_len)
                val = int(3200 * env * math.sin(2 * math.pi * freq_hz * (i / sr)))
            elif freq_hz > 0 and i >= n_samples - tone_len:
                j = i - (n_samples - tone_len)
                env = math.sin(math.pi * j / tone_len)
                val = int(1200 * env * math.sin(2 * math.pi * freq_hz * (j / sr)))
            else:
                val = 0
            frames += struct.pack("<h", val)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def _trim_wav_silence_pure(wav_path: Path, threshold: int = 180) -> tuple[bytes, int, float]:
    """
    Reads a 16-bit WAV, trims leading/trailing silence (with 30ms natural breath pad),
    and returns (pcm_mono_frames, sample_rate, duration_sec).
    Uses pydub if installed for multi-channel/resampling, with pure-Python wave fallback.
    """
    try:
        from pydub import AudioSegment, silence  # type: ignore

        seg = AudioSegment.from_wav(str(wav_path))
        seg = seg.set_channels(1).set_frame_rate(config.SAMPLE_RATE_HZ).set_sample_width(2)
        nonsilent = silence.detect_nonsilent(seg, min_silence_len=40, silence_thresh=-45)
        if nonsilent:
            start_ms = max(0, nonsilent[0][0] - 30)
            end_ms = min(len(seg), nonsilent[-1][1] + 40)
            seg = seg[start_ms:end_ms]
        raw = seg.raw_data
        dur = len(seg) / 1000.0
        return raw, config.SAMPLE_RATE_HZ, dur
    except ImportError:
        with wave.open(str(wav_path), "rb") as wf:
            sr = wf.getframerate()
            n_ch = wf.getnchannels()
            sw = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())

        if sw != 2 or n_ch != 1:
            dur = len(raw) / float(sr * n_ch * sw)
            return raw, sr, dur

        samples = struct.unpack(f"<{len(raw) // 2}h", raw)
        first_idx = 0
        last_idx = len(samples) - 1
        while first_idx < len(samples) and abs(samples[first_idx]) < threshold:
            first_idx += 1
        while last_idx > first_idx and abs(samples[last_idx]) < threshold:
            last_idx -= 1

        if first_idx >= last_idx:
            # Entirely silent (e.g. dry-run)
            return raw, sr, len(samples) / float(sr)

        pad = int(sr * 0.03)
        start = max(0, first_idx - pad)
        end = min(len(samples), last_idx + pad)
        trimmed = struct.pack(f"<{end - start}h", *samples[start:end])
        return trimmed, sr, (end - start) / float(sr)


def call_gemini_tts_single(
    client: Any,
    model_id: str,
    spoken_text_pt: str,
    voice_name: str,
    style_instruction: str,
) -> bytes:
    """
    Calls Gemini 3.8 TTS for a single sentence.
    IMPORTANT: `spoken_text_pt` contains ONLY the clean dialogue text.
    `style_instruction` is strictly passed via `speech_metadata.style`.
    """
    from google.genai import types  # type: ignore

    speech_cfg_kwargs: dict[str, Any] = {
        "voice_config": types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
        )
    }

    # Support speech_metadata on SpeechConfig or GenerateContentConfig depending on SDK build
    speech_metadata_payload = {"style": style_instruction}
    gen_cfg_kwargs: dict[str, Any] = {
        "response_modalities": ["AUDIO"],
    }

    if hasattr(types, "SpeechMetadata"):
        meta_obj = types.SpeechMetadata(style=style_instruction)
        if "speech_metadata" in getattr(types.SpeechConfig, "model_fields", {}):
            speech_cfg_kwargs["speech_metadata"] = meta_obj
        else:
            gen_cfg_kwargs["speech_metadata"] = meta_obj
    else:
        if "speech_metadata" in getattr(types.SpeechConfig, "model_fields", {}):
            speech_cfg_kwargs["speech_metadata"] = speech_metadata_payload
        else:
            gen_cfg_kwargs["speech_metadata"] = speech_metadata_payload

    gen_cfg_kwargs["speech_config"] = types.SpeechConfig(**speech_cfg_kwargs)

    response = client.models.generate_content(
        model=model_id,
        contents=spoken_text_pt,
        config=types.GenerateContentConfig(**gen_cfg_kwargs),
    )

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return _pcm_or_wav_to_wav_bytes(
                    inline.data, getattr(inline, "mime_type", "")
                )

    raise RuntimeError("Gemini TTS レスポンスに音声データが含まれていませんでした。")


def synthesize_lesson_audio(
    lesson_id: str,
    limit: int = 0,
    only_line_ids: set[str] | None = None,
    use_lite: bool = False,
    dry_run: bool = False,
) -> Path:
    lesson_dir = config.LESSONS_DIR / lesson_id
    lesson_json_path = lesson_dir / "lesson.json"
    if not lesson_json_path.exists():
        raise FileNotFoundError(f"lesson.json が見つかりません: {lesson_json_path}")

    lesson = json.loads(lesson_json_path.read_text(encoding="utf-8"))
    all_lines: list[dict[str, Any]] = lesson.get("lines", [])
    target_lines = all_lines[:limit] if limit > 0 else all_lines

    tmp_wav_dir = lesson_dir / ".tmp_wavs"
    tmp_wav_dir.mkdir(parents=True, exist_ok=True)

    model_id = config.TTS_LITE_MODEL if use_lite else config.TTS_MODEL

    lines_to_request = [
        ln
        for ln in target_lines
        if (only_line_ids is None or ln["id"] in only_line_ids)
    ]

    if dry_run:
        print(
            f"[DRY-RUN] APIリクエスト発生数: 0回"
            f"（本番実行時は `{model_id}` へ {len(lines_to_request)}回リクエスト）"
        )
        client = None
    else:
        print(
            f"[synthesize_audio] `{model_id}` を使用し、{len(lines_to_request)}文の音声を生成します..."
        )
        client = config.get_genai_client()

    # Step A: Generate per-sentence WAVs
    for ln in lines_to_request:
        wav_file = tmp_wav_dir / f"{ln['id']}.wav"
        speaker = ln.get("speaker", "Ana")
        voice_name = config.SPEAKER_VOICES.get(speaker, "Aoede")
        clean_pt = ln["pt"].strip()

        if dry_run:
            est_sec = max(2.2, round(len(clean_pt) * 0.09, 2))
            freq = 523.25 if speaker == "Ana" else 392.00
            wav_bytes = _generate_dry_run_wav(est_sec, freq_hz=freq)
        else:
            print(f"  -> TTS生成 [{ln['id']}] ({speaker}/{voice_name}): {clean_pt}")
            wav_bytes = call_gemini_tts_single(
                client=client,
                model_id=model_id,
                spoken_text_pt=clean_pt,
                voice_name=voice_name,
                style_instruction=config.A1_PT_BR_STYLE,
            )
        wav_file.write_bytes(wav_bytes)

    # Step B: Concatenate with exact pauses & record exact timestamps
    combined_pcm = bytearray()
    sr = config.SAMPLE_RATE_HZ
    cursor_sec = 0.0
    prev_speaker = None
    prev_scene = None
    scene_bounds: dict[str, list[float]] = {}

    for idx, ln in enumerate(target_lines):
        wav_file = tmp_wav_dir / f"{ln['id']}.wav"
        if not wav_file.exists():
            # Fallback if partial regeneration was run before full synthesis
            wav_file.write_bytes(_generate_dry_run_wav(2.4))

        if idx > 0:
            if ln["sceneId"] != prev_scene:
                pause_ms = config.PAUSE_SCENE_SWITCH_MS
            elif ln["speaker"] != prev_speaker:
                pause_ms = config.PAUSE_SPEAKER_SWITCH_MS
            else:
                pause_ms = config.PAUSE_SAME_SPEAKER_MS

            pause_samples = int(sr * (pause_ms / 1000.0))
            combined_pcm += b"\x00\x00" * pause_samples
            cursor_sec += pause_samples / float(sr)

        pcm_frames, file_sr, dur_sec = _trim_wav_silence_pure(wav_file)
        sr = file_sr
        start_sec = round(cursor_sec, 2)
        combined_pcm += pcm_frames
        cursor_sec += dur_sec
        end_sec = round(cursor_sec, 2)

        ln["start"] = start_sec
        ln["end"] = end_sec
        prev_speaker = ln["speaker"]
        prev_scene = ln["sceneId"]

        bounds = scene_bounds.setdefault(ln["sceneId"], [start_sec, end_sec])
        bounds[0] = min(bounds[0], start_sec)
        bounds[1] = max(bounds[1], end_sec)

    # Update scene time bounds for processed scenes
    for sc in lesson.get("scenes", []):
        if sc["id"] in scene_bounds:
            sc["startTime"] = scene_bounds[sc["id"]][0]
            sc["endTime"] = scene_bounds[sc["id"]][1]

    if limit == 0 or limit >= len(all_lines):
        lesson["duration"] = round(cursor_sec, 2)

    combined_wav_path = tmp_wav_dir / "combined.wav"
    with wave.open(str(combined_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(bytes(combined_pcm))

    # Step C: Encode CBR 128kbps MP3 via FFmpeg (if ffmpeg is installed)
    mp3_out_path = lesson_dir / (
        "audio_test_limit.mp3" if (0 < limit < len(all_lines)) else "audio.mp3"
    )
    ffmpeg_bin = _find_ffmpeg()
    if ffmpeg_bin:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(combined_wav_path),
            "-codec:a",
            "libmp3lame",
            "-b:a",
            config.MP3_BITRATE,
            "-minrate",
            config.MP3_BITRATE,
            "-maxrate",
            config.MP3_BITRATE,
            "-ar",
            "44100",
            str(mp3_out_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print(f"[synthesize_audio] CBR 128kbps MP3 書き出し完了: {mp3_out_path}")
    else:
        print(
            f"[synthesize_audio] ⚠️ ffmpeg が未検出のため WAV まで出力しました: {combined_wav_path}"
            "（`brew install ffmpeg` で CBR 128kbps MP3 変換が有効になります）"
        )

    # Write updated exact timestamps back to lesson.json (skip overwriting full lesson duration on --dry-run --limit)
    if not dry_run:
        lesson_json_path.write_text(
            json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[synthesize_audio] 秒数タイムスタンプを更新しました: {lesson_json_path}")
    else:
        print(
            f"[DRY-RUN] 検証完了（結合長 {round(cursor_sec, 2)}秒 / lesson.json 本体は保護のため未変更）"
        )

    return mp3_out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gemini 3.8 TTS で文単位の音声を生成し、CBR 128kbps MP3 に結合します。"
    )
    parser.add_argument(
        "--lesson-id", default="manaus-demo", help="対象レッスンID（デフォルト: manaus-demo）"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="先頭N文のみテスト合成（例: --limit 3 でAPI消費を3文に制限）",
    )
    parser.add_argument(
        "--only-lines",
        default="",
        help="再生成する文IDをカンマ区切り指定（例: line-02,line-05）",
    )
    parser.add_argument(
        "--lite",
        action="store_true",
        help="軽量モデル gemini-3.8-flash-lite-tts を使用する",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="APIを叩かずにローカルテストWAV結合・秒数計算のみ検証する",
    )
    args = parser.parse_args()

    only_set = (
        {x.strip() for x in args.only_lines.split(",") if x.strip()}
        if args.only_lines
        else None
    )
    synthesize_lesson_audio(
        lesson_id=args.lesson_id,
        limit=args.limit,
        only_line_ids=only_set,
        use_lite=args.lite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
