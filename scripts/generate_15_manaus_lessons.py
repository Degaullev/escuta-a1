#!/usr/bin/env python3
"""
Generates 15 authentic, deeply researched Pre-A1 / CEFR A1 Manaus lessons
grounded in Brazilian Portuguese news & travel blogs (Portal Amazônia, A Crítica,
Veredicto Manauara, Porto de Manaus, Manaus Cidade Criativa).
Designed for ~80% immediate comprehensibility for beginners.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from generate_script import attach_provisional_timestamps  # noqa: E402
from run_gemini_38_tts_and_omni_video import API_BASE, api_json_request  # noqa: E402

MANAUS_15_TOPICS: list[dict[str, str]] = [
    {
        "id": "manaus-01-teatro",
        "category": "history",
        "badge": "🏛 歴史・街歩き ①",
        "topic": "Teatro Amazonas（アマゾナス劇場）：森の真ん中にあるピンク色の美しいオペラハウス",
        "facts": (
            "Largo de São Sebastiãoにある1896年開館のピンク色の劇場。ゴム景気（Ciclo da Borracha）の時代に建てられた。"
            "丸屋根（cúpula）は緑・黄・青・白の3万6千枚のタイルでブラジル国旗の色を表し、巨大魚ピラルクーの鱗にも例えられる。"
            "昔は馬車の音でオペラの邪魔にならないよう、劇場前の道路にゴムのブロックが敷かれていた。白黒の波模様の石畳も有名。"
        ),
    },
    {
        "id": "manaus-02-xcaboquinho",
        "category": "food",
        "badge": "🍽 グルメ・市場 ①",
        "topic": "Café Regional e X-Caboquinho（マナウスの朝ごはんと名物サンドイッチ）",
        "facts": (
            "マナウス市の無形文化遺産である朝食サンドイッチ『X-Caboquinho（シース・カボキーニョ）』。"
            "フランスパン（pão francês）に、黄色いヤシの実トゥクマン（tucumã）、焼いたチーズ（queijo coalho）、"
            "甘い揚げバナナ（banana frita）を挟む。さらに茹でたホクホクのププーニャ（pupunha cozida）をブラックコーヒーと食べるのが定番。"
        ),
    },
    {
        "id": "manaus-03-tacaca",
        "category": "food",
        "badge": "🍽 グルメ・市場 ②",
        "topic": "Tacacá no Largo（夕暮れの広場で飲む、唇がしびれる熱いスープ『タカカ』）",
        "facts": (
            "夕方になるとLargo de São Sebastiãoの屋台（barraca）で行列ができるアマゾンの伝統スープ『tacacá（タカカ）』。"
            "ひょうたんのお椀（cuia）で熱々を飲む。黄色いキャッサバ発酵スープ（tucupi）、とろみのあるタピオカ（goma）、"
            "干しエビ（camarão）、そして唇や舌がビリビリしびれる不思議なハーブ『ジャンブー（jambu）』が入っている。"
        ),
    },
    {
        "id": "manaus-04-ponta-negra",
        "category": "nature",
        "badge": "🌿 自然・川辺 ①",
        "topic": "Pôr do Sol na Ponta Negra（ポンタ・ネグラの黒い川ビーチと夕日）",
        "facts": (
            "マナウス市民が一番好きな都会のリバービーチ『Praia da Ponta Negra』。海ではなく黒いネグロ川（Rio Negro）の砂浜。"
            "広い遊歩道（calçadão）を散歩しながら、夕方に見る燃えるようなオレンジ色の夕日（pôr do sol）が絶景。"
            "散歩のお供には冷たいクプアスやタペレバのアイスクリーム（sorvete）が大人気。"
        ),
    },
    {
        "id": "manaus-05-musa",
        "category": "nature",
        "badge": "🌿 自然・川辺 ②",
        "topic": "Torre do MUSA（アマゾン博物館MUSAの42メートル展望タワー）",
        "facts": (
            "マナウス市内にある100ヘクタールの原生林『MUSA（Museu da Amazônia）』。"
            "高さ42メートルの鉄製展望タワー（torre alta）の階段を登ると、ジャングルの木々の上（copa das árvores）に出て、"
            "360度見渡す限りの『緑の海（mar verde）』と色鮮やかな鳥（トゥカーノやコンゴウインコ）が見える。"
        ),
    },
    {
        "id": "manaus-06-boto",
        "category": "nature",
        "badge": "🌿 自然・川辺 ③",
        "topic": "O Boto-Cor-de-Rosa（アマゾンのピンク色のカワイルカと満月の伝説）",
        "facts": (
            "ネグロ川に生息する世界最大級の淡水イルカ『boto-cor-de-rosa（ピンクイルカ）』。"
            "水中からひょっこりピンク色の顔を出す姿がとても可愛くて優しい。"
            "アマゾンの民話（lenda）では、満月の祭りの夜になると白いスーツと帽子をかぶったハンサムな若者に変身して踊りに来ると語り継がれている。"
        ),
    },
    {
        "id": "manaus-07-peixe",
        "category": "food",
        "badge": "🍽 グルメ・市場 ③",
        "topic": "Tambaqui e Pirarucu（アマゾンの王様魚タンバキと巨大魚ピラルクー）",
        "facts": (
            "マナウスの昼ごはんの主役は川の魚。『tambaqui（タンバキ）』は炭火焼き（assado na brasa）のリブ（costelinha）が絶品。"
            "『pirarucu（ピラルクー）』は体長2メートルを超える世界最大級の淡水魚で、細かい小骨がほとんどなく肉厚で食べやすく、"
            "『アマゾンのタラ（bacalhau da Amazônia）』とも呼ばれる。ライム（limão）を絞ってファリーニャと食べる。"
        ),
    },
    {
        "id": "manaus-08-porto-redes",
        "category": "culture",
        "badge": "🎭 文化・暮らし ①",
        "topic": "Barco e Redes no Porto（浮き桟橋の港とカラフルなハンモック船の旅）",
        "facts": (
            "ネグロ川は雨季と乾季で水位が10メートル以上変わるため、マナウス港（Porto de Manaus）は水に浮く巨大な浮き桟橋（porto flutuante）になっている。"
            "アマゾンの町々を結ぶ2階建ての定期船（barco regional）では、乗客が色とりどりのハンモック（rede）をデッキに並べて吊るし、"
            "川風に吹かれながらおしゃべりして旅をする。"
        ),
    },
    {
        "id": "manaus-09-bosque-inpa",
        "category": "nature",
        "badge": "🌿 自然・川辺 ④",
        "topic": "Peixe-Boi no Bosque da Ciência（『科学の森』の優しいマナティーとナマケモノ）",
        "facts": (
            "国立アマゾン研究所（INPA）の中にある緑豊かな公園『Bosque da Ciência』。"
            "保護されたアマゾンマナティー『peixe-boi（文字通りには牛の魚！）』が大きな水槽でゆったり草を食べる姿を水中窓から観察できる。"
            "木の上をゆっくり動くナマケモノ（preguiça）や、マナウス固有の小さな白襟ザル『sauim-de-coleira』にも出会える。"
        ),
    },
    {
        "id": "manaus-10-praia-da-lua",
        "category": "nature",
        "badge": "🌿 自然・川辺 ⑤",
        "topic": "Lancha para a Praia da Lua（ボートで10分！三日月形の白い砂浜『月のビーチ』）",
        "facts": (
            "Marina do Davi（ダヴィ港）から小型スピードボート（lancha）に乗って約10分で着く『Praia da Lua（月のビーチ）』。"
            "上空から見ると本当に三日月（lua crescente）の形をした真っ白な砂浜が広がる。"
            "ネグロ川の黒い水は実はとても清潔で温かく（酸性のタンニンを含むため蚊も少ない！）、ぷかぷか水浴び（banho de rio）を楽しむ天国。"
        ),
    },
    {
        "id": "manaus-11-seringal",
        "category": "history",
        "badge": "🏛 歴史・街歩き ②",
        "topic": "Museu do Seringal（森のゴム農園博物館と『白いミルク』ラテックス）",
        "facts": (
            "ボートで川と小川（igarapé）を通って行く野外博物館『Museu do Seringal Vila Paraíso』（映画『A Selva』のセットを保存）。"
            "森の中のゴムの木（seringueira）の幹に斜めの切り込みを入れると、真っ白なミルクのような樹液（leite branco / látex）がポタポタ出てくる。"
            "これを煙で燻して丸いゴムの塊を作り、100年前のマナウスに莫大な富をもたらした。"
        ),
    },
    {
        "id": "manaus-12-cachoeira",
        "category": "nature",
        "badge": "🌿 自然・川辺 ⑥",
        "topic": "Cachoeira Fresca（『滝の大地』プレジデンチ・フィゲイレードの涼しい滝）",
        "facts": (
            "マナウスから北へ約100kmにある『Presidente Figueiredo』は、100以上の滝があることから『Terra das Cachoeiras（滝の大地）』と呼ばれる週末リゾート。"
            "暑いマナウスから森の小道（trilha）を抜けると、琥珀色の冷たくて気持ちいい滝（cachoeira fresca）と神秘的な砂岩の洞窟（gruta）が現れる。"
        ),
    },
    {
        "id": "manaus-13-boi-bumba",
        "category": "culture",
        "badge": "🎭 文化・暮らし ②",
        "topic": "Azul ou Vermelho? Boi-Bumbá!（青か赤か！アマゾン最大の牛祭りパリンチンス）",
        "facts": (
            "アマゾン最大の民俗音楽祭『Festival de Parintins（ボイ・ブンバ）』。マナウスの広場でも毎週末のように練習やイベントが開かれる。"
            "青い牛『Boi Caprichoso（額に青い星）』と、赤い牛『Boi Garantido（額に赤いハート）』の2チームに分かれて歌（toada）と太鼓で競う。"
            "マナウスでは『Qual é o seu boi? Azul ou vermelho?（君の牛はどっち？青？赤？）』が定番の挨拶！"
        ),
    },
    {
        "id": "manaus-14-frutas-sucos",
        "category": "food",
        "badge": "🍽 グルメ・市場 ④",
        "topic": "Suco de Cupuaçu e Guaraná（甘酸っぱいクプアスと本場アマゾンのガラナ）",
        "facts": (
            "マナウスのジューススタンドには南国ならではの果物が並ぶ。『cupuaçu（クプアス）』はカカオの親戚で、白いクリーミーな果肉と甘酸っぱい香りが特徴。"
            "そして日本で炭酸飲料として知られる『guaraná（ガラナ）』はアマゾン（マウエス地方）原産の赤い実で、"
            "マナウスではガラナシロップと氷・ピーナッツ等をミキサーにかけた濃厚エネルギードリンクとしてもよく飲まれる。"
        ),
    },
    {
        "id": "manaus-15-chuva-ponte",
        "category": "culture",
        "badge": "🎭 文化・暮らし ③",
        "topic": "Chuva da Tarde e Ponte Rio Negro（午後のスコールと全長3.6kmのリオ・ネグロ大橋）",
        "facts": (
            "赤道直下のマナウスでは、晴れていても午後に突然バケツをひっくり返したようなスコール『chuva da tarde（午後の雨）』が20〜30分降り、すぐカラッと晴れて涼しい風が吹く。"
            "地元の人はカフェで雨宿りしながら『Já vai passar!（すぐ止むよ！）』と笑う。"
            "雨上がりの澄んだ空の下、ネグロ川を横断する全長3.6kmの美しい斜張橋『Ponte Rio Negro』が夕日に輝く。"
        ),
    },
]

SCHEMA_LOWER: dict[str, Any] = {
    "type": "object",
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
        "title": {"type": "string"},
        "titleJa": {"type": "string"},
        "description": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
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
                    "id": {"type": "string"},
                    "index": {"type": "integer"},
                    "title": {"type": "string"},
                    "titleJa": {"type": "string"},
                    "setting": {"type": "string"},
                    "visualPrompt": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "pt", "ja", "pronunciationHint"],
                            "properties": {
                                "id": {"type": "string"},
                                "pt": {"type": "string"},
                                "ja": {"type": "string"},
                                "pronunciationHint": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
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
                    "id": {"type": "string"},
                    "index": {"type": "integer"},
                    "sceneId": {"type": "string"},
                    "speaker": {"type": "string", "enum": ["Ana", "Pedro"]},
                    "pt": {"type": "string"},
                    "ja": {"type": "string"},
                    "jaGuide": {"type": "string"},
                    "vocabIds": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
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
                    "id": {"type": "string"},
                    "surface": {"type": "string"},
                    "lemma": {"type": "string"},
                    "lineId": {"type": "string"},
                    "matchTokens": {"type": "array", "items": {"type": "string"}},
                    "coreImage": {"type": "string"},
                    "contextMeaning": {"type": "string"},
                    "chunkPt": {"type": "string"},
                    "chunkJa": {"type": "string"},
                    "clozePt": {"type": "string"},
                    "clozeAnswer": {"type": "string"},
                },
            },
        },
        "grammarQuizzes": {
            "type": "array",
            "items": {
                "type": "object",
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
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "prompt": {"type": "string"},
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["lineId", "pt", "ja"],
                            "properties": {
                                "lineId": {"type": "string"},
                                "pt": {"type": "string"},
                                "ja": {"type": "string"},
                            },
                        },
                    },
                    "hint": {"type": "string"},
                    "ruleTitle": {"type": "string"},
                    "explanation": {"type": "string"},
                },
            },
        },
        "listeningQuizzes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "lineId",
                    "question",
                    "options",
                    "correctIndex",
                    "explanation",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "lineId": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correctIndex": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
            },
        },
        "reflectionQuestions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "question",
                    "options",
                    "correctIndex",
                    "culturalNote",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correctIndex": {"type": "integer"},
                    "culturalNote": {"type": "string"},
                },
            },
        },
    },
}


def build_super_a1_prompt(item: dict[str, str]) -> str:
    return f"""
