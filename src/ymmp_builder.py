"""
ymmp_builder.py
input/script.csv + input/template.ymmp + input/images/ → output/project.ymmp
"""
import copy
import csv
import json
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

VOICEVOX_URL = "http://127.0.0.1:50021"
PRONOUNCE_TYPE = "YukkuriMovieMaker.Voice.VOICEVOXVoicePronounce, YukkuriMovieMaker"
AUDIO_QUERY_TYPE = "YukkuriMovieMaker.Voice.VOICEVOXAudioQuery, YukkuriMovieMaker"

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATE_PATH = BASE_DIR / "input" / "template.ymmp"
SCRIPT_PATH = BASE_DIR / "input" / "script.csv"
IMAGES_DIR = BASE_DIR / "input" / "images"
SE_DIR = BASE_DIR / "input" / "se"
OUTPUT_PATH = BASE_DIR / "output" / "project.ymmp"
CONFIG_PATH = BASE_DIR / "config" / "build_config.json"

FIXED_LAYERS = {0, 2, 6}
DEFAULT_FRAMES_PER_CHAR = 8


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def _cfg(config: dict, *keys, default=None):
    node = config
    for k in keys:
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def _fetch_voicevox_speakers(url: str = "http://127.0.0.1:50021/speakers") -> dict:
    """キャラ名 → {speaker_uuid, style_id} のマップを返す。失敗時は空dict。"""
    try:
        res = urllib.request.urlopen(url, timeout=3)
        speakers = json.loads(res.read())
        result = {}
        for s in speakers:
            name = s["name"]
            suuid = s.get("speaker_uuid", "")
            for st in s.get("styles", []):
                if name not in result or st.get("name") == "ノーマル":
                    result[name] = {"speaker_uuid": suuid, "style_id": st["id"]}
        return result
    except Exception:
        return {}


def _audio_query(text: str, style_id: int, speed: int = 100, silence_cfg: dict | None = None) -> dict | None:
    """VOICEVOX から AudioQuery を取得して無音・速度パラメータを適用して返す。"""
    s = silence_cfg or {}
    try:
        encoded = urllib.parse.quote(text)
        req = urllib.request.Request(
            f"{VOICEVOX_URL}/audio_query?text={encoded}&speaker={style_id}",
            method="POST",
        )
        res = urllib.request.urlopen(req, timeout=10)
        aq = json.loads(res.read())
        aq["$type"] = AUDIO_QUERY_TYPE
        aq["speedScale"] = speed / 100.0
        aq["prePhonemeLength"] = s.get("pre_phoneme_length", 0.0)
        aq["postPhonemeLength"] = s.get("post_phoneme_length", 0.0)
        aq["pauseLength"] = s.get("pause_length", 0.0)
        aq["pauseLengthScale"] = s.get("pause_length_scale", 0.0)
        for phrase in aq.get("accent_phrases", []):
            if phrase.get("pause_mora") is not None:
                phrase["pause_mora"]["vowel_length"] = s.get("pause_length", 0.0)
                phrase["pause_mora"]["consonant_length"] = 0.0
        return aq
    except Exception as e:
        print(f"[WARN] audio_query 失敗 (style_id={style_id}): {e}")
        return None


