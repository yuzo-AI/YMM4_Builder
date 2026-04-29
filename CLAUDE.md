# YMM4_Builder — Claude向けプロジェクト概要

## 目的

台本CSV + 漫画コマ画像 + テンプレ.ymmp → 完成済み .ymmp を自動生成する。

## .ymmp ファイル仕様（重要）

- UTF-8 with BOM (`encoding="utf-8-sig"`)
- 改行なし1行JSON（`separators=(',', ':')`, `ensure_ascii=False`）
- `$type` フィールドは .NET シリアライズ型情報 — 絶対に変更しない
- パスは Windows 絶対パス（JSON内でバックスラッシュをエスケープ）

## Timelines[0].Items のレイヤー構成

| Layer | 種別 | 役割 | 個数 |
|-------|------|------|------|
| 0 | ImageItem | 白背景（全期間） | 1固定 |
| 2 | TextItem | クレジットテキスト（全期間） | 1固定 |
| 3 | ImageItem | 漫画コマ（カットごと） | N個 |
| 4 | VoiceItem | 音声+字幕（カットごと） | N個 |
| 5 | AudioItem | 効果音（任意） | N個以下 |
| 6 | AudioItem | BGM（全期間） | 1固定 |
| 1,7,8 | 各種 | テンプレ生成時に削除 | — |

## VoiceItem の書き換えルール

| フィールド | 処理 |
|-----------|------|
| `CharacterName` | CSV の character 列 |
| `Serif` | CSV の dialogue 列 |
| `Hatsuon` | CSV の dialogue 列（Serif と同じ） |
| `Decorations` | 空配列 `[]` にクリア |
| `VoiceCache` | フィールドごと削除 |
| `VoiceLength` | フィールドごと削除 |
| `Frame` | 累積カーソル |
| `Length` | CSV の length_frames 列（空なら文字数×8） |
| 上記以外 | テンプレの値を踏襲 |

## ImageItem (Layer 3) の書き換えルール

| フィールド | 処理 |
|-----------|------|
| `FilePath` | `input/images/{image}` の絶対パス |
| `Frame` | 累積カーソル（VoiceItemと一致） |
| `Length` | VoiceItemと同じ値 |
| 上記以外 | テンプレの値を踏襲 |

## 固定アイテム（Layer 0, 2, 6）の Length 更新

全カットの Length 合計 = 総尺 → 全固定アイテムの Length を総尺に更新する。

## config/voicevox_speakers.json

キャラ名 → speaker_id のマッピング。VOICEVOXエンジンの `/speakers` から取得して手動記載。
現状は未使用（ymmp_builder.py で参照予定）。