あなたはブラジルポルトガル語（pt-BR）の超入門者（Pre-A1〜CEFR A1前半）向け教材デザイナーです。
ブラジルの現地メディア・旅行ブログから収集した以下の正確なマナウス文化・観光情報をもとに、
**「超初心者が映像と一緒に聞いて最初から8割すぐわかる（Comprehensible Input 80%）」** 会話レッスンJSONを作成してください。

【レッスンID】: {item['id']}
【テーマ】: {item['topic']}
【現地ポルトガル語記事に基づく文化ディテール】:
{item['facts']}

【絶対厳守の難易度・構成ルール】:
1. **超シンプル＆超短文（Pre-A1〜A1）**:
   - 全3場面（`scene-1`, `scene-2`, `scene-3`）、合計 **10文**（`line-01` 〜 `line-10`）。
   - **1文は必ず 3語〜8語 以内** の短い自然な口語（現在形中心、複雑な関係代名詞や接続法は一切禁止！）。
   - カタカナや英語から推測しやすい語（`teatro`, `rosa`, `café`, `banana`, `suco`, `foto`, `azul`, `barco`, `museu`, `sol`, `música` 等）と、超基本チャンク（`Olha!`, `Que lindo!`, `Que gostoso!`, `É muito grande!`, `Eu quero...`, `Eu gosto de...`, `Vamos...!`, `Aqui tem...`, `Muito bom!`, `Por favor!`）を積極的に使い、初見でも8割推測できる優しい文にすること。