def _synthesize_frames(aq: dict, style_id: int, fps: int = 60, padding: int = 0) -> int | None:
    """合成WAVの実尺をフレーム数で返す。失敗時は None。"""
    import struct
    try:
        body = json.dumps(aq, ensure_ascii=False).encode()
        req = urllib.request.Request(
            f"{VOICEVOX_URL}/synthesis?speaker={style_id}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        wav = urllib.request.urlopen(req, timeout=60).read()
        sample_rate = struct.unpack_from("<I", wav, 24)[0]
        num_channels = struct.unpack_from("<H", wav, 22)[0]
        bits_per_sample = struct.unpack_from("<H", wav, 34)[0]

        pos = 12
        while pos < len(wav) - 8:
            chunk_id = wav[pos:pos+4]
            chunk_size = struct.unpack_from("<I", wav, pos+4)[0]
            if chunk_id == b"data":
                num_samples = chunk_size // (num_channels * (bits_per_sample // 8))
                return max(1, round(num_samples / sample_rate * fps) + padding)
            pos += 8 + chunk_size

    except Exception as e:
        print(f"[WARN] synthesis 失敗 (style_id={style_id}): {e}")
    return None


def _calc_length(row: dict, synth_frames: int | None = None, fps: int = 60) -> int:
    lf = row.get("length_frames", "").strip()
    if lf:
        return int(lf)
    if synth_frames is not None:
        return synth_frames
    return max(1, len(row["dialogue"])) * DEFAULT_FRAMES_PER_CHAR


def build(
    template_path: Path = TEMPLATE_PATH,
    script_path: Path = SCRIPT_PATH,
    images_dir: Path = IMAGES_DIR,
    se_dir: Path = SE_DIR,
    output_path: Path = OUTPUT_PATH,
) -> None:
    # ---- Load config ----
    config = _load_config()
    silence_cfg = config.get("silence", {})
    speed_override = _cfg(config, "voice", "speed_override")
    padding_frames = silence_cfg.get("padding_frames", 0)

    # ---- Load template ----
    text = template_path.read_text(encoding="utf-8-sig")
    data = json.loads(text)
    items = data["Timelines"][0]["Items"]

    fixed_items = [item for item in items if item.get("Layer") in FIXED_LAYERS]
    img_tmpl = next((item for item in items if item.get("Layer") == 3), None)
    voice_tmpl = next((item for item in items if item.get("Layer") == 4), None)
    se_tmpl = next((item for item in items if item.get("Layer") == 5), None)

    assert img_tmpl is not None, "テンプレートに Layer 3 (ImageItem) が見つかりません"
    assert voice_tmpl is not None, "テンプレートに Layer 4 (VoiceItem) が見つかりません"

    voice_speed = speed_override if speed_override is not None else voice_tmpl.get("VoiceParameter", {}).get("Speed", 100)

    # ---- Load CSV ----
    with script_path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) > 0, "script.csv が空です"

    # ---- Build character map (name → Character entry) ----
    char_map = {c["Name"]: c for c in data.get("Characters", [])}
    vv_map = _fetch_voicevox_speakers()

    needed_chars = {row["character"] for row in rows}
    for char_name in needed_chars:
        if char_name not in char_map:
            base = copy.deepcopy(data["Characters"][0])
            base["Name"] = char_name
            if char_name in vv_map:
                info = vv_map[char_name]
                base["VoiceParameter"]["StyleID"] = info["style_id"]
                base["Voice"]["Arg"] = f"{uuid.uuid4()}:{info['speaker_uuid']}"
            char_map[char_name] = base
            data["Characters"].append(base)
            print(f"[INFO] キャラクター追加: {char_name}")

    # ---- Build per-cut items ----
    new_items = list(fixed_items)
    cursor = 0

    for row in rows:
        char_name = row["character"]
        style_id = char_map[char_name]["VoiceParameter"]["StyleID"] if char_name in char_map else 0

        aq = _audio_query(row["dialogue"], style_id, speed=voice_speed, silence_cfg=silence_cfg)
        synth_frames = _synthesize_frames(aq, style_id, padding=padding_frames) if aq is not None else None
        length = _calc_length(row, synth_frames)

        # Layer 3: ImageItem
        img = copy.deepcopy(img_tmpl)
        img["FilePath"] = str(images_dir / row["image"])
        img["Frame"] = cursor
        img["Length"] = length
        new_items.append(img)

        # Layer 4: VoiceItem
        voice = copy.deepcopy(voice_tmpl)
        voice["CharacterName"] = char_name
        voice["Serif"] = row["dialogue"]
        voice["Hatsuon"] = aq["kana"] if aq and aq.get("kana") else row["dialogue"]
        voice["Decorations"] = []
        voice.pop("VoiceCache", None)
        voice.pop("VoiceLength", None)
        voice["VoiceParameter"]["StyleID"] = style_id
        if aq is not None:
            voice["Pronounce"] = {"$type": PRONOUNCE_TYPE, "AudioQuery": aq, "LipSyncFrames": None}
        else:
            voice.pop("Pronounce", None)
        voice["Frame"] = cursor
        voice["Length"] = length
        new_items.append(voice)

        # Layer 5: AudioItem (SE) — only when se column is non-empty
        se_name = row.get("se", "").strip()
        if se_name:
            assert se_tmpl is not None, (
                f"CSV に SE '{se_name}' が指定されていますが、"
                "テンプレートに Layer 5 (AudioItem) が存在しません"
            )
            se_item = copy.deepcopy(se_tmpl)
            se_item["FilePath"] = str(se_dir / se_name)
            se_item["Frame"] = cursor
            se_item["Length"] = length
            new_items.append(se_item)

        cursor += length

    # ---- Assertions ----
    img_items = [i for i in new_items if i.get("Layer") == 3]
    voice_items = [i for i in new_items if i.get("Layer") == 4]
    assert len(img_items) == len(voice_items) == len(rows), (
        f"アイテム数不一致: image={len(img_items)}, "
        f"voice={len(voice_items)}, csv={len(rows)}"
    )
    for img, voice in zip(img_items, voice_items):
        assert img["Frame"] == voice["Frame"], (
            f"Frame 不一致: image={img['Frame']}, voice={voice['Frame']}"
        )
        assert img["Length"] == voice["Length"], (
            f"Length 不一致: image={img['Length']}, voice={voice['Length']}"
        )

    # ---- Update fixed items Length to total duration ----
    for item in new_items:
        if item.get("Layer") in FIXED_LAYERS:
            item["Length"] = cursor

    # ---- Write output ----
    data["FilePath"] = str(output_path)
    data["Timelines"][0]["Items"] = new_items

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8-sig",
    )

    se_count = sum(1 for i in new_items if i.get("Layer") == 5)
    print(f"[OK] プロジェクト生成完了: {output_path}")
    print(f"     カット数  : {len(rows)}")
    print(f"     SE あり  : {se_count} カット")
    print(f"     総尺     : {cursor} frames ({cursor / 60:.1f}秒 @ 60fps)")
