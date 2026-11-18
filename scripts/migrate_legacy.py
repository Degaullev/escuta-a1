#!/usr/bin/env python3
"""
Escuta A1 — Legacy Claude Edition Asset Backup & Migration Tool
- Safely copies legacy HTML / JSON / audio / 47 scene images into `legacy_backup/`
  (NEVER deletes or overwrites original files, per GEMINI.md Rule 5)
- Parses embedded JS/JSON dialogue arrays from legacy Claude single-HTML or JSON files
  (e.g., Manaus v2 145 sentences, Compras no mercado) and converts them into
  `lessons/<lesson-id>/lesson.json` + copies media into `lessons/<lesson-id>/media/`.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from generate_script import update_catalog  # noqa: E402


def backup_source_safely(source_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = config.LEGACY_BACKUP_DIR / f"{stamp}_{source_path.name}"
    config.LEGACY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if source_path.is_dir():
        shutil.copytree(source_path, dest)
    else:
        shutil.copy2(source_path, dest)
    print(f"[migrate_legacy] 既存資産を保護バックアップしました: {dest}")
    return dest


def _extract_json_array_from_html(html_text: str) -> list[dict[str, Any]]:
    """Extracts embedded dialogue arrays (`const lines = [...]` / `const script = [...]`) from Claude HTML."""
    patterns = [
        r"(?:const|let|var)\s+(?:LINES|SCRIPT|DIALOGUE|DATA|lines|script|sentences)\s*=\s*(\[\s*\{.*?\}\s*\])\s*;",
        r'"lines"\s*:\s*(\[\s*\{.*?\}\s*\])',
    ]
    for pat in patterns:
        match = re.search(pat, html_text, flags=re.DOTALL)
        if match:
            candidate = match.group(1)
            # Strip trailing JS commas before ] or }
            candidate_clean = re.sub(r",\s*([\]}])", r"\1", candidate)
            try:
                parsed = json.loads(candidate_clean)
                if isinstance(parsed, list) and parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
    raise ValueError(
        "HTML内から台本配列データを自動抽出できませんでした。JSON形式または台本変数名を確認してください。"
    )


def convert_legacy_items(
    raw_items: list[dict[str, Any]],
    lesson_id: str,
    title: str,
    title_ja: str,
) -> dict[str, Any]:
    scenes_map: dict[str, dict[str, Any]] = {}
    lines_out: list[dict[str, Any]] = []
    cursor = 0.0

    for idx, item in enumerate(raw_items, start=1):
        pt = str(item.get("pt") or item.get("text") or item.get("portuguese") or "").strip()
        ja = str(item.get("ja") or item.get("translation") or item.get("japanese") or "").strip()
        speaker_raw = str(item.get("speaker") or item.get("role") or "Ana").strip()
        speaker = "Pedro" if "pedro" in speaker_raw.lower() else "Ana"

        raw_scene = str(item.get("scene") or item.get("sceneId") or f"scene-{(idx - 1) // 4 + 1}")
        scene_id = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_scene).lower()
        if not scene_id.startswith("scene"):
            scene_id = f"scene-{scene_id}"

        start_sec = float(item.get("start", cursor))
        est_dur = max(2.2, round(len(pt) * 0.095, 2))
        end_sec = float(item.get("end", round(start_sec + est_dur, 2)))
        cursor = end_sec + 0.65

        if scene_id not in scenes_map:
            s_idx = len(scenes_map) + 1
            img_name = item.get("image") or f"{scene_id}.webp"
            scenes_map[scene_id] = {
                "id": scene_id,
                "index": s_idx,
                "title": item.get("sceneTitle") or f"Cena {s_idx}",
                "titleJa": item.get("sceneTitleJa") or f"場面 {s_idx}",
                "setting": "",
                "startTime": round(start_sec, 2),
                "endTime": round(end_sec, 2),
                "image": f"lessons/{lesson_id}/media/{Path(str(img_name)).name}",
                "video": None,
                "keywords": [],
            }
        else:
            scenes_map[scene_id]["endTime"] = round(end_sec, 2)

        lines_out.append(
            {
                "id": f"line-{idx:03d}",
                "index": idx,
                "sceneId": scene_id,
                "speaker": speaker,
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "pt": pt,
                "ja": ja,
                "jaGuide": ja,
                "vocabIds": [],
            }
        )

    duration = lines_out[-1]["end"] if lines_out else 0.0
    return {
        "id": lesson_id,
        "title": title,
        "titleJa": title_ja,
        "level": "CEFR A1",
        "language": "pt-BR",
        "version": "1.0.0",
        "description": f"既存Claude版資産から移行された教材（全{len(lines_out)}文・{len(scenes_map)}場面）。",
        "audioUrl": f"lessons/{lesson_id}/audio.mp3",
        "duration": round(duration, 2),
        "speakers": {
            "Ana": {"id": "Ana", "name": "Ana", "color": "#FFFFFF", "ttsVoice": "Aoede"},
            "Pedro": {"id": "Pedro", "name": "Pedro", "color": "#FFD54F", "ttsVoice": "Puck"},
        },
        "scenes": list(scenes_map.values()),
        "lines": lines_out,
        "vocabulary": [],
        "grammarQuizzes": [],
        "listeningQuizzes": [],
        "reflectionQuestions": [],
    }


def migrate(
    source: Path,
    lesson_id: str,
    title: str,
    title_ja: str,
    media_source_dir: Path | None = None,
    audio_source: Path | None = None,
) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"移行元ファイルが見つかりません: {source}")

    # Rule 5: Always back up legacy assets before touching anything
    backup_source_safely(source)

    if source.suffix.lower() == ".json":
        loaded = json.loads(source.read_text(encoding="utf-8"))
        raw_items = loaded["lines"] if isinstance(loaded, dict) and "lines" in loaded else loaded
    else:
        html_text = source.read_text(encoding="utf-8")
        raw_items = _extract_json_array_from_html(html_text)

    lesson_dir = config.LESSONS_DIR / lesson_id
    media_dest = lesson_dir / "media"
    media_dest.mkdir(parents=True, exist_ok=True)

    lesson_data = convert_legacy_items(raw_items, lesson_id, title, title_ja)
    out_json = lesson_dir / "lesson.json"
    out_json.write_text(
        json.dumps(lesson_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if media_source_dir and media_source_dir.is_dir():
        backup_source_safely(media_source_dir)
        for img_file in media_source_dir.iterdir():
            if img_file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}:
                shutil.copy2(img_file, media_dest / img_file.name)

    if audio_source and audio_source.is_file():
        backup_source_safely(audio_source)
        shutil.copy2(audio_source, lesson_dir / "audio.mp3")

    update_catalog(lesson_data)
    print(f"[migrate_legacy] ✅ 新形式への変換完了: {out_json} ({len(lesson_data['lines'])}文)")
    return out_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="既存のClaude版HTML/JSON・画像・音声を legacy_backup/ に保護したうえで新形式へ移行します。"
    )
    parser.add_argument("--source", required=True, help="移行元の .html または .json パス")
    parser.add_argument("--lesson-id", required=True, help="移行先レッスンID（例: manaus-full）")
    parser.add_argument("--title", default="Manaus Full Edition", help="英語/ポルトガル語タイトル")
    parser.add_argument("--title-ja", default="マナウス完全版", help="日本語タイトル")
    parser.add_argument("--media-dir", default="", help="既存のイラストフォルダ（47枚等）のパス")
    parser.add_argument("--audio", default="", help="既存のMP3音声ファイルのパス")
    args = parser.parse_args()

    migrate(
        source=Path(args.source).expanduser().resolve(),
        lesson_id=args.lesson_id,
        title=args.title,
        title_ja=args.title_ja,
        media_source_dir=Path(args.media_dir).expanduser().resolve() if args.media_dir else None,
        audio_source=Path(args.audio).expanduser().resolve() if args.audio else None,
    )


if __name__ == "__main__":
    main()