2. **登場人物**:
   - `Ana`（サンパウロから来た旅行者・女性）と `Pedro`（マナウス在住の友人・男性）の掛け合い。
3. **各場面の `visualPrompt`（英語で詳細に記述）**:
   - 必ず以下の外見指定を含めること:
     "Lush 16:9 Studio Ghibli-inspired anime travel illustration in Manaus, Brazil, no text or speech bubbles. Ana (27yo Brazilian woman, wavy shoulder-length dark brown hair, crisp white sleeveless linen top, small teal crossbody strap) and Pedro (29yo Brazilian man, short curly black hair, sunny mustard-yellow short-sleeve collared shirt)..." に続けて、その場面の具体的な風景・食べ物・動物・建物を鮮やかに英語で描写すること。
4. **記号接地データ `vocabulary`（10〜14個）**:
   - 各文の重要語について、`id`（例: `voc-01`）、`surface`、`lemma`、`lineId`、`matchTokens`（文中の単語そのままの配列）、①核となるコアイメージ（`coreImage`）、②文脈での意味（`contextMeaning`）、③短いチャンク（`chunkPt` / `chunkJa`）、④SRS穴埋め（`clozePt` / `clozeAnswer`）を作成し、各 `line.vocabIds` と正確に一致させること。
5. **クイズ＆文化振り返り**:
   - `grammarQuizzes`: 2問（劇中のやさしい3例文を並べ、変化箇所を `[o]` / `[a]` のように角括弧で囲んで法則を予測させる）。
   - `listeningQuizzes`: 4問（4択、`correctIndex` は 0〜3）。
   - `reflectionQuestions`: 2問（3択、`culturalNote` に上記の現地マナウス豆知識を楽しく詳しく解説する）。
