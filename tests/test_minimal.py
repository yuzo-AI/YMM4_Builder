"""
test_minimal.py — 1カット最小テスト
python tests/test_minimal.py
"""
import json
import sys
import tempfile
from pathlib import Path

# src を import パスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ymmp_builder import build

BASE_DIR = Path(__file__).resolve().parent.parent


def run_test() -> None:
    template_path = BASE_DIR / "input" / "template.ymmp"
    assert template_path.exists(), f"テンプレートが見つかりません: {template_path}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 最小 script.csv (1行、SE なし)
        csv_path = tmp / "script.csv"
        csv_path.write_text(
            "id,character,dialogue,image,se,length_frames\n"
            "01,青山龍星,テストセリフ,01.png,,120\n",
            encoding="utf-8-sig",
        )

        # ダミー画像ファイル (中身は問わない)
        images_dir = tmp / "images"
        images_dir.mkdir()
        (images_dir / "01.png").write_bytes(b"")

        output_path = tmp / "project.ymmp"

        build(
            template_path=template_path,
            script_path=csv_path,
            images_dir=images_dir,
            se_dir=tmp / "se",
            output_path=output_path,
        )

        # ---- 検証 ----
        assert output_path.exists(), "output が生成されていません"

        raw = output_path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", "UTF-8 BOM がありません"

        text = raw[3:].decode("utf-8")
        data = json.loads(text)

        items = data["Timelines"][0]["Items"]
        layers = [i["Layer"] for i in items]

        assert layers.count(3) == 1, f"Layer 3 は 1 個のはず: {layers.count(3)}"
        assert layers.count(4) == 1, f"Layer 4 は 1 個のはず: {layers.count(4)}"
        assert layers.count(5) == 0, f"SE なし行なので Layer 5 は 0 個のはず: {layers.count(5)}"

        img = next(i for i in items if i["Layer"] == 3)
        voice = next(i for i in items if i["Layer"] == 4)
        fixed = [i for i in items if i["Layer"] in {0, 2, 6}]

        assert img["Frame"] == voice["Frame"] == 0
        assert img["Length"] == voice["Length"] == 120
        assert all(i["Length"] == 120 for i in fixed), "固定アイテムの Length が総尺と一致しない"
        assert voice["Serif"] == "テストセリフ"
        assert voice["Hatsuon"] == "テストセリフ"
        assert voice["Decorations"] == []
        assert "VoiceCache" not in voice
        assert "VoiceLength" not in voice
        assert str(images_dir / "01.png") in img["FilePath"] or \
               (images_dir / "01.png").as_posix() in img["FilePath"], \
               f"FilePath が期待値と異なる: {img['FilePath']}"

        print("[OK] 全アサーション通過")
        print(f"     Items: {len(items)} 個")
        print(f"     総尺 : {120} frames")


if __name__ == "__main__":
    run_test()
