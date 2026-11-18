#!/usr/bin/env python3
"""
Escuta A1 (Gemini Edition) — Centralized Pipeline Configuration
Loads GEMINI_API_KEY and switchable model IDs from `.env` at the project root.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = PROJECT_ROOT / "lessons"
CATALOG_PATH = LESSONS_DIR / "index.json"
SHARED_CHARACTERS_DIR = LESSONS_DIR / "_shared_characters"
LEGACY_BACKUP_DIR = PROJECT_ROOT / "legacy_backup"
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_file(env_path: Path) -> None:
    """Loads `.env` via python-dotenv if available, with a pure-Python fallback."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=env_path, override=False)
        return
    except ImportError:
        pass

    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(ENV_PATH)

# API Key (never hardcoded)
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# Switchable Model Identifiers
TEXT_MODEL: str = os.environ.get("GEMINI_TEXT_MODEL", "gemini-4-argon")
AUDIT_MODEL: str = os.environ.get("GEMINI_AUDIT_MODEL", "gemini-4-argon")
TTS_MODEL: str = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
TTS_LITE_MODEL: str = os.environ.get(
    "GEMINI_TTS_LITE_MODEL", "gemini-3.8-flash-lite-tts"
)
IMAGE_MODEL: str = os.environ.get(
    "GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image-preview"
)
VIDEO_MODEL: str = os.environ.get("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview")
WHISPER_MODEL_SIZE: str = os.environ.get("WHISPER_MODEL_SIZE", "small")

# Fixed Speaker Profiles
SPEAKER_VOICES: dict[str, str] = {
    "Ana": os.environ.get("ANA_TTS_VOICE", "Aoede"),
    "Pedro": os.environ.get("PEDRO_TTS_VOICE", "Puck"),
}

# Gemini 3.8 TTS style metadata (MUST be passed in speech_metadata.style, NEVER in spoken text)
A1_PT_BR_STYLE: str = (
    "Natural Brazilian Portuguese (pt-BR), warm friendly conversational delivery, "
    "articulated clearly and about 15% slower for A1 language learners"
)

# Exact Silence Intervals (milliseconds)
PAUSE_SAME_SPEAKER_MS: int = 350
PAUSE_SPEAKER_SWITCH_MS: int = 650
PAUSE_SCENE_SWITCH_MS: int = 1400

# Audio Output Spec (iOS Safari seek-safe CBR MP3)
MP3_BITRATE: str = "128k"
SAMPLE_RATE_HZ: int = 24000

# Consistent Character Sheet Prompts
CHARACTER_PROFILES: dict[str, str] = {
    "Ana": (
        "Ana, a friendly 27-year-old Brazilian woman from São Paulo, warm brown eyes, "
        "shoulder-length wavy dark brown hair, wearing a crisp white casual linen top "
        "and a small teal shoulder bag, warm storybook travel illustration style."
    ),
    "Pedro": (
        "Pedro, a cheerful 29-year-old Brazilian man living in Manaus, short curly black hair, "
        "friendly smile, wearing a sunny mustard-yellow short-sleeve shirt (#FFD54F), "
        "warm storybook travel illustration style."
    ),
}


def require_api_key() -> str:
    """Validates GEMINI_API_KEY before making live Gemini API requests."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise RuntimeError(
            "GEMINI_API_KEY が設定されていません。プロジェクト直下に `.env` を作成し、"
            "GEMINI_API_KEY=... を設定してください（`.env.example` 参照）。"
        )
    return GEMINI_API_KEY


def get_genai_client():
    """Returns an initialized google.genai.Client (requires google-genai >= 2.25.0)."""
    api_key = require_api_key()
    from google import genai  # type: ignore

    return genai.Client(api_key=api_key)