""".strip()


def generate_one_lesson(item: dict[str, str]) -> dict[str, Any]:
    lid = item["id"]
    lesson_dir = config.LESSONS_DIR / lid
    (lesson_dir / "media").mkdir(parents=True, exist_ok=True)
    out_path = lesson_dir / "lesson.json"

    resp = api_json_request(
        "POST",
        f"{API_BASE}/v1beta/interactions",
        {
            "model": "gemini-4-hydrogen",
            "store": False,
            "input": build_super_a1_prompt(item),
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": SCHEMA_LOWER,
            },
        },
        timeout=180,
    )

    text_out = None
    for step in resp.get("steps", []):
        if step.get("type") == "model_output":
            for part in step.get("content", []):
                if part.get("type") == "text" and part.get("text"):
                    text_out = part["text"]
    if not text_out:
        raise RuntimeError(f"Empty JSON output for {lid}")

    raw_data = json.loads(text_out)

    # Validate & sanitize vocabIds so zero dangling IDs exist
    valid_vids = {v["id"] for v in raw_data.get("vocabulary", [])}
    for idx, ln in enumerate(raw_data.get("lines", []), start=1):
        ln["id"] = f"line-{idx:02d}"
        ln["index"] = idx
        ln["vocabIds"] = [vid for vid in ln.get("vocabIds", []) if vid in valid_vids]

    lesson = attach_provisional_timestamps(raw_data, lid)
    lesson["level"] = "やさしい A1"
    lesson["category"] = item["category"]
    lesson["badge"] = item["badge"]

    out_path.write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  [Lesson JSON OK] {lid}: {lesson['titleJa']} ({len(lesson['lines'])}文)")
    return lesson


def rebuild_full_catalog() -> None:
    cat = json.loads(config.CATALOG_PATH.read_text(encoding="utf-8"))
    existing = {x["id"]: x for x in cat.get("lessons", [])}

    # Ensure manaus-demo has category metadata too
    if "manaus-demo" in existing:
        existing["manaus-demo"]["category"] = "nature"
        existing["manaus-demo"]["badge"] = "🌟 入門編（水の出会い＆市場）"
        existing["manaus-demo"]["level"] = "やさしい A1"

    ordered_entries = []
    if "manaus-demo" in existing:
        ordered_entries.append(existing["manaus-demo"])

    for item in MANAUS_15_TOPICS:
        lid = item["id"]
        lpath = config.LESSONS_DIR / lid / "lesson.json"
        if not lpath.exists():
            continue
        lesson = json.loads(lpath.read_text(encoding="utf-8"))
        ordered_entries.append(
            {
                "id": lid,
                "title": lesson["title"],
                "titleJa": lesson["titleJa"],
                "level": lesson.get("level", "やさしい A1"),
                "category": item["category"],
                "sceneCount": len(lesson.get("scenes", [])),
                "lineCount": len(lesson.get("lines", [])),
                "duration": lesson.get("duration", 0),
                "badge": item["badge"],
                "description": lesson.get("description", ""),
                "path": f"lessons/{lid}/lesson.json",
            }
        )

    cat["lessons"] = ordered_entries
    config.CATALOG_PATH.write_text(
        json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✅ カタログ更新完了: 全 {len(ordered_entries)} レッスン収録！")


def main() -> None:
    print("15個のマナウス超入門（Pre-A1〜A1）レッスンJSONを並列生成中...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(generate_one_lesson, item): item["id"] for item in MANAUS_15_TOPICS}
        for fut in as_completed(futs):
            lid = futs[fut]
            fut.result()
    rebuild_full_catalog()


if __name__ == "__main__":
    main()
