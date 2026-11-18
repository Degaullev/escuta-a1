#!/usr/bin/env python3
"""
Escuta A1 — Step 3 of Pipeline: Dual Quality Audit & Auto-Repair
1. Acoustic Recognition Check: Whisper (`language="pt"`) vs script text
2. Native Prosody & Pedagogical Check: Gemini Multimodal direct audio input
3. Auto-Repair: Rewrites unnatural/clipped A1 lines and re-synthesizes only flagged lines (max 2 retries)
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from synthesize_audio import synthesize_lesson_audio  # noqa: E402

AUDIT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": ["overallPass", "summaryJa", "issues"],
    "properties": {
        "overallPass": {"type": "BOOLEAN"},
        "summaryJa": {"type": "STRING"},
        "issues": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["lineId", "reasonJa", "suggestedPt"],
                "properties": {
                    "lineId": {"type": "STRING"},
                    "reasonJa": {"type": "STRING"},
                    "suggestedPt": {"type": "STRING"},
                    "suggestedJa": {"type": "STRING"},
                },
            },
        },
    },
}


def _normalize_pt(text: str) -> str:
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9\s]", "", stripped).strip()


def run_whisper_stage(
    lines: list[dict[str, Any]], tmp_wav_dir: Path, similarity_threshold: float = 0.78
) -> list[dict[str, Any]]:
    """Stage 1: Transcribes each sentence WAV with Whisper (language='pt') and checks similarity."""
    transcriber_kind = None
    fw_model = None
    ow_model = None

    try:
        from faster_whisper import WhisperModel  # type: ignore

        fw_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        transcriber_kind = "faster-whisper"
    except ImportError:
        try:
            import whisper  # type: ignore

            ow_model = whisper.load_model(config.WHISPER_MODEL_SIZE)
            transcriber_kind = "openai-whisper"
        except ImportError:
            print(
                "[audit_quality] ⚠️ faster-whisper / openai-whisper が未インストールのため Stage 1 をスキップします。"
            )
            return []

    print(f"[audit_quality] Stage 1: {transcriber_kind} (`language='pt'`) で音響認識チェックを実行中...")
    flagged: list[dict[str, Any]] = []

    for ln in lines:
        wav_path = tmp_wav_dir / f"{ln['id']}.wav"
        if not wav_path.exists():
            continue

        if transcriber_kind == "faster-whisper":
            segments, _ = fw_model.transcribe(str(wav_path), language="pt")
            heard = " ".join(seg.text for seg in segments).strip()
        else:
            res = ow_model.transcribe(str(wav_path), language="pt")
            heard = str(res.get("text", "")).strip()

        expected_norm = _normalize_pt(ln["pt"])
        heard_norm = _normalize_pt(heard)
        ratio = difflib.SequenceMatcher(None, expected_norm, heard_norm).ratio()
        print(f"  - [{ln['id']}] 一致率={ratio:.2f} | 台本='{ln['pt']}' | 認識='{heard}'")

        if ratio < similarity_threshold:
            flagged.append(
                {
                    "lineId": ln["id"],
                    "reasonJa": f"Whisper音響認識ズレ（一致率 {ratio:.2f}: '{heard}'）",
                    "heardPt": heard,
                }
            )
    return flagged


def run_gemini_multimodal_audit(
    audio_path: Path,
    lines: list[dict[str, Any]],
    vocabulary: list[dict[str, Any]],
    whisper_flags: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stage 2: Sends audio bytes + script JSON directly to Gemini for native Brazilian audit."""
    from google.genai import types  # type: ignore

    client = config.get_genai_client()
    audio_bytes = audio_path.read_bytes()
    mime_type = "audio/mpeg" if audio_path.suffix.lower() == ".mp3" else "audio/wav"

    audit_prompt = f"""
あなたはブラジル・サンパウロ出身のネイティブ音声監督兼CEFR A1ポルトガル語教師です。
添付された会話音声と台本データを聴き比べて監査してください。

監査項目:
1. ブラジル人が聴いて不自然なイントネーション、音が潰れている箇所、または演技指示の誤読がないか。
2. Whisper第1段階チェックで検出された懸念箇所（{json.dumps(whisper_flags, ensure_ascii=False)}）が実際に聞き取りにくいか。
3. A1学習者向けの日本語訳やコアイメージ解説に誤りがないか。

問題がある文のみ `issues` に含め、自然で明瞭に発音しやすいCEFR A1ブラジルポルトガル語文（`suggestedPt`）を提案してください。問題がなければ `issues` は空配列にしてください。

対象台本:
{json.dumps(lines, ensure_ascii=False, indent=2)}

重要語彙（コアイメージ）:
{json.dumps(vocabulary[:10], ensure_ascii=False, indent=2)}
""".strip()

    print(
        f"[audit_quality] Stage 2: `{config.AUDIT_MODEL}` へ音声マルチモーダル監査リクエストを 1回送信します..."
    )
    response = client.models.generate_content(
        model=config.AUDIT_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            audit_prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AUDIT_RESPONSE_SCHEMA,
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def audit_and_repair_lesson(
    lesson_id: str,
    limit: int = 0,
    max_retries: int = 2,
    use_lite_tts: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    lesson_dir = config.LESSONS_DIR / lesson_id
    lesson_json_path = lesson_dir / "lesson.json"
    if not lesson_json_path.exists():
        raise FileNotFoundError(f"lesson.json が見つかりません: {lesson_json_path}")

    lesson = json.loads(lesson_json_path.read_text(encoding="utf-8"))
    all_lines = lesson.get("lines", [])
    target_lines = all_lines[:limit] if limit > 0 else all_lines

    if dry_run:
        print(
            f"[DRY-RUN] 監査対象: {len(target_lines)}文 | APIリクエスト発生数: 0回\n"
            f"  - Stage 1 (ローカルWhisper): {len(target_lines)}個のWAVをローカル照合（API消費 0回）\n"
            f"  - Stage 2 (本番時 `{config.AUDIT_MODEL}`): 音声マルチモーダル監査 1回（リトライ最大{max_retries}回）"
        )
        return {"overallPass": True, "summaryJa": "Dry-run 正常確認完了", "issues": []}

    tmp_wav_dir = lesson_dir / ".tmp_wavs"
    combined_audio = (
        lesson_dir / "audio.mp3"
        if (lesson_dir / "audio.mp3").exists()
        else tmp_wav_dir / "combined.wav"
    )
    if not combined_audio.exists():
        raise FileNotFoundError(
            f"監査対象の音声ファイルが見つかりません ({combined_audio})。先に synthesize_audio.py を実行してください。"
        )

    attempt = 0
    last_report: dict[str, Any] = {"overallPass": True, "issues": []}

    while attempt <= max_retries:
        print(f"\n=== 品質監査パス {attempt + 1} / {max_retries + 1} ===")
        whisper_flags = run_whisper_stage(target_lines, tmp_wav_dir)
        report = run_gemini_multimodal_audit(
            audio_path=combined_audio,
            lines=target_lines,
            vocabulary=lesson.get("vocabulary", []),
            whisper_flags=whisper_flags,
        )
        last_report = report
        issues = report.get("issues", [])
        print(f"[audit_quality] 監査サマリー: {report.get('summaryJa', '')}")

        if not issues:
            print("[audit_quality] ✅ 全文が品質基準をクリアしました！")
            break

        if attempt == max_retries:
            print(
                f"[audit_quality] ⚠️ 最大リトライ回数（{max_retries}回）に到達したため監査を終了します。"
            )
            break

        # Apply natural A1 rewrites and partially re-synthesize only flagged lines
        flagged_ids: set[str] = set()
        line_lookup = {ln["id"]: ln for ln in all_lines}
        for issue in issues:
            lid = issue["lineId"]
            if lid in line_lookup and issue.get("suggestedPt"):
                print(
                    f"  -> リペア [{lid}]: '{line_lookup[lid]['pt']}' => '{issue['suggestedPt']}' ({issue.get('reasonJa')})"
                )
                line_lookup[lid]["pt"] = issue["suggestedPt"].strip()
                if issue.get("suggestedJa"):
                    line_lookup[lid]["ja"] = issue["suggestedJa"].strip()
                flagged_ids.add(lid)

        if not flagged_ids:
            break

        lesson_json_path.write_text(
            json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        synthesize_lesson_audio(
            lesson_id=lesson_id,
            limit=limit,
            only_line_ids=flagged_ids,
            use_lite=use_lite_tts,
            dry_run=False,
        )
        lesson = json.loads(lesson_json_path.read_text(encoding="utf-8"))
        all_lines = lesson.get("lines", [])
        target_lines = all_lines[:limit] if limit > 0 else all_lines
        attempt += 1

    return last_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Whisper音響認識＋Geminiネイティブ音声監査を行い、不自然な文のみ自動再合成します。"
    )
    parser.add_argument("--lesson-id", default="manaus-demo", help="対象レッスンID")
    parser.add_argument("--limit", type=int, default=0, help="先頭N文のみ監査（例: --limit 3）")
    parser.add_argument("--max-retries", type=int, default=2, help="自動リペアの最大回数（デフォルト: 2）")
    parser.add_argument("--lite", action="store_true", help="リペア再合成時に lite TTS を使用")
    parser.add_argument("--dry-run", action="store_true", help="APIを呼び出さず処理フローと見積もりのみ確認")
    args = parser.parse_args()

    audit_and_repair_lesson(
        lesson_id=args.lesson_id,
        limit=args.limit,
        max_retries=args.max_retries,
        use_lite_tts=args.lite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
