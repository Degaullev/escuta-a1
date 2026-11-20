#!/usr/bin/env python3
"""
Generates high-motion, expressive 720p 6s Studio Ghibli-style AI animations
using `gemini-omni-1.2-flash` First-Frame-to-Video (NO `last_frame` lock, allowing
natural character movement, eating, sipping, pointing, laughing, and camera motion!).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from run_gemini_38_tts_and_omni_video import (  # noqa: E402
    API_BASE,
    api_json_request,
    download_generated_video,
    redact,
    upload_file_resumable,
)

CHOREOGRAPHY_1_TO_3: dict[str, str] = {
    "manaus-01-teatro:scene-1": (
        "Dynamic 2D Studio Ghibli-style anime motion, lively camera push-in and gentle tilt up. "
        "Ana walks forward onto the plaza with sparkling eyes, turns toward Pedro, and points excitedly "
        "up at the grand pink Teatro Amazonas opera house while her wavy dark hair sways in the breeze; "
        "Pedro smiles broadly and gestures with open arms welcoming her as birds fly across the bright blue sky "
        "and visitors stroll in the background. Use this image as the starting frame."
    ),
    "manaus-01-teatro:scene-2": (
        "Expressive 2D Studio Ghibli-style anime character animation. Pedro points upward toward the "
        "glittering green, yellow, and blue tiled dome of Teatro Amazonas shining in tropical sunlight; "
        "Ana steps joyfully onto the black-and-white wave-patterned stone pavement, holds up her smartphone, "
        "and leans in beside smiling Pedro to snap a cheerful travel photo together. Use this image as the starting frame."
    ),
    "manaus-01-teatro:scene-3": (
        "Warm golden-hour 2D Studio Ghibli-style anime motion outside Teatro Amazonas. Pedro gestures toward "
        "the historic street while explaining its rubber-boom story; Ana claps her hands happily in amazement, "
        "street musicians play lively acoustic music in the background, and the two walk cheerfully toward a cozy "
        "outdoor café table with steaming coffee cups. Use this image as the starting frame."
    ),
    "manaus-02-xcaboquinho:scene-1": (
        "Vibrant sunny morning 2D Studio Ghibli-style anime animation at a lively Manaus regional breakfast café. "
        "Pedro waves warmly and pulls out a wooden chair inviting Ana to sit while smiling brightly; Ana walks up "
        "to the colorful breakfast table looking delighted as aromatic steam rises from fresh bread and coffee, "
        "and café staff bustle cheerfully in the background. Use this image as the starting frame."
    ),
    "manaus-02-xcaboquinho:scene-2": (
        "Appetizing, expressive 2D Studio Ghibli-style anime food and character animation. Pedro points proudly "
        "at the warm crusty X-Caboquinho sandwich as melted grilled white queijo coalho cheese stretches slightly "
        "over golden fried plantain and bright orange tucumã slices with gentle steam rising; Ana picks up the "
        "sandwich with both hands, takes an eager bite, and her eyes light up with pure joy. Use this image as the starting frame."
    ),
    "manaus-02-xcaboquinho:scene-3": (
        "Cozy 2D Studio Ghibli-style anime breakfast animation. Fresh hot black coffee is poured smoothly into "
        "a cup with curling white steam beside a plate of warm orange-yellow cooked pupunha palm fruit; "
        "Pedro offers a piece of pupunha with a fork while Ana lifts her coffee cup with both hands, takes a "
        "happy sip, and smiles warmly. Use this image as the starting frame."
    ),
    "manaus-03-tacaca:scene-1": (
        "Lively twilight 2D Studio Ghibli-style anime street scene in Largo de São Sebastião under glowing warm "
        "festive lights. Steam billows up from large pots at the busy tacacá street stall as the vendor ladles "
        "hot broth and happy locals chat in line; Ana points eagerly at the stall and holds up one finger to "
        "order a gourd bowl while Pedro nods and grins beside her. Use this image as the starting frame."
    ),
    "manaus-03-tacaca:scene-2": (
        "Vivid 2D Studio Ghibli-style anime street-food close-up motion. Hot golden tucupi broth with pink shrimp, "
        "translucent tapioca goma, and green jambu leaves swirls with rich rising steam inside a patterned cuia "
        "gourd bowl; Ana receives the hot gourd carefully in both hands, reacts to the warmth, and blows gently "
        "across the steaming surface while Pedro smiles and points out the ingredients. Use this image as the starting frame."
    ),
    "manaus-03-tacaca:scene-3": (
        "Playful, expressive 2D Studio Ghibli-style anime character reaction. Ana takes a sip of tacacá from the "
        "patterned cuia gourd bowl, pauses in cute surprise, touches her tingling lips with her fingertips as "
        "her eyes widen, and then bursts into a delighted laugh while Pedro laughs heartily and gives a thumbs-up "
        "under the warm evening lights of Manaus. Use this image as the starting frame."
    ),
}


def generate_first_frame_dynamic_video(
    lesson_id: str, scene_id: str, still_path: Path, prompt: str, dest_mp4: Path
) -> str:
    mime = "image/webp" if still_path.suffix.lower() == ".webp" else "image/jpeg"
    uri, uploaded_mime = upload_file_resumable(still_path, mime)

    payload: dict[str, Any] = {
        "model": "gemini-omni-1.2-flash",
        "store": True,
        "input": [
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

    inter_id = resp.get("id")
    status = resp.get("status", "completed")
    while status in ("queued", "in_progress") and inter_id:
        time.sleep(6)
        resp = api_json_request("GET", f"{API_BASE}/v1beta/interactions/{inter_id}", timeout=60)
        status = resp.get("status", "completed")

    if status != "completed":
        raise RuntimeError(f"{lesson_id}/{scene_id} ended with status={status}")

    video_uri = None
    for step in resp.get("steps", []):
        if step.get("type") == "model_output":
            for item in step.get("content", []):
                if item.get("type") == "video" and item.get("uri"):
                    video_uri = item["uri"]
    if not video_uri:
        raise RuntimeError(f"No video URI in response for {lesson_id}/{scene_id}")

    download_generated_video(video_uri, dest_mp4)
    kb = dest_mp4.stat().st_size // 1024
    return f"{lesson_id}/{scene_id} ({kb} KB)"


def main() -> None:
    target_lessons = ["manaus-01-teatro", "manaus-02-xcaboquinho", "manaus-03-tacaca"]
    jobs: list[tuple[str, str, Path, str, Path]] = []

    for lid in target_lessons:
        media_dir = config.LESSONS_DIR / lid / "media"
        for sid in ("scene-1", "scene-2", "scene-3"):
            key = f"{lid}:{sid}"
            still_webp = media_dir / f"{sid}.webp"
            out_mp4 = media_dir / f"{sid}.mp4"
            jobs.append((lid, sid, still_webp, CHOREOGRAPHY_1_TO_3[key], out_mp4))

    print(f"=== Gemini Omni 1.2 Flash 720p ダイナミックAI動画生成（全{len(jobs)}場面・3並列×3ウェーブ）===")
    # Run in 3 waves of 3 concurrent requests so we stay comfortably within RPM limits
    for w_idx in range(0, len(jobs), 3):
        wave = jobs[w_idx : w_idx + 3]
        print(f"\n--- Wave {(w_idx // 3) + 1}/3 ({[f'{x[0]}:{x[1]}' for x in wave]}) ---")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = {
                pool.submit(generate_first_frame_dynamic_video, *job): f"{job[0]}:{job[1]}"
                for job in wave
            }
            for fut in as_completed(futs):
                k = futs[fut]
                try:
                    info = fut.result()
                    print(f"  [Omni 720p OK] {info}")
                except Exception as exc:
                    print(f"  [ERROR] {k} -> {redact(str(exc))}", file=sys.stderr)
                    raise

    # Add cache-buster query param `?v=dyn720` to lessons 1-3 so mobile/desktop browsers reload immediately
    stamp = f"dyn{int(time.time())}"
    for lid in target_lessons:
        lpath = config.LESSONS_DIR / lid / "lesson.json"
        lesson = json.loads(lpath.read_text(encoding="utf-8"))
        for sc in lesson["scenes"]:
            sid = sc["id"]
            sc["video"] = f"lessons/{lid}/media/{sid}.mp4?v={stamp}"
        lpath.write_text(json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n✅ 最初の3課（全9場面）の720pダイナミックAI動画化が完了しました！")


if __name__ == "__main__":
    main()
