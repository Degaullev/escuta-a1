#!/usr/bin/env python3
"""
Escuta A1 — Step 1 of Pipeline: CEFR A1 Script & Pedagogical Data Generator
Uses Gemini Structured Outputs (JSON Schema) to generate `lessons/<id>/lesson.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

LESSON_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": [
        "title",
        "titleJa",
        "description",
        "scenes",
        "lines",
        "vocabulary",
        "grammarQuizzes",
        "listeningQuizzes",
        "reflectionQuestions",
    ],
    "properties": {
        "title": {"type": "STRING"},
        "titleJa": {"type": "STRING"},
        "description": {"type": "STRING"},
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "index",
                    "title",
                    "titleJa",
                    "setting",
                    "visualPrompt",
                    "keywords",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "index": {"type": "INTEGER"},
                    "title": {"type": "STRING"},
                    "titleJa": {"type": "STRING"},
                    "setting": {"type": "STRING"},
                    "visualPrompt": {"type": "STRING"},
                    "keywords": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "required": ["id", "pt", "ja", "pronunciationHint"],
                            "properties": {
                                "id": {"type": "STRING"},
                                "pt": {"type": "STRING"},
                                "ja": {"type": "STRING"},
                                "pronunciationHint": {"type": "STRING"},
                            },
                        },
                    },
                },
            },
        },
        "lines": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "index",
                    "sceneId",
                    "speaker",
                    "pt",
                    "ja",
                    "jaGuide",
                    "vocabIds",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "index": {"type": "INTEGER"},
                    "sceneId": {"type": "STRING"},
                    "speaker": {"type": "STRING", "enum": ["Ana", "Pedro"]},
                    "pt": {"type": "STRING"},
                    "ja": {"type": "STRING"},
                    "jaGuide": {"type": "STRING"},
                    "vocabIds": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "vocabulary": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "surface",
                    "lemma",
                    "lineId",
                    "matchTokens",
                    "coreImage",
                    "contextMeaning",
                    "chunkPt",
                    "chunkJa",
                    "clozePt",
                    "clozeAnswer",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "surface": {"type": "STRING"},
                    "lemma": {"type": "STRING"},
                    "lineId": {"type": "STRING"},
                    "matchTokens": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "coreImage": {"type": "STRING"},
                    "contextMeaning": {"type": "STRING"},
                    "chunkPt": {"type": "STRING"},
                    "chunkJa": {"type": "STRING"},
                    "clozePt": {"type": "STRING"},
                    "clozeAnswer": {"type": "STRING"},
                },
            },
        },
        "grammarQuizzes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "title",
                    "prompt",
                    "examples",
                    "hint",
                    "ruleTitle",
                    "explanation",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "prompt": {"type": "STRING"},
                    "examples": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "required": ["lineId", "pt", "ja"],
                            "properties": {
                                "lineId": {"type": "STRING"},
                                "pt": {"type": "STRING"},
                                "ja": {"type": "STRING"},
                            },
                        },
                    },
                    "hint": {"type": "STRING"},
                    "ruleTitle": {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                },
            },
        },
        "listeningQuizzes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "lineId",
                    "question",
                    "options",
                    "correctIndex",
                    "explanation",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "lineId": {"type": "STRING"},
                    "question": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correctIndex": {"type": "INTEGER"},
                    "explanation": {"type": "STRING"},
                },
            },
        },
        "reflectionQuestions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": [
                    "id",
                    "question",
                    "options",
                    "correctIndex",
                    "culturalNote",
                ],
                "properties": {
                    "id": {"type": "STRING"},
                    "question": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correctIndex": {"type": "INTEGER"},
                    "culturalNote": {"type": "STRING"},
                },
            },
        },
    },
}


def build_prompt(topic: str, scene_count: int, line_count: int) -> str:
    return f"""
あなたは第二言語習得理論（SLA）と認知言語学（記号接地・コアイメージ）に精通したブラジルポルトガル語（pt-BR）教材設計者です。

以下の条件で、CEFR A1入門者向けの会話レッスンJSONを生成してください。
- 題材: {topic}
- 場面数: {scene_count} 場面（scene-1 .. scene-{scene_count}）
- 合計文数: 約 {line_count} 文（1文あたり4〜11語程度の短く自然なブラジル日常会話）
- 登場人物:
  - Ana（女性・旅行者/質問役）
  - Pedro（男性・地元の案内役）

