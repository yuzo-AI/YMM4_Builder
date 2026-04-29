# YMM4_Builder

台本CSV + 漫画コマ画像 + テンプレ.ymmp から、完成済みYMM4プロジェクトファイルを自動生成する。

## ディレクトリ構造

```
YMM4_Builder/
├── input/
│   ├── template.ymmp     # template_generator.py で生成
│   ├── script.csv        # 台本CSV
│   ├── images/           # 連番PNG (01.png, 02.png ...)
│   └── se/               # 効果音ファイル (*.mp3 など)
├── output/
│   └── project.ymmp      # 生成済みプロジェクト
├── config/
│   └── voicevox_speakers.json   # キャラ名 → speaker_id マッピング
├── src/
│   ├── template_generator.py
│   ├── ymmp_builder.py
│   └── run.py
└── tests/
    └── test_minimal.py
```

## セットアップ

### 1. テンプレート生成

既存の完成済み `.ymmp` から雛形を生成する（初回のみ）:

```
python src/template_generator.py
```

### 2. voicevox_speakers.json の設定

VOICEVOXエンジン起動後、以下のURLから speaker_id を確認して `config/voicevox_speakers.json` に記載する:

```
http://127.0.0.1:50021/speakers
```

記載例:

```json
{
  "青山龍星": 13,
  "もち子さん": 20,
  "白上虎太郎": 29
}
```

### 3. script.csv の準備

`input/script.csv` を以下の形式で作成する:

```csv
id,character,dialogue,image,se,length_frames
01,青山龍星,セリフテキスト,01.png,効果音.mp3,170
02,青山龍星,セリフテキスト,02.png,,236
```

- `se` 列が空の行は効果音なし
- `length_frames` 列が空の行はデフォルト計算（文字数 × 8 frames）

### 4. 素材の配置

- 漫画コマ画像 → `input/images/` （01.png, 02.png ...）
- 効果音ファイル → `input/se/` （script.csv の `se` 列に記載したファイル名と一致させる）

### 5. プロジェクト生成

```
python src/run.py
```

`output/project.ymmp` が生成される。YMM4で開いて書き出すだけで動画が完成する。

## 注意事項

- VoiceCache を削除しているため、YMM4で開いた直後は音声再生成のため少し時間がかかる可能性がある
- `.ymmp` ファイルは UTF-8 with BOM 形式
- パスはWindowsの絶対パスで埋め込まれる
