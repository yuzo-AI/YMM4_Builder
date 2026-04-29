"""
ymmp_builder.py
input/script.csv + input/template.ymmp + input/images/ → output/project.ymmp
"""
import copy
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATE_PATH = BASE_DIR / "input" / "template.ymmp"
SCRIPT_PATH = BASE_DIR / "input" / "script.csv"
IMAGES_DIR = BASE_DIR / "input" / "images"
SE_DIR = BASE_DIR / "input" / "se"
OUTPUT_PATH = BASE_DIR / "output" / "project.ymmp"

FIXED_LAYERS = {0, 2, 6}
DEFAULT_FRAMES_PER_CHAR = 8


def _calc_length(row: dict) -> int:
    lf = row.get("length_frames", "").strip()
    if lf:
        return int(lf)
    return max(1, len(row["dialogue"])) * DEFAULT_FRAMES_PER_CHAR


def build(
    template_path: Path = TEMPLATE_PATH,
    script_path: Path = SCRIPT_PATH,
    images_dir: Path = IMAGES_DIR,
    se_dir: Path = SE_DIR,
    output_path: Path = OUTPUT_PATH,
) -> None:
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

    # ---- Load CSV ----
    with script_path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) > 0, "script.csv が空です"

    # ---- Build per-cut items ----
    new_items = list(fixed_items)
    cursor = 0

    for row in rows:
        length = _calc_length(row)

        # Layer 3: ImageItem
        img = copy.deepcopy(img_tmpl)
        img["FilePath"] = str(images_dir / row["image"])
        img["Frame"] = cursor
        img["Length"] = length
        new_items.append(img)

        # Layer 4: VoiceItem
        voice = copy.deepcopy(voice_tmpl)
        voice["CharacterName"] = row["character"]
        voice["Serif"] = row["dialogue"]
        voice["Hatsuon"] = row["dialogue"]
        voice["Decorations"] = []
        voice.pop("VoiceCache", None)
        voice.pop("VoiceLength", None)
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