必須ルール:
1. ポルトガル語はポルトガル（pt-PT）ではなく、自然なブラジル口語（pt-BR: você, a gente, estar com fome, tomar 等）にすること。
2. 各場面に2〜3個の `keywords`（場面推測キーワード＋カタカナ発音ヒント）を付けること。
3. 重要語句 `vocabulary` には丸暗記訳ではなく、必ず「核となる感覚・空間図式（`coreImage`）」「この場面での意味（`contextMeaning`）」「短い会話チャンク（`chunkPt` / `chunkJa`）」「SRS用穴埋め文（`clozePt` / `clozeAnswer`）」を入れ、各 `line.vocabIds` と対応させること。
4. `grammarQuizzes`（2問）では、劇中の3文を並べて変化部分を `[o]` や `[a]` のように角括弧で囲み、学習者が法則を予測してから読める解説を作ること。
5. `listeningQuizzes`（3〜4問、4択）と `reflectionQuestions`（2問、ブラジル文化コラム付き）を含めること。
""".strip()


def attach_provisional_timestamps(raw_data: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    """Assigns provisional timestamps using exact pause rules until TTS overwrites them."""
    cursor = 0.0
    prev_speaker = None
    prev_scene = None
    scene_bounds: dict[str, list[float]] = {}

    for idx, line in enumerate(raw_data.get("lines", []), start=1):
        line["index"] = idx
        if idx > 1:
            if line["sceneId"] != prev_scene:
                cursor += config.PAUSE_SCENE_SWITCH_MS / 1000.0
            elif line["speaker"] != prev_speaker:
                cursor += config.PAUSE_SPEAKER_SWITCH_MS / 1000.0
            else:
                cursor += config.PAUSE_SAME_SPEAKER_MS / 1000.0

        est_dur = max(2.2, round(len(line.get("pt", "")) * 0.095, 2))
        start_sec = round(cursor, 2)
        end_sec = round(cursor + est_dur, 2)
        line["start"] = start_sec
        line["end"] = end_sec
        cursor = end_sec
        prev_speaker = line["speaker"]
        prev_scene = line["sceneId"]

        bounds = scene_bounds.setdefault(line["sceneId"], [start_sec, end_sec])
        bounds[0] = min(bounds[0], start_sec)
        bounds[1] = max(bounds[1], end_sec)

    for sc in raw_data.get("scenes", []):
        sid = sc["id"]
        b = scene_bounds.get(sid, [0.0, round(cursor, 2)])
        sc["startTime"] = b[0]
        sc["endTime"] = b[1]
        sc["image"] = f"lessons/{lesson_id}/media/{sid}.webp"
        sc.setdefault("video", None)

    return {
        "id": lesson_id,
        "title": raw_data["title"],
        "titleJa": raw_data["titleJa"],
        "level": "CEFR A1",
        "language": "pt-BR",
        "version": "1.0.0",
        "description": raw_data["description"],
        "audioUrl": f"lessons/{lesson_id}/audio.mp3",
        "audioFormat": {
            "codec": "mp3",
            "bitrate": config.MP3_BITRATE,
            "mode": "CBR",
            "pausesMs": {
                "sameSpeaker": config.PAUSE_SAME_SPEAKER_MS,
                "speakerSwitch": config.PAUSE_SPEAKER_SWITCH_MS,
                "sceneSwitch": config.PAUSE_SCENE_SWITCH_MS,
            },
        },
        "duration": round(cursor, 2),
        "speakers": {
            "Ana": {
                "id": "Ana",
                "name": "Ana",
                "nameJa": "アナ",
                "color": "#FFFFFF",
                "ttsVoice": config.SPEAKER_VOICES["Ana"],
                "gender": "female",
            },
            "Pedro": {
                "id": "Pedro",
                "name": "Pedro",
                "nameJa": "ペドロ",
                "color": "#FFD54F",
                "ttsVoice": config.SPEAKER_VOICES["Pedro"],
                "gender": "male",
            },
        },
        "scenes": raw_data["scenes"],
        "lines": raw_data["lines"],
        "vocabulary": raw_data["vocabulary"],
        "grammarQuizzes": raw_data["grammarQuizzes"],
        "listeningQuizzes": raw_data["listeningQuizzes"],
        "reflectionQuestions": raw_data["reflectionQuestions"],
    }


def build_dry_run_payload(topic: str, lesson_id: str) -> dict[str, Any]:
    """Creates a 3-line local test lesson without calling external APIs."""
    raw = {
        "title": f"Demo: {lesson_id}",
        "titleJa": f"{topic}（ドライラン検証用）",
        "description": f"API未呼び出し（--dry-run）で生成されたテスト教材です。題材: {topic}",
        "scenes": [
            {
                "id": "scene-1",
                "index": 1,
                "title": "Encontro inicial",
                "titleJa": "場面1：挨拶と注文",
                "setting": topic,
                "visualPrompt": f"Ana and Pedro in Brazil: {topic}",
                "keywords": [
                    {
                        "id": "kw-1-1",
                        "pt": "bom dia",
                        "ja": "おはよう",
                        "pronunciationHint": "ボン・ジーア",
                    },
                    {
                        "id": "kw-1-2",
                        "pt": "quero",
                        "ja": "〜がほしい",
                        "pronunciationHint": "ケーロ",
                    },
                ],
            }
        ],
        "lines": [
            {
                "id": "line-01",
                "index": 1,
                "sceneId": "scene-1",
                "speaker": "Ana",
                "pt": "Oi, Pedro! Tudo bem com você?",
                "ja": "やあ、ペドロ！元気にしてる？",
                "jaGuide": "やあペドロ、元気？",
                "vocabIds": ["voc-tudo-bem"],
            },
            {
                "id": "line-02",
                "index": 2,
                "sceneId": "scene-1",
                "speaker": "Pedro",
                "pt": "Tudo ótimo! Vamos tomar uma água de coco gelada?",
                "ja": "最高だよ！冷たいココナッツウォーターを飲もうか？",
                "jaGuide": "冷たいココナッツウォーターを飲もうか？",
                "vocabIds": ["voc-gelada"],
            },
            {
                "id": "line-03",
                "index": 3,
                "sceneId": "scene-1",
                "speaker": "Ana",
                "pt": "Boa ideia! Eu quero uma agora, por favor.",
                "ja": "いい考えだね！今すぐ1つほしいな、お願い。",
                "jaGuide": "いいね、今すぐ1つお願いします。",
                "vocabIds": ["voc-quero"],
            },
        ],
        "vocabulary": [
            {
                "id": "voc-tudo-bem",
                "surface": "Tudo bem",
                "lemma": "tudo bem",
                "lineId": "line-01",
                "matchTokens": ["Tudo", "bem"],
                "coreImage": "周りのすべて（tudo）が良い状態（bem）に収まっている安心感。",
                "contextMeaning": "「元気？／大丈夫だよ！」（質問にも返事にも使える万能チャンク）",
                "chunkPt": "Tudo bem com você?",
                "chunkJa": "あなたは元気ですか？",
                "clozePt": "____ ___ com você?",
                "clozeAnswer": "Tudo bem",
            },
            {
                "id": "voc-gelada",
                "surface": "gelada",
                "lemma": "gelado / gelada",
                "lineId": "line-02",
                "matchTokens": ["gelada"],
                "coreImage": "氷（gelo）のようにキンキンに冷えている心地よい感覚。",
                "contextMeaning": "「キンキンに冷えた」（女性名詞 água に合わせて -a）",
                "chunkPt": "uma água de coco gelada",
                "chunkJa": "よく冷えたココナッツウォーター",
                "clozePt": "Vamos tomar uma água de coco ______?",
                "clozeAnswer": "gelada",
            },
            {
                "id": "voc-quero",
                "surface": "quero",
                "lemma": "querer",
                "lineId": "line-03",
                "matchTokens": ["quero"],
                "coreImage": "自分の心が対象に向かって真っすぐ手を伸ばすイメージ。",
                "contextMeaning": "「〜がほしい・〜したい」",
                "chunkPt": "Eu quero uma agora, por favor.",
                "chunkJa": "今すぐ1つください。",
                "clozePt": "Eu _____ uma agora, por favor.",
                "clozeAnswer": "quero",
            },
        ],
        "grammarQuizzes": [
            {
                "id": "gram-01",
                "title": "パターン予測：冷たい飲み物の言い方",
                "prompt": "名詞によって gelado / gelada の語尾がどう変わるか見比べましょう。",
                "examples": [
                    {"lineId": "line-02", "pt": "uma água gelad[a]", "ja": "冷たい水"},
                    {"lineId": "line-02", "pt": "um suco gelad[o]", "ja": "冷たいジュース"},
                    {"lineId": "line-03", "pt": "Bo[a] idei[a]!", "ja": "いい考え！"},
                ],
                "hint": "uma（女性）と um（男性）に注目！",
                "ruleTitle": "女性名詞には -a、男性名詞には -o で音をそろえる",
                "explanation": "água や ideia は女性名詞なので gelada / boa になります。",
            }
        ],
        "listeningQuizzes": [
            {
                "id": "lquiz-01",
                "lineId": "line-02",
                "question": "ペドロは何を飲もうと誘っていますか？",
                "options": ["冷たいココナッツウォーター", "熱いコーヒー", "オレンジジュース", "紅茶"],
                "correctIndex": 0,
                "explanation": "「uma água de coco gelada」と誘っています。",
            }
        ],
        "reflectionQuestions": [
            {
                "id": "ref-01",
                "question": "ブラジルのビーチや街角で定番の水分補給ドリンクは何でしたか？",
                "options": ["緑茶", "冷たいココナッツウォーター（água de coco gelada）", "ホットミルク"],
                "correctIndex": 1,
                "culturalNote": "ブラジルでは緑色の実のまま冷やしたココナッツにストローを刺して飲むのが日常の風景です。",
            }
        ],
    }
    return attach_provisional_timestamps(raw, lesson_id)


def update_catalog(lesson: dict[str, Any]) -> None:
    catalog: dict[str, Any] = {"version": "1.0.0", "lessons": []}
    if config.CATALOG_PATH.exists():
        catalog = json.loads(config.CATALOG_PATH.read_text(encoding="utf-8"))

    entry = {
        "id": lesson["id"],
        "title": lesson["title"],
        "titleJa": lesson["titleJa"],
        "level": lesson.get("level", "CEFR A1"),
        "sceneCount": len(lesson.get("scenes", [])),
        "lineCount": len(lesson.get("lines", [])),
        "duration": lesson.get("duration", 0),
        "badge": f"{len(lesson.get('scenes', []))}場面・{len(lesson.get('lines', []))}文",
        "description": lesson.get("description", ""),
        "path": f"lessons/{lesson['id']}/lesson.json",
    }

    lessons_list = [x for x in catalog.get("lessons", []) if x.get("id") != lesson["id"]]
    lessons_list.append(entry)
    catalog["lessons"] = lessons_list
    config.CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def generate_lesson_script(
    topic: str,
    lesson_id: str,
    scene_count: int = 3,
    line_count: int = 12,
    dry_run: bool = False,
) -> Path:
    lesson_dir = config.LESSONS_DIR / lesson_id
    (lesson_dir / "media").mkdir(parents=True, exist_ok=True)
    out_path = lesson_dir / "lesson.json"

    if dry_run:
        print(
            f"[DRY-RUN] APIリクエスト発生数: 0回（本番時は `{config.TEXT_MODEL}` へ 1回リクエスト）"
        )
        lesson = build_dry_run_payload(topic, lesson_id)
    else:
        print(
            f"[generate_script] モデル `{config.TEXT_MODEL}` へ Structured Output リクエストを 1回送信します..."
        )
        from google.genai import types  # type: ignore

        client = config.get_genai_client()
        response = client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=build_prompt(topic, scene_count, line_count),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LESSON_RESPONSE_SCHEMA,
                temperature=0.6,
            ),
        )
        raw_json = json.loads(response.text)
        lesson = attach_provisional_timestamps(raw_json, lesson_id)

    out_path.write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    update_catalog(lesson)
    print(f"[generate_script] 保存完了: {out_path} ({len(lesson['lines'])}文)")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="題材から CEFR A1 の lesson.json（台本・記号接地・クイズ）を生成します。"
    )
    parser.add_argument("--topic", required=True, help="レッスンの題材・シチュエーション")
    parser.add_argument("--lesson-id", required=True, help="保存先ディレクトリID（例: cafe-sp）")
    parser.add_argument("--scenes", type=int, default=3, help="場面数（デフォルト: 3）")
    parser.add_argument("--lines", type=int, default=12, help="合計文数の目安（デフォルト: 12）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="外部APIを呼び出さずにローカル検証用データを生成",
    )
    args = parser.parse_args()
    generate_lesson_script(
        topic=args.topic,
        lesson_id=args.lesson_id,
        scene_count=args.scenes,
        line_count=args.lines,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
