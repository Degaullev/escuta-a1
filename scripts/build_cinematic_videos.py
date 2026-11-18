#!/usr/bin/env python3
"""
Converts high-res Gemini scene illustrations into:
1. Crisp WebP stills (`scene-1.webp`, `scene-2.webp`, `scene-3.webp`)
2. Seamless 6-second 30fps H.264 MP4 ambient loop videos (`scene-1.mp4`, `scene-2.mp4`, `scene-3.mp4`)
   with smooth sinusoidal camera motion (zero loop seam), animated river water-shimmer displacement
   for Scenes 1 & 2, and warm stained-glass sunbeam bokeh shimmer for Scene 3.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageEnhance  # type: ignore

FFMPEG = "/opt/homebrew/bin/ffmpeg"
MEDIA_DIR = Path("/Users/okudayuuya/.gemini/antigravity/scratch/escuta-a1/lessons/manaus-demo/media")
BRAIN_DIR = Path("/Users/okudayuuya/.gemini/antigravity/brain/b824f334-5ed1-4b74-892b-9f45caaebeff")

SOURCES = {
    "scene-1": (BRAIN_DIR / "scene_1_1795007284721.jpg", "water_right"),
    "scene-2": (BRAIN_DIR / "scene_2_1795007311599.jpg", "water_center"),
    "scene-3": (BRAIN_DIR / "scene_3_1795007274709.jpg", "market_light"),
}

OUT_W, OUT_H = 960, 540
FPS = 24
DURATION_SEC = 6
TOTAL_FRAMES = FPS * DURATION_SEC  # 144 frames seamless 2*pi cycle


def render_seamless_mp4(scene_id: str, src_path: Path, effect: str) -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    base_img = Image.open(src_path).convert("RGB")

    # Save crisp 1280x720 WebP still
    still_img = base_img.resize((1280, 720), Image.Resampling.LANCZOS)
    webp_path = MEDIA_DIR / f"{scene_id}.webp"
    still_img.save(webp_path, format="WEBP", quality=90)

    # Overscan base image slightly for smooth sinusoidal camera drift + gentle zoom
    work_w, work_h = int(OUT_W * 1.09), int(OUT_H * 1.09)
    work_base = base_img.resize((work_w, work_h), Image.Resampling.LANCZOS)

    mp4_path = MEDIA_DIR / f"{scene_id}.mp4"
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
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    for f in range(TOTAL_FRAMES):
        theta = (2.0 * math.pi * f) / TOTAL_FRAMES  # exact 0 -> 2pi seamless loop

        # Smooth sinusoidal zoom & pan
        zoom = 1.035 + 0.025 * (0.5 - 0.5 * math.cos(theta))
        crop_w = work_w / zoom
        crop_h = work_h / zoom
        cx = (work_w - crop_w) * (0.5 + 0.35 * math.sin(theta))
        cy = (work_h - crop_h) * (0.5 + 0.25 * math.sin(theta + 1.1))

        frame = work_base.crop((cx, cy, cx + crop_w, cy + crop_h)).resize(
            (OUT_W, OUT_H), Image.Resampling.BILINEAR
        )

        if effect in ("water_right", "water_center"):
            # Subtle horizontal water-ripple shimmer + sunlit specular glints on river region
            overlay = frame.copy()
            band_h = 6
            y_start = int(OUT_H * (0.36 if effect == "water_right" else 0.24))
            x_min = int(OUT_W * (0.44 if effect == "water_right" else 0.28))
            x_max = int(OUT_W * (0.98 if effect == "water_right" else 0.76))

            for y in range(y_start, OUT_H - band_h, band_h):
                depth = (y - y_start) / float(max(1, OUT_H - y_start))
                shift = int(round((1.5 + 3.0 * depth) * math.sin(theta * 2.0 + y * 0.11)))
                if shift != 0:
                    strip = frame.crop((x_min, y, x_max, y + band_h))
                    dest_x = max(0, min(OUT_W - (x_max - x_min), x_min + shift))
                    overlay.paste(strip, (dest_x, y))

            # Gentle sunlight shimmer warmth modulation
            shimmer = 1.0 + 0.028 * math.sin(theta * 2.0)
            overlay = ImageEnhance.Brightness(overlay).enhance(shimmer)
            frame = Image.blend(frame, overlay, alpha=0.55)

        elif effect == "market_light":
            # Warm sunlit rays & floating golden bokeh motes inside Mercado Adolpho Lisboa
            light_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(light_layer)
            ray_alpha = int(18 + 10 * math.sin(theta))
            draw.polygon(
                [(120, 0), (310, 0), (540, OUT_H), (260, OUT_H)],
                fill=(255, 228, 150, ray_alpha),
            )
            for idx in range(14):
                base_x = (idx * 73 + 60) % (OUT_W - 80) + 40
                base_y = (idx * 47 + 40) % (OUT_H - 120) + 30
                mx = base_x + 14.0 * math.sin(theta + idx * 0.9)
                my = base_y + 10.0 * math.cos(theta + idx * 1.3)
                alpha = int(38 + 32 * math.sin(theta * 2.0 + idx))
                r = 2 + (idx % 3)
                draw.ellipse((mx - r, my - r, mx + r, my + r), fill=(255, 240, 185, max(0, alpha)))

            rgba_frame = frame.convert("RGBA")
            frame = Image.alpha_composite(rgba_frame, light_layer).convert("RGB")

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    err = proc.stderr.read() if proc.stderr else b""
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"FFmpeg failed for {scene_id}: {err.decode('utf-8', errors='ignore')}")
    print(f"Generated {webp_path.name} and {mp4_path.name} ({mp4_path.stat().st_size // 1024} KB)")


def main() -> None:
    for sid, (src, eff) in SOURCES.items():
        render_seamless_mp4(sid, src, eff)


if __name__ == "__main__":
    main()
