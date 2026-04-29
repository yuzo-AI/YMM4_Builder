"""
template_generator.py
既存の完成済み .ymmp から input/template.ymmp を生成する。

使い方:
    python src/template_generator.py [source.ymmp] [output_template.ymmp]

引数省略時のデフォルト:
    source : プロジェクトルートの .ymmp ファイル（ハードコード）
    output : input/template.ymmp
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SOURCE = BASE_DIR / "毎日アレを借りに来る、可愛い隣人が最高すぎた。.ymmp"
DEFAULT_OUTPUT = BASE_DIR / "input" / "template.ymmp"

FIXED_LAYERS = {0, 2, 6}


def generate_template(source_path: Path, output_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8-sig")
    data = json.loads(text)

    items = data["Timelines"][0]["Items"]

    fixed_items = [item for item in items if item.get("Layer") in FIXED_LAYERS]
    layer3_template = next((item for item in items if item.get("Layer") == 3), None)
    layer4_template = next((item for item in items if item.get("Layer") == 4), None)
    layer5_template = next((item for item in items if item.get("Layer") == 5), None)

    assert layer3_template is not None, "Layer 3 の ImageItem が見つかりません"
    assert layer4_template is not None, "Layer 4 の VoiceItem が見つかりません"

    template_items = [layer3_template, layer4_template]
    if layer5_template is not None:
        template_items.append(layer5_template)

    data["Timelines"][0]["Items"] = fixed_items + template_items
    data["FilePath"] = ""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8-sig",
    )

    se_note = "Layer 5 (AudioItem) × 1" if layer5_template else "なし（元ファイルに Layer 5 が存在しない）"
    print(f"[OK] テンプレート生成完了: {output_path}")
    print(f"     固定アイテム  : {len(fixed_items)} 個 (Layer 0, 2, 6)")
    print(f"     雛形アイテム  : Layer 3 (ImageItem) × 1, Layer 4 (VoiceItem) × 1, {se_note}")
    print(f"     削除アイテム  : Layer 1, 7, 8 および余分な Layer 3/4/5")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    generate_template(source, output)
