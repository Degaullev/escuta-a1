#!/usr/bin/env python3
"""
Escuta A1 — Step 4 of Pipeline: Consistent Character Stills & Optional Veo Loop Videos
- Creates/loads fixed Ana & Pedro character reference sheets (`lessons/_shared_characters/`)
- Generates consistent scene illustrations (`lessons/<id>/media/scene-*.webp`)
- Only when `--with-video` is specified, generates 5-8s ambient loop MP4s via Veo (`veo-3.1-generate-preview`)
  for designated key scenes; remaining scenes automatically fall back to still images.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def _extract_image_bytes(response: Any) -> bytes:
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                return inline.data
    raise RuntimeError("画像生成レスポンスから画像バイト列を取得できませんでした。")


def _save_as_webp_or_png(raw_bytes: bytes, dest_webp: Path) -> Path:
    try:
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(raw_bytes))
        img.save(dest_webp, format="WEBP", quality=86)
        return dest_webp
    except ImportError:
        png_path = dest_webp.with_suffix(".png")
        png_path.write_bytes(raw_bytes)
        return png_path


def ensure_character_references(client: Any) -> list[tuple[str, bytes]]:
    """Generates or loads cached Ana & Pedro reference sheets for visual consistency."""
    from google.genai import types  # type: ignore

    config.SHARED_CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    refs: list[tuple[str, bytes]] = []

    for name, desc in config.CHARACTER_PROFILES.items():
        ref_path = config.SHARED_CHARACTERS_DIR / f"{name.lower()}_ref.png"
        if not ref_path.exists():
            print(f"[generate_visuals] キャラクター設定画を初回生成中: {name} (`{config.IMAGE_MODEL}`)")
            prompt = (
                f"Character reference sheet, clean portrait and upper body on neutral warm background, "
                f"consistent facial features and outfit: {desc}"
            )
            resp = client.models.generate_content(
                model=config.IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            )
            ref_path.write_bytes(_extract_image_bytes(resp))
        refs.append((name, ref_path.read_bytes()))
    return refs


def generate_scene_still(
    client: Any,
    char_refs: list[tuple[str, bytes]],
    scene: dict[str, Any],
    dest_webp: Path,
) -> Path:
    """Generates a 16:9 scene illustration referencing Ana & Pedro character sheets."""
    from google.genai import types  # type: ignore

    parts: list[Any] = []
    for name, img_bytes in char_refs:
        parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        parts.append(f"Reference image above is {name}. Keep face, hair, and outfit identical.")

    visual_prompt = scene.get("visualPrompt") or scene.get("setting") or scene.get("title", "")
    parts.append(
        "Create a warm, expressive 16:9 travel storybook illustration in Brazil matching the "
        f"character references above. No text or speech bubbles in image. Scene: {visual_prompt}"
    )

    resp = client.models.generate_content(
        model=config.IMAGE_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    img_bytes = _extract_image_bytes(resp)
    return _save_as_webp_or_png(img_bytes, dest_webp)


def generate_scene_veo_video(
    client: Any,
    scene: dict[str, Any],
    still_path: Path | None,
    dest_mp4: Path,
) -> Path:
    """Generates a 5-8s silent ambient loop MP4 using Veo (`veo-3.1-generate-preview`)."""
    from google.genai import types  # type: ignore

    visual_prompt = scene.get("visualPrompt") or scene.get("setting") or scene.get("title", "")
    loop_prompt = (
        "Subtle, peaceful 6-second seamless ambient Cinemagraph loop in Brazil, "
        "gentle water ripples and warm tropical breeze, camera steady, no spoken dialogue: "
        f"{visual_prompt}"
    )

    kwargs: dict[str, Any] = {
        "model": config.VIDEO_MODEL,
        "prompt": loop_prompt,
    }
    if still_path and still_path.exists() and hasattr(types, "Image"):
        mime = "image/webp" if still_path.suffix.lower() == ".webp" else "image/png"
        kwargs["image"] = types.Image(image_bytes=still_path.read_bytes(), mime_type=mime)

    operation = client.models.generate_videos(**kwargs)
    print(f"  -> Veo動画生成ジョブ待機中 ({scene['id']})...")
    while not operation.done:
        time.sleep(8)
        operation = client.operations.get(operation)

    generated_videos = getattr(operation.response, "generated_videos", None) or []
    if not generated_videos:
        raise RuntimeError(f"Veo動画生成結果が空でした ({scene['id']})")

    video_obj = generated_videos[0].video
    client.files.download(file=video_obj)
    video_obj.save(str(dest_mp4))
    return dest_mp4


def generate_lesson_visuals(
    lesson_id: str,
    limit: int = 0,
    with_video: bool = False,
    video_scene_ids: set[str] | None = None,
    dry_run: bool = False,
) -> None:
    lesson_dir = config.LESSONS_DIR / lesson_id
    lesson_json_path = lesson_dir / "lesson.json"
    if not lesson_json_path.exists():
        raise FileNotFoundError(f"lesson.json が見つかりません: {lesson_json_path}")

    lesson = json.loads(lesson_json_path.read_text(encoding="utf-8"))
    media_dir = lesson_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    scenes: list[dict[str, Any]] = lesson.get("scenes", [])
    target_scenes = scenes[:limit] if limit > 0 else scenes

    if with_video and not video_scene_ids:
        # Default to the opening key scene unless user explicitly lists multiple scenes
        video_scene_ids = {target_scenes[0]["id"]} if target_scenes else set()

    if dry_run:
        missing_refs = sum(
            1
            for name in config.CHARACTER_PROFILES
            if not (config.SHARED_CHARACTERS_DIR / f"{name.lower()}_ref.png").exists()
        )
        vid_count = (
            len([s for s in target_scenes if s["id"] in (video_scene_ids or set())])
            if with_video
            else 0
        )
        print(
            f"[DRY-RUN] APIリクエスト発生数: 0回\n"
            f"  - 本番時 キャラ設定画生成 (`{config.IMAGE_MODEL}`): 初回のみ {missing_refs}回\n"
            f"  - 本番時 場面イラスト生成 (`{config.IMAGE_MODEL}`): {len(target_scenes)}回\n"
            f"  - 本番時 Veoショート動画生成 (`{config.VIDEO_MODEL}`): {vid_count}回"
            f"（未生成場面は静止画へ自動フォールバック）"
        )
        return

    client = config.get_genai_client()
    char_refs = ensure_character_references(client)

    for sc in target_scenes:
        sid = sc["id"]
        dest_webp = media_dir / f"{sid}.webp"
        print(f"[generate_visuals] 場面静止画を生成中 [{sid}]: {sc.get('titleJa', sid)}")
        saved_img = generate_scene_still(client, char_refs, sc, dest_webp)
        sc["image"] = f"lessons/{lesson_id}/media/{saved_img.name}"

        if with_video and video_scene_ids and sid in video_scene_ids:
            dest_mp4 = media_dir / f"{sid}.mp4"
            print(f"[generate_visuals] Veoループ動画を生成中 [{sid}] (`{config.VIDEO_MODEL}`)")
            generate_scene_veo_video(client, sc, saved_img, dest_mp4)
            sc["video"] = f"lessons/{lesson_id}/media/{dest_mp4.name}"
        else:
            # Ensure clean fallback to still image when video is not generated
            if not (sc.get("video") and (config.PROJECT_ROOT / sc["video"]).exists()):
                sc["video"] = None

    lesson_json_path.write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[generate_visuals] ビジュアルパスを更新しました: {lesson_json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ana/Pedro一貫キャラクター静止画と、オプションのVeo情景ループ動画を生成します。"
    )
    parser.add_argument("--lesson-id", default="manaus-demo", help="対象レッスンID")
    parser.add_argument("--limit", type=int, default=0, help="先頭N場面のみ生成")
    parser.add_argument(
        "--with-video",
        action="store_true",
        help="指定時のみ重要場面で Veo (veo-3.1-generate-preview) ショート動画を生成",
    )
    parser.add_argument(
        "--video-scenes",
        default="",
        help="動画を生成する場面IDをカンマ区切り指定（省略時は scene-1 のみ）",
    )
    parser.add_argument("--dry-run", action="store_true", help="APIを呼び出さずに見積もりのみ確認")
    args = parser.parse_args()

    vid_set = (
        {x.strip() for x in args.video_scenes.split(",") if x.strip()}
        if args.video_scenes
        else None
    )
    generate_lesson_visuals(
        lesson_id=args.lesson_id,
        limit=args.limit,
        with_video=args.with_video,
        video_scene_ids=vid_set,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
