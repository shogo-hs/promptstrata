# Changelog

このファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) の形式に従います。
バージョン番号は [Semantic Versioning](https://semver.org/lang/ja/) に従います
（0.x のあいだは minor で破壊的変更が入りえます。詳細は
[docs/adr/0009-versioning.md](docs/adr/0009-versioning.md)）。

## [Unreleased]

## [0.1.0] - 2026-08-23

### Added

- 5レイヤー（ロール・語彙・ガバナンス・チャネル・手順）の YAML からシステムプロンプトを合成する機能
- レイヤーはすべて任意。存在するものだけを順に連結し、空の見出しを残さない
- 規則の優先順位（禁止事項 > チャネル > 手順 > 役割 > 語彙）をプロンプト冒頭に書き込む機能
- ビルド時変数（`$var`。`string.Template` による展開）
- `built.fingerprint`（本文の sha256 先頭12桁）と `built.sources`
- 層をまたぐ検査（`promptstrata lint`）— スキーマ違反、`id` の重複、語彙の別名衝突、変数の書式と不足、レイヤー0件の検出
- CLI（`promptstrata build` / `promptstrata lint`）
- 動くサンプル `examples/sorairo-pay/`

[Unreleased]: https://github.com/shogo-hs/promptstrata/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/shogo-hs/promptstrata/releases/tag/v0.1.0
